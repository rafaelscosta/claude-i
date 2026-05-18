"""Cleanup and signal-handler registration.

Stubs for STORY-001.0. The full ``atexit`` + signal-handler implementation
lands in STORY-001.2 (gap G6). The stubs here exist so ``cli.py`` and tests
can import a stable surface without breaking when the implementation lands.
"""

from __future__ import annotations


def reap_orphans() -> int:
    """Kill orphaned ``claude-i-*`` tmux sessions and return the count killed.

    Stub: returns ``0`` until STORY-001.2 wires it to ``tmux ls`` and
    ``tmux kill-session``.
    """
    return 0


def register_cleanup(session: str) -> None:
    """Register an ``atexit`` + signal handler to tear down ``session``.

    Stub: no-op until STORY-001.2 implements the SIGTERM / SIGINT handlers.
    The parameter shape stays stable so downstream callers in ``runner.py``
    do not need to change when the implementation lands.
    """
    del session  # unused — preserved for forward-compat signature stability
