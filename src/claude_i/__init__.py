"""claude-i: like `claude -p`, but driven through an interactive Claude session.

The interactive `claude` CLI loads everything (hooks, MCPs, skills, plugins);
`claude -p` is headless and skips a lot of it. ``claude-i`` bridges the two:
it scripts an interactive session inside a headless ``tmux``, captures the
final assistant message via a gated Stop hook, and tears down the process
tree on exit.
"""

__version__ = "0.2.4"

__all__ = ["__version__"]
