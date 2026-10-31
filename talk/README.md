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
| `TALK_TOOLS`   | Claude Code tools that run without asking                                         | `Read,Glob,Grep,Edit(./**),Write(./**),WebSearch,WebFetch` |
| `TALK_NO_LOG`  | set to `1` to keep no log                                                       | logging on                                                   |

Edit `spoken-style.md` to change how the assistant talks. It is passed to Claude as extra system instructions on every turn.

## What it may do, and how it asks

By default the assistant can do these without asking: create and edit files inside the working folder, read and search files anywhere on the computer, search the web, and open web pages. Change that list with `TALK_TOOLS`. Allow rules in your own Claude Code settings also apply, and anything they allow is not asked aloud.

Claude Code also runs read-only commands such as `git status` without asking, along with a simple `echo` into a file inside the working folder, since that is the same as editing a file there.

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
