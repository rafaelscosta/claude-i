"""Unit tests for ``claude_i.reaper``.

STORY-001.2 / Task 3.2 / Gap G6 — cleanup infrastructure.

- ``register_cleanup`` wires up an ``atexit`` handler + ``SIGTERM`` handler.
- The ``atexit`` handler invokes ``tmux kill-session -t <session>``.
- Registration is idempotent — repeated calls do not stack handlers.
- ``reap_orphans`` scans ``tmux ls`` output and kills sessions whose owning
  PID is gone.
"""

from __future__ import annotations

import signal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from claude_i import reaper


@pytest.fixture(autouse=True)
def _reset_reaper_state() -> Any:
    """Reset the module-level state between tests.

    ``reaper`` keeps process-wide state (``_session_to_cleanup``,
    ``_registered``). Without a reset, tests bleed into each other and order
    becomes load-bearing.
    """
    reaper._session_to_cleanup = None
    reaper._registered = False
    yield
    reaper._session_to_cleanup = None
    reaper._registered = False


def test_register_cleanup_sets_session_name() -> None:
    """``register_cleanup`` stores the session for later teardown."""
    with patch.object(reaper, "atexit") as _ae, patch.object(reaper.signal, "signal"):
        reaper.register_cleanup("claude-i-12345")
    assert reaper._session_to_cleanup == "claude-i-12345"
    assert reaper._registered is True


def test_register_cleanup_calls_tmux_on_atexit() -> None:
    """The atexit handler invokes ``tmux kill-session -t <session>``."""
    reaper._session_to_cleanup = "claude-i-99999"
    with patch.object(reaper, "subprocess") as sub:
        sub.run = MagicMock(return_value=MagicMock(returncode=0, stdout=""))
        reaper._atexit_handler()
        sub.run.assert_called_once()
        argv = sub.run.call_args.args[0]
        assert argv == ["tmux", "kill-session", "-t", "claude-i-99999"]
        assert sub.run.call_args.kwargs.get("check") is False


def test_atexit_handler_noop_when_no_session() -> None:
    """The atexit handler is a no-op when no session was registered."""
    reaper._session_to_cleanup = None
    with patch.object(reaper, "subprocess") as sub:
        sub.run = MagicMock()
        reaper._atexit_handler()
        sub.run.assert_not_called()


def test_atexit_handler_swallows_exceptions() -> None:
    """The atexit handler never raises — we may already be exiting."""
    reaper._session_to_cleanup = "claude-i-1"
    with patch.object(reaper, "subprocess") as sub:
        sub.run = MagicMock(side_effect=OSError("boom"))
        # Must NOT raise.
        reaper._atexit_handler()


def test_register_cleanup_is_idempotent() -> None:
    """Calling ``register_cleanup`` twice registers atexit / signal only once."""
    with (
        patch.object(reaper, "atexit") as ae,
        patch.object(reaper.signal, "signal") as sig,
    ):
        reaper.register_cleanup("claude-i-1")
        reaper.register_cleanup("claude-i-2")
        # atexit.register called once even though register_cleanup ran twice.
        assert ae.register.call_count == 1
        assert sig.call_count == 1
    # But the tracked session updates to the latest value.
    assert reaper._session_to_cleanup == "claude-i-2"


def test_sigterm_handler_calls_sys_exit() -> None:
    """The SIGTERM handler converts the signal to ``sys.exit(1)``.

    Without this, the default Python SIGTERM handler terminates without
    running atexit callbacks — defeating the purpose of registration.
    """
    with pytest.raises(SystemExit) as exc:
        reaper._sigterm_handler(signal.SIGTERM, None)
    assert exc.value.code == 1


def test_register_cleanup_installs_sigterm_handler() -> None:
    """``register_cleanup`` swaps the SIGTERM handler for ``_sigterm_handler``."""
    with patch.object(reaper.signal, "signal") as sig:
        reaper.register_cleanup("claude-i-7")
        sig.assert_called_once_with(signal.SIGTERM, reaper._sigterm_handler)


def test_reap_orphans_returns_zero_when_no_tmux() -> None:
    """When ``tmux ls`` returns non-zero, ``reap_orphans`` returns 0."""
    with patch.object(reaper, "subprocess") as sub:
        sub.run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        assert reaper.reap_orphans() == 0


def test_reap_orphans_skips_non_claude_i_sessions() -> None:
    """Sessions whose names don't start with ``claude-i-`` are ignored."""
    with patch.object(reaper, "subprocess") as sub:
        sub.run = MagicMock(
            return_value=MagicMock(returncode=0, stdout="other-session\nmain\n")
        )
        assert reaper.reap_orphans() == 0
        # Only the ls call — no kill-session calls.
        assert sub.run.call_count == 1


def test_reap_orphans_kills_dead_pid_sessions() -> None:
    """A ``claude-i-<pid>`` session whose PID is gone is killed and counted."""
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        calls.append(argv)
        if argv[:2] == ["tmux", "ls"]:
            return MagicMock(
                returncode=0, stdout="claude-i-99999\nclaude-i-not-an-int\n"
            )
        return MagicMock(returncode=0, stdout="")

    with (
        patch.object(reaper, "subprocess") as sub,
        patch.object(reaper, "_pid_alive", return_value=False),
    ):
        sub.run = MagicMock(side_effect=fake_run)
        killed = reaper.reap_orphans()
    assert killed == 1
    kill_calls = [c for c in calls if c[:2] == ["tmux", "kill-session"]]
    assert kill_calls == [["tmux", "kill-session", "-t", "claude-i-99999"]]


def test_reap_orphans_skips_live_pid_sessions() -> None:
    """A session whose PID is still alive is NOT killed."""
    with (
        patch.object(reaper, "subprocess") as sub,
        patch.object(reaper, "_pid_alive", return_value=True),
    ):
        sub.run = MagicMock(
            return_value=MagicMock(returncode=0, stdout="claude-i-12345\n")
        )
        killed = reaper.reap_orphans()
    assert killed == 0


def test_pid_alive_returns_false_for_dead_pid() -> None:
    """``_pid_alive`` returns False when ``os.kill`` raises ``ProcessLookupError``."""
    with patch("os.kill", side_effect=ProcessLookupError):
        assert reaper._pid_alive(999999) is False


def test_pid_alive_returns_true_for_live_pid() -> None:
    """``_pid_alive`` returns True when ``os.kill`` succeeds (signal 0)."""
    with patch("os.kill", return_value=None):
        assert reaper._pid_alive(1) is True


def test_pid_alive_returns_true_for_permission_error() -> None:
    """A PermissionError means the PID exists but is owned by someone else."""
    with patch("os.kill", side_effect=PermissionError):
        assert reaper._pid_alive(1) is True
