# claude-i

Like `claude -p`, but driven through an interactive Claude Code session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins); `claude -p` is headless and skips a lot of it. `claude-i` bridges the two: it scripts an interactive session inside a headless `tmux`, captures the final assistant message via a gated Stop hook, and tears down the process tree on exit.

## Status

Bootstrapping. See `docs/epics/EPIC-001-packaging-and-hardening.md` for full scope.

## Install

| Method                | Command                                                                                          | Platforms        |
|-----------------------|--------------------------------------------------------------------------------------------------|------------------|
| Homebrew (recommended for macOS) | `brew install rafaelscosta/claude-i/claude-i`                                                    | macOS            |
| pipx                  | `pipx install claude-i`                                                                          | macOS, Linux     |
| uv tool               | `uv tool install claude-i`                                                                       | macOS, Linux     |
| One-line bootstrap    | `curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh \| bash`     | macOS, Linux     |

> Native Windows is not supported in v0.2.0; use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install). The `claude-i` CLI emits `PLATFORM_ERROR=3` on `sys.platform == "win32"` (G9 platform guard, STORY-001.2).

### Homebrew tap

The tap repository is [`rafaelscosta/homebrew-claude-i`](https://github.com/rafaelscosta/homebrew-claude-i). The formula declares `tmux` as a `depends_on`, so `brew install` ensures both binaries are present after a single command.

See [`docs/guides/homebrew-tap.md`](docs/guides/homebrew-tap.md) for tap details, dev-pass URL strategy, and the v0.2.0 epic-close finalization steps.

### One-line bootstrap (`install.sh`)

The bootstrap script at the repo root detects OS and package manager:

- **macOS** — tries the Homebrew tap first; falls back to `pipx install claude-i` if the tap is unreachable.
- **Ubuntu/Debian** — installs `tmux` via `apt`, bootstraps `pipx` (PEP 668-safe: distro package preferred, `python3 -m pip install --user pipx` as fallback), then `pipx install claude-i`.
- **Fedora/RHEL** — installs `tmux` via `dnf`, bootstraps `pipx` the same way, then `pipx install claude-i`.

Flags:

- `--dry-run` — print the commands that would run, but do not execute them.
- `--check` — exit 0 if `claude-i` is already installed and reachable; exit 2 otherwise.
- `--local <path>` — install from a local sdist/wheel path instead of PyPI (used by CI smoke and the v0.2.0 dev pass before PyPI publish).

After install, `pipx ensurepath` writes `~/.local/bin` into your shell-rc but does not reload the current shell. The script verifies the install via the explicit `$HOME/.local/bin/claude-i` path so `--version` works without restarting your shell. For fresh shells, run `source ~/.bashrc` (or equivalent) or open a new terminal.

### Security note (`curl | bash`)

The bootstrap URL `https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh` has no checksum at the curl layer — that risk is documented and accepted for v0.2.0 in [`docs/guides/homebrew-tap.md` § Security](docs/guides/homebrew-tap.md). The script itself does not verify a checksum of its own bytes. The wheel installed by `pipx install claude-i` is verified by `pip` against the PyPI manifest hash. The Homebrew formula provides `sha256` for the source artifact (AC-7).

## Origin

Forked from [gist isingh/62bdfd0886b0b72bf6231c44f0389ecc](https://gist.github.com/isingh/62bdfd0886b0b72bf6231c44f0389ecc). Original single-file script preserved in `seed/claude-i` for traceability.

## License

MIT — see `LICENSE`.
