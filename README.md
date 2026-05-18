# claude-i

Like `claude -p`, but driven through an interactive Claude Code session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins); `claude -p` is headless and skips a lot of it. `claude-i` bridges the two: it scripts an interactive session inside a headless `tmux`, captures the final assistant message via a gated Stop hook, and tears down the process tree on exit.

## Status

Bootstrapping. See `docs/epics/EPIC-001-packaging-and-hardening.md` for full scope.

## Install

claude-i is currently a **private repository** — install paths require read access (be added as a collaborator, or have a PAT with `repo` scope).

> Native Windows is not supported in v0.2.0; use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install). The `claude-i` CLI emits `PLATFORM_ERROR=3` on `sys.platform == "win32"` (G9 platform guard, STORY-001.2).

### Option 1 — pipx + git (recommended)

```bash
pipx install git+https://github.com/rafaelscosta/claude-i.git@v0.2.0
```

Requires `gh auth login` or a `GH_TOKEN`/`GITHUB_TOKEN` env var with read access to the repo.

### Option 2 — GitHub Release wheel

```bash
gh release download v0.2.0 --pattern '*.whl' -R rafaelscosta/claude-i
pipx install ./claude_i-0.2.0-py3-none-any.whl
```

### Option 3 — sdist (uv-compatible)

```bash
gh release download v0.2.0 --pattern '*.tar.gz' -R rafaelscosta/claude-i
uv tool install ./claude_i-0.2.0.tar.gz
# or: pipx install ./claude_i-0.2.0.tar.gz
```

### Verify

```bash
claude-i --version    # → claude-i 0.2.0
claude-i doctor       # self-diagnostic
```

### Artifact checksums (v0.2.0)

- `claude_i-0.2.0-py3-none-any.whl` — SHA256 `ee6a455efd90b279114eb460030d9c96ac83a0119b39621ae837b3c709268e10`
- `claude_i-0.2.0.tar.gz` — SHA256 `28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353`

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
