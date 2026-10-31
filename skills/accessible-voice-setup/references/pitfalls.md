# Pitfalls

Each of these was observed in practice, not theorised. Each one presented as "it isn't working" with no error message.

## Phantom audio outputs

Three separate devices each reported an **active** audio endpoint while producing no audible sound. Treat "endpoint active" as meaningless on its own.

**1. A monitor with no speakers.** A GPU presents an audio sink over HDMI/DisplayPort whether or not the panel has any speakers in it. Windows showed the endpoint active, unmuted, at 46% volume, and happily rendered two and a half minutes of speech into nothing. Many budget monitors have no speakers; the audio endpoint appears regardless.

**2. A Bluetooth speaker that was asleep.** The device stayed paired, and its Bluetooth and A2DP/MEDIA nodes reported `OK` the whole time — but the **AudioEndpoint** repeatedly went inactive. Many Bluetooth speakers drop the audio stream after a few minutes with no signal, and the OS sends nothing while idle, so it sleeps, drops, reconnects, and sleeps again. The symptom the person reports is "it keeps disconnecting."

*Workaround if Bluetooth is unavoidable:* stream a near-silent looping WAV so the device never sees an idle channel. Generate a few seconds of near-silence (amplitude 1 rather than pure zero, since some devices gate on all-zeros), loop it with `System.Media.SoundPlayer.PlayLooping()` in a hidden background process, and track the PID so it can be stopped. This works, but prefer wired.

**3. A USB microphone's own headphone jack.** USB mics like the Blue Yeti expose a `Speakers (...)` playback endpoint for their built-in headphone socket. The OS may silently make it the **default output**. If nothing is plugged into the mic, audio vanishes. This is especially confusing because the device is obviously present and working in the other direction.

## Security policy silently blocking the configuration

On Windows, if every execution-policy scope is `Undefined`, the effective policy is `Restricted`, and **PowerShell profiles do not load at all**. A whole custom command vocabulary can exist on disk and simply not exist in the person's shell. There is no error until they try a command.

```powershell
Get-ExecutionPolicy -List          # check EVERY scope, not just the effective one
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`RemoteSigned` is user-scoped, needs no admin, and still requires signatures on downloaded scripts. Check this **before** building anything profile-based.

An already-open terminal never picks up a newly changed policy. The person must open a new window.

## Testing in a privileged environment and reporting it as theirs

This is the deepest trap, and it caused the one above to go unnoticed.

Claude Code's PowerShell tool runs with `-ExecutionPolicy Bypass` and exports `PSExecutionPolicyPreference=Bypass`, **which child processes inherit**. So every test of the profile passed, repeatedly, while the person's own shell could not load it.

To test anything that depends on policy or profile loading:

```powershell
Remove-Item Env:\PSExecutionPolicyPreference -ErrorAction SilentlyContinue
& powershell -Command '<test>'      # no -NoProfile, no -ExecutionPolicy
```

Generalise the principle: **if you have privileges the person does not, your test is not their experience.**

## Permission prompts that nobody can see

A voice loop usually drives Claude Code without its interactive screen, through `claude -p` or the Agent SDK. In that mode there is nowhere to show an approval prompt, so **every action that needs permission is denied silently**. The person hears only "that is outside what I can do," with no idea that a single approval was all it needed. It looks like a capability gap. It is a missing approval path.

Protected files make this worse. Claude Code always asks before editing files such as `~/.gitconfig` or anything under `~/.claude`, whatever the allow rules say, so even a generous allowlist still hits prompts.

Fix it by giving the approvals a spoken path, not by widening permissions until nothing asks:

- In the Agent SDK, pass a `can_use_tool` callback that reads the request aloud and takes a spoken yes or no. From the CLI, `--permission-prompt-tool` does the same job through an MCP tool. The `talk` program in this repository implements the SDK route.
- Describe the request for the ear, then read the real command too, a little slower. The description is written by the model, so it can't be the only thing the person hears. Say symbols and flags as words, such as "pipe" and "dash File Path".
- Let them ask "what does that do?" and get a plain explanation before anything runs. Someone still learning can't judge a command just by hearing it.
- Accept only a short, clear yes. "Okay, what does that do?" contains a yes word and is not a yes.
- Refuse on silence or an unclear answer. Never approve by default, and don't let the model report silence as "you said no."
- Keep a short allowlist of safe everyday actions so approvals stay rare enough to be heard and considered, not reflexively answered. Scope it: allowing `Write` as a whole tool lets it write anywhere on the computer without asking, while `Write(./**)` stays inside the working folder.

Check this before declaring a voice setup finished: ask the assistant to do one thing that needs approval, and confirm the request is actually spoken to the person. Use a command that changes something, such as deleting a scratch file. Read-only commands such as `git status` can be approved automatically, and so can a simple `echo` into a file the allow rules already cover, so those prove nothing.

## A voice program recording its own beep

A microphone can pick up a "start talking" beep, even from headphones. The recording then starts on the beep and stops at the silence after it, producing blank turns, and enough of those can trigger a false "check your microphone" warning. Discard the audio captured during the beep and for about a quarter second after it.

## Devices appearing and disappearing

USB audio devices and webcams vanished and reappeared between consecutive commands. Sometimes a genuine disconnect; sometimes a device that had not finished registering, where the default role was not yet assigned, producing a confusing "no default recording device" error seconds before it worked fine.

Re-query device state at the point of use. Never act on a reading from earlier in the conversation. If a device test fails, check the device still exists before concluding the device is broken.
