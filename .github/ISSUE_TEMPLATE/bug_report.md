---
name: Bug report
about: Something is broken in claude-i
title: ""
labels: bug
assignees: ""
---

## Pre-flight checks

- [ ] I am running `claude-i 0.2.2` or later (`claude-i --version`).
- [ ] `claude-i doctor` reports all 5 checks PASS (or I've included the FAIL output below).
- [ ] If this is an intermittent failure under automation, I've tried `claude-i --retries 3 "<prompt>"` (Bug 5 mitigation per NOTES.md).
- [ ] I've searched existing issues at https://github.com/rafaelscosta/claude-i/issues and confirmed this is not a duplicate.

## What happened

<!-- One short paragraph. Include the command you ran and what you expected vs. what you got. -->

## Minimal reproduction

```bash
# Paste the smallest sequence of commands that reproduces the bug.
```

## Environment

- claude-i: <!-- paste the output of `claude-i --version` -->
- claude (Claude Code CLI): <!-- paste the output of `claude --version` -->
- tmux: <!-- `tmux -V` -->
- OS: <!-- macOS 25.5.0 / Ubuntu 24.04 / etc. -->
- Python: <!-- `python3 --version` -->
- Install path: <!-- brew / pipx wheel / pipx git tag / sdist -->

## `claude-i doctor` output

```
<!-- paste `claude-i doctor` or `claude-i doctor --json` here -->
```

## `claude-i --verbose` output (if relevant)

```
<!-- paste relevant stderr/stdout from running with --verbose -->
```

## Additional context

<!-- Any other context, log snippets, or screenshots that might help. -->
