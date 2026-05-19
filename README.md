# claude-i

Like `claude -p`, but driven through an interactive Claude Code session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins); `claude -p` is headless and skips a lot of it. `claude-i` bridges the two: it scripts an interactive session inside a headless `tmux`, captures the final assistant message via a gated Stop hook, and tears down the process tree on exit.

## Status

**v0.2.2** — production-ready for both interactive use and non-interactive automation. See `docs/epics/EPIC-001-packaging-and-hardening.md` for full scope and `docs/stories/STORY-001.7-*.md` for the most recent changes.

## Install

> Native Windows is not supported; use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install). The `claude-i` CLI emits `PLATFORM_ERROR=3` on `sys.platform == "win32"` (G9 platform guard, STORY-001.2).

### Option 1 — Homebrew (macOS / Linux, recommended)

```bash
brew tap rafaelscosta/claude-i
brew install claude-i
```

### Option 2 — pipx + GitHub Release

```bash
pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.2/claude_i-0.2.2-py3-none-any.whl
```

### Option 3 — pipx + git tag

```bash
pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.2
```

### Option 4 — sdist (uv-compatible)

```bash
pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.2/claude_i-0.2.2.tar.gz
# or: uv tool install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.2/claude_i-0.2.2.tar.gz
```

### PyPI (pending Trusted Publisher setup)

The `publish.yml` workflow is wired for PyPI Trusted Publishing via OIDC. Once a Pending Publisher is registered at https://pypi.org/manage/account/publishing/, the next dispatch lands `claude-i` on PyPI and enables `pipx install claude-i` / `uv tool install claude-i` directly. See `NOTES.md` § "IP Status — Public Release" for the operator setup steps.

### Verify

```bash
claude-i --version    # → claude-i 0.2.2
claude-i doctor       # self-diagnostic — should report 5/5 PASS
```

### Artifact checksums (v0.2.2)

- `claude_i-0.2.2-py3-none-any.whl` — SHA256 `97992abe632c2ae759378642f8353a861be7d3f84d932c6e0ba85234ed36933d`
- `claude_i-0.2.2.tar.gz` — SHA256 `f25d84f24916de2a8f6dc017169de71baea030b2b7e56a06e5e5a08e44719084`

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

v0.2.2 (2026-05-19) is the first public release after the IP-lock reversal documented in `NOTES.md` § "IP Status — Public Release".

| Path | Status |
|---|---|
| Repository (PUBLIC) | ✓ active |
| GitHub Release (wheel + sdist) | ✓ active |
| Homebrew tap (`rafaelscosta/claude-i`) | ✓ active |
| PyPI (`pip install claude-i`) | pending Trusted Publisher setup |
| `install.sh` bootstrap (`curl | sh`) | available for local testing; canonical one-liner pending |

The `install.sh` script lives at the repo root and supports `--local <path>` mode using artifacts downloaded from a GitHub Release. See [`docs/guides/homebrew-tap.md`](docs/guides/homebrew-tap.md) for detailed bootstrap docs.

## Origin

Forked from [gist isingh/62bdfd0886b0b72bf6231c44f0389ecc](https://gist.github.com/isingh/62bdfd0886b0b72bf6231c44f0389ecc). Original single-file script preserved in `seed/claude-i` for traceability.

## License

MIT — see `LICENSE`.
