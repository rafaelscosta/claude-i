# claude-i

Like `claude -p`, but driven through an interactive Claude Code session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins); `claude -p` is headless and skips a lot of it. `claude-i` bridges the two: it scripts an interactive session inside a headless `tmux`, captures the final assistant message via a gated Stop hook, and tears down the process tree on exit.

## Status

Bootstrapping. See `docs/epics/EPIC-001-packaging-and-hardening.md` for full scope.

## Install

```bash
# PyPI via pipx (recommended)
pipx install claude-i

# PyPI via uv tool
uv tool install claude-i
```

Homebrew formula and `curl | bash` bootstrap installer land in STORY-001.4 (full install matrix tracked there).

## Origin

Forked from [gist isingh/62bdfd0886b0b72bf6231c44f0389ecc](https://gist.github.com/isingh/62bdfd0886b0b72bf6231c44f0389ecc). Original single-file script preserved in `seed/claude-i` for traceability.

## License

MIT — see `LICENSE`.
