# claude-i

Like `claude -p`, but driven through an interactive Claude Code session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins); `claude -p` is headless and skips a lot of it. `claude-i` bridges the two: it scripts an interactive session inside a headless `tmux`, captures the final assistant message via a gated Stop hook, and tears down the process tree on exit.

## Status

**v0.2.4** — production-ready for both interactive use and non-interactive automation. This release includes the v0.2.3 long-prompt / `@agent` / slash-skill fixes, late Stop-hook artifact cleanup, clearer Bug 5 retry guidance, and Node 24-ready CI/release infrastructure.

## Install

> Native Windows is not supported; use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install). The `claude-i` CLI emits `PLATFORM_ERROR=3` on `sys.platform == "win32"` (G9 platform guard, STORY-001.2).

### Option 1 — PyPI (recommended)

```bash
pipx install claude-i
# or: uv tool install claude-i
```

### Option 2 — Homebrew (macOS / Linux)

```bash
brew tap rafaelscosta/claude-i
brew install claude-i
```

### Option 3 — pipx + GitHub Release

```bash
pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.4/claude_i-0.2.4-py3-none-any.whl
```

### Option 4 — pipx + git tag

```bash
pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.4
```

### Option 5 — sdist (uv-compatible)

```bash
pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.4/claude_i-0.2.4.tar.gz
# or: uv tool install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.4/claude_i-0.2.4.tar.gz
```

### Verify

```bash
claude-i --version    # → claude-i 0.2.4
claude-i doctor       # self-diagnostic — should report 5/5 PASS
```

### Artifact checksums

Checksums are published with the GitHub Release assets. For local verification:

```bash
shasum -a 256 claude_i-0.2.4-py3-none-any.whl claude_i-0.2.4.tar.gz
```

## Usage

### Interactive (single-shot)

```bash
claude-i "What is 2+2?"
# → 4
```

### Non-interactive automation / CI / scripts

Use `--retries N` to absorb the upstream Anthropic-side burst-load session hang (Bug 5 in NOTES.md):

```bash
claude-i --retries 3 "<prompt>"
```

The runner spawns a fresh tmux session on each retry. Recommended:

| Use case | Invocation |
|---|---|
| Interactive single-shot | `claude-i "<prompt>"` |
| Automation / CI scripts | `claude-i --retries 3 "<prompt>"` |
| High-burst pipeline | `claude-i --retries 5 "<prompt>"` + 2s sleep between calls |

If the final stderr contains `No Stop hook signal`, the CLI now classifies it
as the documented Bug 5 environmental/upstream hang and suggests the retry
level above. Run `claude-i doctor` first; if doctor is green, treat the timeout
as host/upstream saturation rather than a payload parsing regression.

### Script-friendly first run

On the very first invocation, `claude-i` prompts to install its Stop hook. In a non-TTY context (CI, redirected stdin) this would normally fail with `EOFError`. Opt into auto-install:

```bash
export CLAUDE_I_AUTO_INSTALL_HOOK=1
claude-i --retries 3 "<prompt>"
```

### JSON output

```bash
claude-i --output-format json --retries 3 "<prompt>"
# → {"text": "...", "cost_usd": null, "tokens_in": null, "tokens_out": null, "duration_ms": 4231}
```

### Subcommands

```bash
claude-i doctor                  # self-diagnostic (5 checks; --json for machine-readable)
claude-i uninstall               # remove the Stop hook from settings.json
claude-i reap                    # kill orphaned claude-i-* tmux sessions
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Runtime error (timeout, parse failure, doctor FAIL, all retries exhausted) |
| 2 | Missing dependency or config error |
| 3 | Unsupported platform (native Windows; use WSL2) |

## Distribution Status

v0.2.4 (2026-06-10) is the current public release. v0.2.3 fixed long prompts, agent/slash-skill invocation, and title/SKIP misattribution; v0.2.4 adds the final PyPI release hygiene and environmental hardening.

| Path | Status |
|---|---|
| Repository (PUBLIC) | ✓ active |
| GitHub Release (wheel + sdist) | ✓ active |
| Homebrew tap (`rafaelscosta/claude-i`) | ✓ active |
| PyPI (`pipx install claude-i`) | ✓ active |
| `install.sh` bootstrap (`curl | sh`) | macOS uses Homebrew; Linux direct PyPI path available after first PyPI publish; `--local` supported |

The `install.sh` script lives at the repo root and supports `--local <path>` mode using artifacts downloaded from a GitHub Release. See [`docs/guides/homebrew-tap.md`](docs/guides/homebrew-tap.md) for detailed bootstrap docs.

## Origin

Forked from [gist isingh/62bdfd0886b0b72bf6231c44f0389ecc](https://gist.github.com/isingh/62bdfd0886b0b72bf6231c44f0389ecc). Original single-file script preserved in `seed/claude-i` for traceability.

## License

MIT — see `LICENSE`.
