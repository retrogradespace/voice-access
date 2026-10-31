---
name: accessible-voice-setup
description: Audit a computer's real input/output capabilities and build a working accessible configuration around them — voice control, text-to-speech, dictation, single-word command vocabularies, screen-reader-friendly output. Useful when someone operates their machine without a keyboard, mouse, or screen; relies on speech in or out; is setting up assistive technology; says a device "isn't working" or "I hear nothing"; or asks to make a machine usable given a disability, impairment, injury, or situational constraint. Also use before building any voice-driven or spoken workflow, since it establishes what the hardware can actually do.
---
# Accessible machine setup

Establish what a machine can **actually** do for someone, verify it with the person rather than with an API, then build a configuration around what is proven to work.

## The one rule that matters

**A successful API call is not evidence that a human perceived anything.**

Operating systems report audio endpoints as "active," speech calls as "completed," and devices as "OK" while the person hears, sees, or receives nothing. Every stage must be confirmed by the person — and confirmed in a way that cannot be satisfied by a polite "okay."

Use **repeat-back verification**: speak a specific, arbitrary word and ask them to tell you what it was.

> "Listen carefully. The test word is *lantern*. Tell me the word you heard."

If they say "lantern," output works. "Did you hear that?" does not establish this — it invites a yes that means "I heard you ask."

The mirror for input: have them say a specific phrase, then show them what was captured.

## Workflow

Work in this order. Do not build configuration on unverified hardware.

### 1. Discover what physically exists

Enumerate **endpoints**, not adapters. An audio *controller* existing tells you nothing about whether a speaker is attached.

See `references/windows-audio-diagnostics.md` for the exact commands, including how to read endpoint states and how to install the volume/device-switching module.

Establish, as facts:

- Which output endpoints exist, and which are **genuinely connected** versus merely present
- Which input endpoints exist, their level and mute state
- What the default device is for each direction
- Whether a monitor, dock, or USB device is presenting a phantom audio sink

### 2. Verify each direction with the person

Run repeat-back verification for output. Run a level measurement plus a read-back for input.

Record which device was default **at the moment of the test**, and check it again afterwards. Defaults change mid-operation, especially with Bluetooth.

### 3. Configure around what works

Only now build the interface. See `references/voice-command-design.md` for naming rules — the short version: one plain dictatable English word per command, no flags, no symbols, no punctuation, and a `commands` word that lists everything.

Make the configuration **self-describing**, so the person can recover their own bearings without reading documentation.

### 4. Harden it

Assistive technology that needs maintenance has failed. Check that the configuration:

- Survives a reboot and a new shell
- Loads under the system's **actual** security policy (see Pitfalls — this is the most common silent failure)
- Degrades gracefully on bad input rather than throwing
- Does not depend on a device that can disappear
- Has a spoken path for permission approvals if Claude runs without its interactive screen; otherwise every approval is silently denied (see Pitfalls)

## Choosing hardware

When something must be bought or attached, bias hard toward **wired**.

Bluetooth audio has many silent failure modes: idle-sleep disconnects, profile-level connection without an active audio endpoint, shared-radio arbitration on combo WiFi/BT chips, and devices being reclaimed by another paired host. Each is individually fixable and collectively exhausting. For something a person depends on to use their computer, a cheap wired device beats an expensive wireless one.

**Watch for echo.** An open microphone plus any speaker in the same room means the machine's own speech output is captured as input, which corrupts dictation. Headphones eliminate it. A conference speakerphone with hardware echo cancellation manages it. Plain speakers plus an open mic do not.

## Working with the person

Adapt to the constraint, don't narrate around it.

- **Do the work.** Do not hand someone who cannot type a command to type. Run it yourself.
- **Avoid multiple-choice dialogs.** They are a click-through interface; for someone using voice, prose questions they can answer by speaking are cheaper.
- **Expect garbled input** from dictation or on-screen keyboards. Infer from context; do not ask for a repeat. Never invite someone to apologize for how their input arrives.
- **One mouse click beats any amount of typing.** Prefer actions completed by approving a prompt.
- **Report failure plainly.** If something does not work, say so and say what you know. Someone depending on this cannot act on optimism.

## Never

- Claim something played, displayed, or was received because the call returned successfully
- Test in an environment you have privileged access to and report the result as the person's experience
- Leave speech output, or any assistive path, silently broken
- Recommend a configuration whose failure mode is "debug it yourself"

## Reference files

- `references/windows-audio-diagnostics.md` — exact enumeration commands, endpoint state codes, module setup
- `references/voice-command-design.md` — naming a dictatable command vocabulary, collision handling
- `references/pitfalls.md` — specific traps, each observed in practice
- `scripts/audit-audio.ps1` — runnable Windows audio audit
