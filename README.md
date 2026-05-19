# claude-i

Like `claude -p`, but driven through an interactive Claude Code session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins); `claude -p` is headless and skips a lot of it. `claude-i` bridges the two: it scripts an interactive session inside a headless `tmux`, captures the final assistant message via a gated Stop hook, and tears down the process tree on exit.

## Status

**v0.2.2** — production-ready for both interactive use and non-interactive automation. See `docs/epics/EPIC-001-packaging-and-hardening.md` for full scope and `docs/stories/STORY-001.7-*.md` for the most recent changes.

## Install

claude-i is currently a **private repository** — install paths require read access (be added as a collaborator, or have a PAT with `repo` scope).

> Native Windows is not supported; use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install). The `claude-i` CLI emits `PLATFORM_ERROR=3` on `sys.platform == "win32"` (G9 platform guard, STORY-001.2).

### Option 1 — pipx + git tag (recommended)

```bash
pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.2
```

Requires `gh auth login` or a `GH_TOKEN`/`GITHUB_TOKEN` env var with read access to the repo.

### Option 2 — GitHub Release wheel

```bash
pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.2/claude_i-0.2.2-py3-none-any.whl
```

### Option 3 — sdist (uv-compatible)

```bash
pipx install https://github.com/rafaelscosta/claude-i/releases/download/v0.2.2/claude_i-0.2.2.tar.gz
# or: uv tool install ...
```

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

## Public Release (deferred)

The following paths land when the repo flips PUBLIC + PyPI Pending Publisher is configured:

- `pipx install claude-i` (PyPI)
- `uv tool install claude-i` (PyPI)
- `brew install rafaelscosta/claude-i/claude-i` (Homebrew tap)
- `curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh | sh`

See `NOTES.md` § "Private Distribution Phase" for the operator checklist to enable public release.

### Bootstrap script (`install.sh`) — currently for local use

The repo also ships `install.sh` at the root. While the repo is private, it is intended for local dev/testing (`--local <path>` mode using artifacts downloaded from a GitHub Release). Once public, it becomes the canonical one-liner via `curl | bash`. Documentation in [`docs/guides/homebrew-tap.md`](docs/guides/homebrew-tap.md).

## Origin

Forked from [gist isingh/62bdfd0886b0b72bf6231c44f0389ecc](https://gist.github.com/isingh/62bdfd0886b0b72bf6231c44f0389ecc). Original single-file script preserved in `seed/claude-i` for traceability.

## License

MIT — see `LICENSE`.
