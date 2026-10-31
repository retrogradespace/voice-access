# voice-access

Tools for people who use a computer by voice. Both need Windows and Claude Code, which requires a Claude account.

- **`skills/accessible-voice-setup`** — a Claude skill. It audits what a Windows machine can actually do for sound in and out, verifies each direction with the person rather than trusting the operating system, then builds a dictatable one-word command vocabulary around what works. Copy the folder into `~/.claude/skills/` to use it with Claude Code.
- **`talk`** — a spoken dialogue loop. Speak, it transcribes locally, Claude Code answers, and the answer is read aloud. See `talk/README.md`.

The core rule behind both: a successful API call is not evidence that a human heard anything. Confirm with the person.

## Development

Co-authored by [retrogradespace](https://github.com/retrogradespace) and Claude, Anthropic's AI model, working together in Claude Code. retrogradespace designed the program, set the direction, tested `talk` on real hardware by voice, and reviewed the work before it was published. Claude wrote talk.py and revised code with requirements provided by retrogradespace. Documentation and all supporting reference files, scripts and skill files polished by Claude with dictation, design and editing contributed by retrogradespace.

Languages: Python (the `talk` program), PowerShell (the audio audit script and the Windows speech output), and Markdown (the skill and documentation).

## License

MIT. See `LICENSE`.

## Ideas?

Drop a and a human person will get back to you, but not after the machine has to nudge them🤓. Think this could be improved? Here for it, please reach out or take out a pull request , Happy hacking folks. 🤖
