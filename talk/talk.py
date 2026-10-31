"""Spoken dialogue loop: listen on the default mic, transcribe locally,
hand the words to Claude Code, speak the answer on the default output.

When Claude needs permission for something, such as running a command or
editing a file outside the pre-approved list, the request is read aloud and
the answer is taken by voice. Nothing that needs approval happens silently,
and nothing is refused silently.

    talk.py            full dialogue
    talk.py --mirror   no assistant; speak back exactly what was heard
    talk.py --once     one exchange, then exit (used for testing)

Settings come from environment variables, all optional:

    TALK_WORKDIR   folder the assistant works in (default: the current folder)
    TALK_NOTES     folder for the daily dialogue log (default: WORKDIR/notes)
    TALK_NAME      how the log labels the speaker (default: You)
    TALK_VOICE     Windows voice name (default: Microsoft Zira Desktop)
    TALK_RATE      speaking speed from -10 (slowest) to 10 (fastest) (default: 0)
    TALK_TOOLS     tools that run without asking (default: see ALLOWED_TOOLS)
    TALK_NO_LOG    set to 1 to keep no log at all
"""
import os
os.environ.setdefault("CT2_USE_MKL", "0")  # some MKL builds fail to allocate memory on CPU
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import argparse
import asyncio
import datetime
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import winsound
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import sounddevice as sd

HERE = Path(__file__).resolve().parent
WORKDIR = Path(os.environ.get("TALK_WORKDIR") or Path.cwd()).expanduser()
NOTES = Path(os.environ.get("TALK_NOTES") or WORKDIR / "notes").expanduser()
STYLE_FILE = HERE / "spoken-style.md"
SPEAKER = os.environ.get("TALK_NAME") or "You"
KEEP_LOG = os.environ.get("TALK_NO_LOG") != "1"

RATE = 16000
BLOCK = 480                 # 30 ms
SILENCE_END = 1.4           # seconds of quiet that end an utterance
MAX_UTTERANCE = 90
APPROVAL_WAIT = 30          # seconds to wait for a spoken yes or no before refusing
MODELS = ("small.en", "base.en", "tiny.en")   # first that loads wins; smaller ones need less memory
VOICE = os.environ.get("TALK_VOICE") or "Microsoft Zira Desktop"
try:
    SPEECH_RATE = max(-10, min(10, int(os.environ.get("TALK_RATE") or 0)))
except ValueError:
    SPEECH_RATE = 0
# These run without asking. Anything else is asked aloud.
ALLOWED_TOOLS = os.environ.get("TALK_TOOLS") or "Read,Glob,Grep,Edit(./**),Write(./**),WebSearch,WebFetch"
CLAUDE_TIMEOUT = 600        # includes time spent waiting for spoken approvals

STOP_PHRASES = {"goodbye", "good bye", "stop listening", "end conversation"}
RESET_PHRASES = {"new conversation", "start over", "fresh start"}
REPEAT_PHRASES = {"repeat that", "say that again", "say again"}
# Whisper invents these from near-silence.
HALLUCINATIONS = {"", "you", "thank you", "thanks for watching", "bye", "thank you for watching"}

YES_WORDS = {"yes", "yeah", "yep", "allow", "approve", "approved", "okay", "ok", "sure"}
YES_PHRASES = ("go ahead", "do it")
# A yes may contain only these besides its yes words. "Um" stays out: it means still deciding.
YES_EXTRAS = {"go", "ahead", "do", "it", "please", "thanks", "thank", "you"}
NO_WORDS = {"no", "nope", "deny", "refuse", "stop", "cancel", "dont", "not", "goodbye"}
EXPLAIN = "explain"
EXPLAIN_PHRASES = ("what does", "what do", "what is that", "whats that", "explain")
COMMAND_RATE = max(-10, SPEECH_RATE - 1)    # commands are harder to follow than sentences
# Spoken in place of symbols that change what a command does.
COMMAND_SYMBOLS = (("&&", " then "), ("||", " or else "), ("\n", " then "), (";", " then "), ("|", " pipe "), ("&", " and "),
                   (">", " into "), ("<", " from "), ("*", " star "), ("#", " hash "), ("`", " backtick "))


