# Designing a dictatable command vocabulary

For someone driving a machine by speech, the command set *is* the interface. Design it for the mouth, not the keyboard.

## Naming rules

1. **One plain English word per command.** `projects`, `status`, `louder`, `capture`. Not `cd-projects`, not `git-status`, not `set_volume`.
2. **No symbols, flags, or punctuation.** Anything requiring a hyphen, slash, quote, or dash is a dictation failure waiting to happen. Hide all of that inside the function.
3. **Common words that transcribe reliably.** Avoid homophones and anything a speech engine mangles. Avoid two-letter commands entirely.
4. **Verbs for actions, nouns for places.** `save`, `upload`, `discard` versus `projects`, `notes`, `sandbox`.
5. **Trailing free text where it is natural.** `save fixed the login bug` and `capture remember to call the dentist` should both work. Collect the remainder:
   ```powershell
   param([Parameter(ValueFromRemainingArguments = $true)]$words)
   $text = ($words -join ' ')
   ```
6. **Never require the person to name or save anything.** `capture` should append to a dated file created on demand. Any step that asks "what should I call this?" is friction at exactly the wrong moment.
7. **A discovery word.** `commands` must print the whole vocabulary. Someone cannot scroll back through terminal history without a keyboard, so the list must be one word away — and worth pairing with speech output so it can be *heard*.

## Shell collisions

Short natural words frequently collide with built-ins. In PowerShell, resolution order is **Alias → Function → Cmdlet → Application**, so an alias beats your function silently.

Release only the aliases you actually need:

```powershell
foreach ($a in @('history','h','r','start','read')) {
    if (Test-Path "Alias:$a") { Remove-Item "Alias:$a" -Force -ErrorAction SilentlyContinue }
}
```

Observed collisions: `history` and `h` (Get-History), `r` (Invoke-History), `start` (Start-Process), `read` (worth clearing defensively).

**Do not bulk-remove aliases you are not using.** Stripping `gc`, `gp`, `gl`, `sl` to be safe breaks unrelated scripts that depend on them. Remove only genuine conflicts.

Functions do beat external executables, so a `find` or `tree` function safely shadows `find.exe` and `tree.com` without intervention.

`$PID`, `$PROFILE` and other automatic variables are read-only — using them as your own variable names throws.

## Robustness

This is assistive technology. It must not throw.

- **Tolerate bad arguments.** Dictation will deliver a word where a number was expected. Parse defensively and fall back to a default rather than crashing:
  ```powershell
  $secs = 8
  $parsed = 0
  if ([int]::TryParse([string]$seconds, [ref]$parsed) -and $parsed -gt 0) { $secs = $parsed }
  ```
- **A bare command should teach itself.** `save` with no message prints `Say: save <your commit message>` instead of failing.
- **Confirm what happened.** `Captured at 14:32.` A silent success is indistinguishable from a silent failure when you cannot easily inspect state.
- **Never leave speech mid-sentence with no way out.** Use async speech plus a one-word `quiet` that cancels it.

## Speech output commands worth having

- `read <anything>` — speak arbitrary text
- `readfile <file>` — speak a whole file
- `quiet` — stop immediately, mid-sentence
- `faster` / `slower` — adjust rate
- `voice` — list voices, or switch

Strip markdown before speaking a file. Asterisks, hashes and backticks are read aloud as literal noise by SAPI, so clean them first:

```powershell
$body = (Get-Content $file -Raw) -replace '[#*`\-]', ' '
```

**Compose for the ear, not the eye.** Reading a written summary aloud verbatim does not work — file paths, version numbers and symbols are meaningless spoken. Write a separate spoken version: short sentences, explicit "Say: X" phrasing, no punctuation-heavy constructs. Roughly 330 words runs about 145 seconds, so set generous timeouts on blocking speech calls.

## Where the configuration lives

On Windows, confirm the real profile path rather than assuming — `Documents` is frequently redirected to OneDrive, so `$PROFILE` may resolve under `OneDrive\Documents\WindowsPowerShell\`. Use `$PROFILE` itself, and tell the person a `reload` command exists so edits take effect without opening a new window.

Validate before handing over:

```powershell
$errs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$errs)
```

A profile with a syntax error fails to load entirely, taking every command with it — the same total-failure mode as a blocking execution policy.
