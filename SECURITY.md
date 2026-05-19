# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.2 | ✓ |
| < 0.2.2 | ✗ — upgrade to 0.2.2 (silent upgrade from 0.2.0/0.2.1) |

## Reporting a vulnerability

**Do not file public issues for security vulnerabilities.** Open a GitHub Security Advisory at https://github.com/rafaelscosta/claude-i/security/advisories/new instead, or email the maintainer directly via the contact in the GitHub profile.

When reporting, include:

- A description of the vulnerability and its impact.
- Steps to reproduce, ideally a minimal proof-of-concept.
- Your claude-i version (`claude-i --version`), Python version, and OS.

You can expect:

- Acknowledgement within 7 days.
- A status update within 14 days.
- A fix and coordinated disclosure plan within 30 days for high-severity issues, longer for low-severity (negotiated case-by-case).

## What is in scope

- The `claude-i` CLI itself and its supporting modules (`hook.py`, `runner.py`, `cli.py`, etc.).
- The `install.sh` bootstrap script.
- The Homebrew formula at `rafaelscosta/homebrew-claude-i`.

## What is out of scope

- Vulnerabilities in `claude` (Anthropic's Claude Code CLI). Report those to Anthropic directly: https://www.anthropic.com/security
- Vulnerabilities in `tmux`. Report upstream: https://github.com/tmux/tmux/security
- Vulnerabilities in Python or `pipx`. Report to their respective projects.
- Issues that require the attacker to already have local arbitrary-code-execution capability on the user's machine.

## Threat model

claude-i orchestrates a sub-`claude` process via tmux on the same machine. It reads/writes to `~/.claude/settings.json` (with `fcntl.flock`) and creates short-lived sentinel files in `tempfile.gettempdir()`. It does not open network sockets, does not send telemetry, and does not transmit any data outside the local machine.

Trust boundary: claude-i trusts the same user account it runs as. It does NOT defend against an attacker who can already write to `~/.claude/settings.json` or read user-owned tempdir files — they would already have full agent capabilities. See the G4 / G6 / G7 hardening notes in `docs/stories/STORY-001.1-*.md` and `STORY-001.2-*.md` for the layered isolation contracts.