def say(msg):
    print(msg, flush=True)


def beep(kind):
    tones = {
        "listen": [(880, 90)],
        "heard": [(660, 70), (990, 70)],
        "tick": [(330, 40)],
        "error": [(220, 300)],
        "bye": [(660, 90), (440, 140)],
    }
    try:
        for f, ms in tones[kind]:
            winsound.Beep(f, ms)
    except Exception:
        pass


# ---------------------------------------------------------------- speech out

_SPEAK_PS = (
    "Add-Type -AssemblyName System.Speech;"
    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "try { $s.SelectVoice($env:TALK_VOICE) } catch {};"
    "$s.Volume = 100; $s.Rate = [int]$env:TALK_RATE;"
    "$s.Speak($env:TALK_TEXT)"
)


def clean_for_speech(text):
    text = re.sub(r"```.*?```", " code omitted. ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*`_>|]", " ", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    return re.sub(r"[ \t]+", " ", text).strip()


def speak(text, rate=SPEECH_RATE):
    """Blocking. A fresh synthesizer each time, so it follows the current default output."""
    text = clean_for_speech(text)
    if not text:
        return
    env = dict(os.environ, TALK_TEXT=text[:30000], TALK_VOICE=VOICE, TALK_RATE=str(rate))
    env.pop("PSExecutionPolicyPreference", None)
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _SPEAK_PS],
                       env=env, timeout=600)
    except Exception as e:
        say(f"[speech failed: {e}]")
        beep("error")


# ----------------------------------------------------------------- speech in

def load_model():
    from faster_whisper import WhisperModel
    last = None
    for name in MODELS:
        try:
            m = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=6)
            say(f"[transcriber: {name}]")
            return m
        except Exception as e:
            last = e
            say(f"[could not load {name}: {e}]")
    raise RuntimeError(f"no transcription model could be loaded: {last}")


def rms(block):
    return float(np.sqrt(np.mean(np.square(block)))) if len(block) else 0.0


def record_utterance(stream, threshold, wait=None):
    """Wait for speech, return it as float32 mono once the speaker goes quiet.
    With wait set, give up and return None if nobody speaks within that many seconds."""
    pre, chunks = [], []
    loud_run, quiet, started = 0, 0.0, False
    t0 = time.time()
    while True:
        data, _ = stream.read(BLOCK)
        block = data[:, 0].copy()
        level = rms(block)
        if not started:
            if wait is not None and time.time() - t0 > wait:
                return None
            pre.append(block)
            pre = pre[-12:]                     # ~360 ms of lead-in
            loud_run = loud_run + 1 if level > threshold else 0
            if loud_run >= 3:
                started, chunks, t0 = True, list(pre), time.time()
            continue
        chunks.append(block)
        quiet = quiet + BLOCK / RATE if level < threshold else 0.0
        if quiet >= SILENCE_END or time.time() - t0 > MAX_UTTERANCE:
            return np.concatenate(chunks)


def calibrate(stream):
    levels = [rms(stream.read(BLOCK)[0][:, 0]) for _ in range(25)]
    floor = float(np.median(levels))
    return floor, max(floor * 3.5, 0.004)


def transcribe(model, audio):
    kwargs = dict(language="en", beam_size=5, condition_on_previous_text=False)
    try:
        segs, _ = model.transcribe(audio, vad_filter=True, **kwargs)
        segs = list(segs)
    except Exception:
        segs, _ = model.transcribe(audio, **kwargs)
        segs = list(segs)
    return " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.8).strip()


def beep_listen(stream):
    """Signal that it is listening, without recording the beep: a mic can pick it up from headphones."""
    beep("listen")
    stream.read(stream.read_available)
    stream.read(BLOCK * 8)              # 240 ms for what is still ringing


