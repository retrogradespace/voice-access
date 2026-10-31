# talk

Spoken dialogue with Claude on Windows. Listens on the default microphone, transcribes on your own machine with Whisper, sends the words to the Claude Code command line, and speaks the answer on the default output. No audio leaves the computer. Claude receives the transcribed text, along with any files it reads and anything else it works with while helping you.

## Setup

1. Install Python (tested on 3.14) and the Claude Code command line, and sign the command line in once with your Claude account (`claude auth status` should say you are logged in). The separate install is required: the Claude agent library that talk uses carries its own copy, but talk runs the one you signed in to.
2. In this folder:

   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Run it from the folder you want the assistant to work in:

   ```
   path\to\talk\.venv\Scripts\python path\to\talk\talk.py
   ```

   Add `--mirror` to test the microphone without the assistant: it repeats back what it heard.

The first run downloads the Whisper model, which takes a minute.

For someone who cannot type, wrap both commands as one-word PowerShell functions (for example `talk` and `mirror`) in their profile. The `accessible-voice-setup` skill in this repository covers how to do that safely.

## While it is running

- "goodbye" or "stop listening" — stop
- "repeat that" — hear the last answer again
- "new conversation" — forget the conversation so far
- "permissions" — hear what Claude can do without asking, and how to change it

## Sounds

- one high beep — listening
- two rising beeps — heard you, working
- soft low tick every few seconds — still waiting for the answer
- long low tone — something went wrong on that turn; it keeps listening

## Settings

All optional, set as environment variables.

| Variable         | Meaning                                                                           | Default                                                      |
| ---------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `TALK_WORKDIR` | folder the assistant works in                                                     | the current folder                                           |
| `TALK_NOTES`   | folder for the daily dialogue log                                                 | `notes` inside the working folder                          |
| `TALK_NAME`    | how the log labels the speaker                                                    | `You`                                                      |
| `TALK_VOICE`   | Windows voice                                                                     | `Microsoft Zira Desktop`                                   |
| `TALK_RATE`    | speaking speed, `-10` slowest to `10` fastest; try `-2` for a little slower | `0`                                                        |
| `TALK_TOOLS`   | Claude Code tools that run without asking; replaces the spoken permissions        | not set; see [What it may do](#what-it-may-do-and-how-it-asks) |
| `TALK_NO_LOG`  | set to `1` to keep no log                                                       | logging on                                                   |

Edit `spoken-style.md` to change how the assistant talks. It is passed to Claude as extra system instructions on every turn.

## What it may do, and how it asks

It starts with the smallest set of permissions. Without asking, it can only read and search files in the working folder, and run read-only commands there such as `git status`. Those come from Claude Code itself, and `talk` can't turn them off. Allow rules in your own Claude Code settings also apply, and anything they allow is not asked aloud.

### Choosing how much to allow

You decide how far to widen that, by voice. Say each phrase on its own after the beep:

| Say | Claude can then do this without asking | The risk it reads to you first |
|---|---|---|
| "allow editing" | create and change files in the working folder, including a simple `echo` into a file there | It could overwrite your work. |
| "allow reading" | read and search files anywhere on the computer | Anything it reads is sent to Claude. |
| "allow web" | search the web and open web pages | A harmful page could try to trick it. |

Each one takes effect only after a short, clear yes. To go back, say "ask before editing", "ask before reading" or "ask before web"; these need no yes. Say "permissions" at any time to hear the current state and the options.

Allowing both reading and web is the widest choice, because a harmful page could try to trick Claude into sending a file's contents somewhere.

Your choices are saved for next time and apply in whichever folder you start `talk` from. The program handles these phrases itself, so Claude can't change them. It refuses Claude's requests to change the settings file, even if you say yes.

They are stored in `.claude\talk-permissions.json` in your user folder, for example `{"allowed": ["web"]}`. A helper can edit that file by hand or delete it to start over. Someone who wants finer control can set `TALK_TOOLS` instead, which replaces these choices and turns off the spoken changes for that window:

```
$env:TALK_TOOLS = "Edit(./**),Write(./**)"
```

Anything else, such as deleting a file or uploading to GitHub, is asked aloud: "Claude wants to run a command it describes as: save the changes to git. The actual command is: git commit. Say yes to allow it, or no to refuse." The description is Claude's own wording, so the real command is read out as well, more slowly than other speech and up to about 200 characters. The full request appears on screen and in the log, along with the outcome.

Say yes or no after the beep, or ask "what does that do?". Asking stops the action, nothing runs, and Claude explains it in plain words and then asks again.

Only a short, clear answer counts as yes, such as "yes", "okay" or "go ahead". A hesitant "yeah, um" does not. If there is no clear answer within about thirty seconds, after one retry, the answer is no. Claude is told about a refusal and will not retry it.

Questions that Claude would normally show as clickable choices are read aloud too, with their options. Say one of the options, or give your own answer.

This matters because a voice session has no screen to click "allow" on. Without spoken approvals, every action that needs permission would be refused quietly, and Claude could only say it was not allowed.

Unless `TALK_NO_LOG` is set, every exchange is appended to `dialogue-<date>.md` in the notes folder. That log is a full transcript; keep it somewhere private.

## Known quirks

- `CT2_USE_MKL=0` is set in `talk.py`; on some machines the transcriber otherwise fails with `mkl_malloc: failed to allocate memory`.
- Audio is passed to Whisper as an array, never as a file path, which avoids audio-file decoding problems on some Python versions.
- The Claude command line signs in separately from the desktop app.
- `requirements.txt` holds some audio packages at older versions because Windows Smart App Control blocked a newer build. If an install fails with `An Application Control policy has blocked this file`, that is the cause.
- Windows only for now: it uses `winsound` for beeps and the built-in Windows speech engine for output.
