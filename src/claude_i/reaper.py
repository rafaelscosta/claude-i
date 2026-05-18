"""Cleanup and signal-handler registration.

STORY-001.2 / Task 3.2 / Gap G6 — full implementation.

The seed already calls ``tmux kill-session`` inside the ``runner.run`` finally
block, but that does not survive:

- ``SIGKILL`` (cannot be intercepted by user-space — best-effort only)
- ``os._exit`` or similar abrupt termination
- Crashes that bypass the ``finally`` (rare, but possible)

``atexit`` + a ``SIGTERM`` handler that translates the signal into a normal
``sys.exit`` give us belt-and-suspenders cleanup for normal exits,
``KeyboardInterrupt``, and ``SIGTERM``. ``SIGKILL`` remains best-effort —
documented in ``--help``.

Idempotency: ``register_cleanup`` is safe to call multiple times. Only the
first call wires up ``atexit`` / ``signal``; subsequent calls just update the
session name.
"""

from __future__ import annotations

import atexit
import signal
import subprocess
import sys
from types import FrameType

# Module-level state — single session being tracked at a time. claude-i is a
# single-session CLI; if the model ever changes, this becomes a set[str].
_session_to_cleanup: str | None = None

# Idempotency flag — atexit / signal registration runs exactly once per
# process. Without this, repeated register_cleanup calls would register
# duplicate atexit handlers (which fire in reverse-registration order).
_registered: bool = False


def _atexit_handler() -> None:
    """Tear down the tracked tmux session on interpreter exit.

    Best-effort — failures are swallowed because we are already exiting.
    ``check=False`` suppresses ``CalledProcessError`` for already-dead
    sessions; ``capture_output=True`` keeps the cleanup silent.
    """
    if _session_to_cleanup is None:
        return
    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", _session_to_cleanup],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        # Cleanup never raises. We may be in the middle of an exception-driven
        # exit; raising here would mask the real error.
        pass


def _sigterm_handler(signum: int, frame: FrameType | None) -> None:
    """Translate ``SIGTERM`` into a normal exit so ``atexit`` fires.

    Without this, the default Python handler for ``SIGTERM`` terminates the
    interpreter without running ``atexit`` callbacks. We swap that for
    ``sys.exit(1)`` so the registered cleanup runs.

    ``signum`` and ``frame`` are mandatory per ``signal.signal`` contract but
    unused — we exit unconditionally.
    """
    del signum, frame  # unused
    sys.exit(1)


def register_cleanup(session: str) -> None:
    """Register an ``atexit`` + ``SIGTERM`` handler to tear down ``session``.

    Idempotent across calls — only the first call wires up handlers, but
    subsequent calls update the tracked session name (single-session model).
    """
    global _session_to_cleanup, _registered
    _session_to_cleanup = session
    if _registered:
        return
    atexit.register(_atexit_handler)
    # SIGTERM only — SIGINT is already handled by Python (raises
    # KeyboardInterrupt → finally blocks run → atexit fires). Reinstalling
    # would override that conversion and prevent finally blocks from running.
    signal.signal(signal.SIGTERM, _sigterm_handler)
    _registered = True


def reap_orphans() -> int:
    """Kill orphaned ``claude-i-*`` tmux sessions and return the count killed.

    Scans ``tmux ls`` output for session names matching ``claude-i-<pid>``,
    checks whether the owning PID is still alive, and kills any session whose
    PID is gone. Returns the number of sessions killed (0 if tmux not running
    or no orphans found).

    Best-effort — never raises. Used by ``claude-i reap`` (STORY-001.5) but
    landed here in 001.2 so the atexit infrastructure has a sibling reaper
    for ad-hoc cleanup.
    """
    try:
        result = subprocess.run(
            ["tmux", "ls", "-F", "#{session_name}"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return 0
    if result.returncode != 0:
        # tmux not running or no server — no sessions to reap.
        return 0
    killed = 0
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name.startswith("claude-i-"):
            continue
        pid_str = name[len("claude-i-"):]
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        if _pid_alive(pid):
            continue
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", name],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            killed += 1
        except Exception:
            continue
    return killed


def _pid_alive(pid: int) -> bool:
    """Return True when ``pid`` is alive (POSIX ``kill -0`` semantics)."""
    try:
        # Signal 0 is a no-op check — raises ProcessLookupError if pid is gone,
        # PermissionError if alive but owned by someone else (treated as alive).
        import os

        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