def listen(model, wait=None):
    """One short spoken answer, as text. Empty if nobody spoke in time."""
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK) as stream:
        _, threshold = calibrate(stream)
        beep_listen(stream)
        audio = record_utterance(stream, threshold, wait)
    if audio is None:
        return ""
    beep("heard")
    return transcribe(model, audio)


def normal(text):
    return re.sub(r"[^a-z ]", "", text.lower()).strip()


def yes_or_no(text):
    """True for a short, clear yes, False for no, None for anything else.
    A yes word inside a longer sentence, as in "okay, what does that do", is not a yes."""
    key = normal(text)
    words = set(key.split())
    yes = bool(words & YES_WORDS) or any(p in key for p in YES_PHRASES)
    if words & NO_WORDS:
        return None if yes else False
    return True if yes and words <= YES_WORDS | YES_EXTRAS else None


# ------------------------------------------------------------ approvals aloud

def clip(text, limit=200):
    text = clean_for_speech(str(text))
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + ", and more"


def spoken_command(command):
    for symbol, words in COMMAND_SYMBOLS:
        command = command.replace(symbol, words)
    command = re.sub(r"(?:^|(?<=\s))(-+)", lambda m: "dash " * len(m[1]), command)  # -Path, --force
    command = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", command)     # FilePath runs together when spoken
    return clip(command)


def describe(tool, args):
    """What a permission request means, in words that make sense spoken."""
    def file_name(p):
        path = Path(str(p))
        if not path.name:
            return str(p)
        return f"{path.name} in the folder {path.parent.name}" if path.parent.name else path.name

    if tool in ("Bash", "PowerShell"):
        if args.get("description"):
            return f"run a command it describes as: {clip(args['description'])}"
        return "run a command"
    if tool == "Write":
        return f"create or replace the file {file_name(args.get('file_path', ''))}"
    if tool in ("Edit", "MultiEdit", "NotebookEdit"):
        return f"change the file {file_name(args.get('file_path') or args.get('notebook_path', ''))}"
    if tool == "Read":
        return f"read the file {file_name(args.get('file_path', ''))}"
    if tool == "WebFetch":
        return f"open a web page on {urlparse(args.get('url', '')).netloc or 'the web'}"
    if tool.startswith("mcp__"):
        parts = tool.split("__")
        action = parts[-1].replace("_", " ").replace("-", " ")
        service = parts[1].replace("_", " ").replace("-", " ") if len(parts) > 2 else "a connected service"
        return f"use {action}, from {service}"
    return f"use the {tool} tool"


# --------------------------------------------------------------------- brain

def find_claude():
    for name in ("claude.cmd", "claude.exe", "claude"):
        p = shutil.which(name)
        if p:
            return p
    return None


def drop_leaked_env():
    # Drop variables a parent Claude session may have leaked; a normal shell has none.
    for k in list(os.environ):
        if k.startswith(("CLAUDE_CODE_", "CLAUDE_AGENT_SDK")) or k in ("CLAUDECODE", "CLAUDE_PID"):
            os.environ.pop(k, None)


class Brain:
    def __init__(self, model):
        self.exe = find_claude()
        self.model = model
        self.session = None
        self.quiet = threading.Event()      # set while asking aloud, so the ticker stays silent
        drop_leaked_env()

    def ask(self, text):
        if not self.exe:
            return "The Claude command is not installed, so I can hear you but cannot answer."
        try:
            import claude_agent_sdk  # noqa: F401
        except ImportError:
            return ("The Claude agent library is not installed, so I can hear you but cannot answer. "
                    "It needs a one time install from the requirements file.")
        stop = threading.Event()
        threading.Thread(target=self._ticker, args=(stop,), daemon=True).start()
        try:
            return asyncio.run(asyncio.wait_for(self._ask(text), CLAUDE_TIMEOUT))
        except TimeoutError:
            return "That took more than ten minutes, so I stopped waiting. Try asking again."
        except Exception as e:
            say(f"[assistant error: {type(e).__name__}: {e}]")
            return "The assistant ran into a problem on that turn. The details are on screen."
        finally:
            stop.set()

    async def _ask(self, text):
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage
        options = ClaudeAgentOptions(
            allowed_tools=[t.strip() for t in ALLOWED_TOOLS.split(",") if t.strip()],
            system_prompt={"type": "preset", "preset": "claude_code",
                           "append": STYLE_FILE.read_text(encoding="utf-8")},
            permission_mode="default",      # anything not pre-approved comes to _approve
            can_use_tool=self._approve,
            cwd=str(WORKDIR),
            resume=self.session,
            cli_path=self.exe,
        )
        result = None
        async with ClaudeSDKClient(options=options) as client:
            await client.query(text)
            async for msg in client.receive_response():
                if isinstance(msg, ResultMessage):
                    result = msg
        if result is None:
            return "The assistant finished but said nothing."
        self.session = result.session_id or self.session
        reply = (result.result or "").strip()
        if "not logged in" in reply.lower():
            self.session = None
            return ("The Claude command line is not signed in on this machine, so I can hear you but cannot answer yet. "
                    "It needs a one time sign in.")
        if result.is_error and not reply:
            say(f"[assistant error: {result.subtype}]")
            return "The assistant ran into a problem on that turn. The details are on screen."
        return reply or "The assistant finished but said nothing."

    async def _approve(self, tool_name, input_data, context):
        from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny
        self.quiet.set()
        try:
            if tool_name == "AskUserQuestion":
                answers = await asyncio.to_thread(self._answer_questions, input_data)
                return PermissionResultAllow(
                    updated_input={"questions": input_data.get("questions", []), "answers": answers})
            exact = f"{tool_name} {json.dumps(input_data, ensure_ascii=False)}"
            say(f"[exact request: {exact}]")
            # A command's description is written by Claude, so the real command is read out too.
            command = spoken_command(input_data.get("command", "")) if tool_name in ("Bash", "PowerShell") else ""
            allowed = await asyncio.to_thread(self._spoken_yes_no, describe(tool_name, input_data), command)
            log_approval(exact, allowed)
        finally:
            self.quiet.clear()
        if allowed is True:
            return PermissionResultAllow(updated_input=input_data)
        if allowed == EXPLAIN:
            return PermissionResultDeny(
                message="Nothing has run. The user asked what this does before deciding, and may be new to "
                        "programming. In plain words, explain what it would do and any risk, then ask whether "
                        "to go ahead and wait for their answer. Try the action again only if they say yes.")
        answer = "said no" if allowed is False else "gave no clear answer, so it was refused"
        return PermissionResultDeny(
            message=f"The user was asked aloud and {answer}. Do not retry this action. "
                    "Tell them briefly what you would have done, so they can decide another way.")

    def _spoken_yes_no(self, what, command=""):
        """True or False as answered, EXPLAIN if they asked what it does, None if no clear answer came."""
        say(f"[approval needed: {what}]")
        prompt = f"Claude wants to {what}."
        ask = "Say yes to allow it, no to refuse, or ask what does that do."
        for _ in range(2):
            speak(prompt)
            if command:
                speak(f"The actual command is: {command}.", rate=COMMAND_RATE)
            speak(ask)
            heard = listen(self.model, wait=APPROVAL_WAIT)
            say(f"[approval answer: {heard!r}]")
            if any(p in normal(heard) for p in EXPLAIN_PHRASES):
                speak("Nothing has run. Claude will explain.")
                return EXPLAIN
            answer = yes_or_no(heard)
            if answer is not None:
                speak("Allowed." if answer else "Refused.")
                return answer
            prompt = f"I did not catch a yes or a no. Should Claude {what}?"
            ask = "Say yes, no, or what does that do."
        speak("I did not get a clear answer, so I refused it.")
        return None

    def _answer_questions(self, data):
        answers = {}
        for q in data.get("questions", []):
            question = q.get("question", "")
            labels = [o.get("label", "") for o in q.get("options", [])]
            speak(f"{question} The choices are: {', '.join(labels)}. Say one, or give your own answer.")
            heard = listen(self.model, wait=APPROVAL_WAIT)
            say(f"[answer: {heard!r}]")
            key = normal(heard)
            picked = [l for l in labels if normal(l) and normal(l) in key]
            answers[question] = ", ".join(picked) if picked else (heard or "No answer was given.")
        return answers

    def _ticker(self, stop):
        while not stop.wait(2.5):
            if not self.quiet.is_set():
                beep("tick")


# ---------------------------------------------------------------------- loop

def append_log(entry):
    if not KEEP_LOG:
        return
    try:
        NOTES.mkdir(parents=True, exist_ok=True)
        with open(NOTES / f"dialogue-{datetime.datetime.now():%Y-%m-%d}.md", "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        say(f"[could not write the dialogue log: {e}]")


def log_heard(heard):
    append_log(f"\n**{datetime.datetime.now():%H:%M} {SPEAKER}:** {heard}\n")


def log_reply(reply):
    append_log(f"\n**Claude:** {reply}\n")


def log_approval(exact, allowed):
    outcome = "allowed" if allowed is True else "held for an explanation" if allowed == EXPLAIN else "refused"
    append_log(f"\n**{datetime.datetime.now():%H:%M} Approval {outcome}:** `{exact}`\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", action="store_true")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    try:
        mic = sd.query_devices(kind="input")["name"]
        out = sd.query_devices(kind="output")["name"]
    except Exception as e:
        say(f"[no audio device: {e}]")
        speak("I cannot find a microphone, so I cannot listen.")
        return 1
    say(f"[mic: {mic}]  [output: {out}]")

    speak("Starting. One moment while I load.")
    try:
        model = load_model()
    except Exception as e:
        say(f"[{e}]")
        speak("The transcription engine would not load. This is usually low memory. Close something and try again.")
        return 1

    brain = None if args.mirror else Brain(model)
    last_reply = ""
    speak("Mirror ready. I will repeat what I hear. Say goodbye to stop." if args.mirror
          else "Ready. Speak after the beep. Say goodbye to stop.")

    empty_runs = 0
    while True:
        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK) as stream:
                floor, threshold = calibrate(stream)
                beep_listen(stream)
                audio = record_utterance(stream, threshold)
            beep("heard")
            peak = float(np.max(np.abs(audio)))
            heard = transcribe(model, audio)
            say(f"[{len(audio) / RATE:.1f}s, peak {peak:.3f}, floor {floor:.4f}] {SPEAKER}: {heard}")

            key = normal(heard)
            if key in HALLUCINATIONS or len(key) < 2:
                empty_runs += 1
                if empty_runs == 3:
                    speak("I keep hearing sound but no words. Check the microphone light, or move closer.")
                continue
            empty_runs = 0

            if key in STOP_PHRASES:
                beep("bye")
                speak("Goodbye.")
                return 0
            if key in REPEAT_PHRASES and last_reply:
                speak(last_reply)
                continue
            if key in RESET_PHRASES and brain:
                brain.session = None
                speak("New conversation.")
                continue

            log_heard(heard)        # first, so approvals during the turn land after it in the log
            reply = f"I heard: {heard}" if args.mirror else brain.ask(heard)
            last_reply = reply
            say(f"Claude: {reply}\n")
            log_reply(reply)
            speak(reply)
            if args.once:
                return 0
        except KeyboardInterrupt:
            beep("bye")
            return 0
        except Exception as e:
            say(f"[error: {type(e).__name__}: {e}]")
            beep("error")
            speak("Something went wrong on that turn. I am still listening.")
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
