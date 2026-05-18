"""Unit tests for ``claude_i.hook``.

STORY-001.1 / G2 — Tasks 2.6 / 2.7:

- ``hook_installed()`` does a structural check (type + command), not just a
  loose substring compare. Catches legacy / malformed entries.
- ``install_hook()`` preserves pre-existing ``Stop`` hooks from other tools
  (append-only).

All tests use ``monkeypatch`` to redirect ``claude_i.settings.SETTINGS`` (and
the imported alias in ``claude_i.hook``) to a temporary file so the user's
real ``~/.claude/settings.json`` is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_i import hook, settings


def _redirect_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``settings.SETTINGS`` to a tmp file. Returns the new path."""
    target = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "SETTINGS", target)
    # ``hook`` imported ``SETTINGS`` at module load; rebind that name too.
    monkeypatch.setattr(hook, "SETTINGS", target)
    return target


def test_hook_installed_returns_false_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No settings file → ``hook_installed`` returns False, never raises."""
    _redirect_settings(tmp_path, monkeypatch)
    assert hook.hook_installed() is False


def test_hook_installed_returns_false_on_malformed_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed JSON → ``hook_installed`` returns False, never raises."""
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text("{not: valid json")
    assert hook.hook_installed() is False


def test_hook_installed_detects_correct_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A settings file with a well-formed claude-i hook returns True."""
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {"hooks": [{"type": "command", "command": settings.HOOK_CMD}]}
                    ]
                }
            }
        )
    )
    assert hook.hook_installed() is True


def test_hook_installed_detects_legacy_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A legacy entry with the right command but wrong type returns False.

    The seed's check (``command == HOOK_CMD`` only) would falsely report
    True here. The hardened check requires ``type == "command"`` too.
    """
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        # Legacy entry: right command, wrong type (e.g. someone
                        # pasted the command into an http entry by mistake).
                        {"hooks": [{"type": "http", "command": settings.HOOK_CMD}]}
                    ]
                }
            }
        )
    )
    assert hook.hook_installed() is False


def test_hook_installed_ignores_unrelated_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A settings file with OTHER Stop hooks but no claude-i hook → False."""
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {
                                    "type": "http",
                                    "url": "http://localhost:7483/hooks/stop",
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    assert hook.hook_installed() is False


def test_install_hook_creates_settings_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install_hook`` creates a fresh settings.json with the hook entry."""
    target = _redirect_settings(tmp_path, monkeypatch)
    assert not target.exists()
    hook.install_hook()
    assert target.exists()
    cfg = json.loads(target.read_text())
    assert cfg["hooks"]["Stop"][0]["hooks"][0]["command"] == settings.HOOK_CMD
    assert cfg["hooks"]["Stop"][0]["hooks"][0]["type"] == "command"


def test_install_hook_preserves_existing_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-existing Stop hooks survive ``install_hook`` (Task 2.7)."""
    target = _redirect_settings(tmp_path, monkeypatch)
    pre_existing = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "http",
                            "url": "http://localhost:7483/hooks/stop",
                            "timeout": 5,
                        }
                    ]
                }
            ]
        }
    }
    target.write_text(json.dumps(pre_existing))

    hook.install_hook()
    cfg = json.loads(target.read_text())
    stop_list = cfg["hooks"]["Stop"]
    # Both the pre-existing entry AND the new claude-i entry must be present.
    assert len(stop_list) == 2
    http_entries = [
        h
        for g in stop_list
        for h in g.get("hooks", [])
        if h.get("type") == "http"
    ]
    command_entries = [
        h
        for g in stop_list
        for h in g.get("hooks", [])
        if h.get("type") == "command" and h.get("command") == settings.HOOK_CMD
    ]
    assert len(http_entries) == 1, "pre-existing http hook lost on install"
    assert len(command_entries) == 1, "claude-i hook not added"


def test_install_hook_refuses_malformed_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``install_hook`` exits with CONFIG_ERROR (2) on malformed settings.json.

    STORY-001.2 G8 / Task 3.8: this migrated from a string-form ``sys.exit``
    (exit code 1) to a named constant ``CONFIG_ERROR`` (exit code 2). The
    1→2 change is the intended semantic correction — malformed settings IS
    a config error, not a runtime error. The error message moves from the
    SystemExit message field to stderr.
    """
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text("{not: json")
    with pytest.raises(SystemExit) as exc:
        hook.install_hook()
    assert exc.value.code == 2, (
        f"malformed JSON must exit CONFIG_ERROR (2); got {exc.value.code}"
    )
    captured = capsys.readouterr()
    assert "not valid JSON" in captured.err


def test_install_then_detect_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: install_hook then hook_installed returns True."""
    _redirect_settings(tmp_path, monkeypatch)
    assert hook.hook_installed() is False
    hook.install_hook()
    assert hook.hook_installed() is True


# STORY-001.2 / Task 3.4 / Gap G7 — fcntl.flock on install_hook mutation.


def test_install_hook_acquires_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install_hook`` calls ``fcntl.flock`` with ``LOCK_EX`` before writing."""
    import fcntl as real_fcntl

    _redirect_settings(tmp_path, monkeypatch)
    flock_calls: list[tuple[int, int]] = []

    real_flock = real_fcntl.flock

    def fake_flock(fd: int, op: int) -> None:
        flock_calls.append((fd, op))
        # Delegate to real flock so the lock actually works.
        real_flock(fd, op)

    monkeypatch.setattr(hook.fcntl, "flock", fake_flock)
    hook.install_hook()

    # Expect at least one LOCK_EX|LOCK_NB (acquire) and one LOCK_UN (release).
    ops = [op for _fd, op in flock_calls]
    assert real_fcntl.LOCK_EX | real_fcntl.LOCK_NB in ops, (
        f"install_hook must acquire flock with LOCK_EX|LOCK_NB; got ops: {ops}"
    )
    assert real_fcntl.LOCK_UN in ops, (
        f"install_hook must release flock with LOCK_UN; got ops: {ops}"
    )


def test_install_hook_creates_lock_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install_hook`` creates the sibling ``claude-i.lock`` file."""
    target = _redirect_settings(tmp_path, monkeypatch)
    hook.install_hook()
    lock_file = target.parent / "claude-i.lock"
    assert lock_file.exists(), (
        "install_hook must create a sibling claude-i.lock for advisory locking"
    )


def test_install_hook_exits_on_lock_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install_hook`` exits with code 1 when the lock cannot be acquired.

    Simulates contention by stubbing ``fcntl.flock`` to always raise
    ``BlockingIOError``. The retry loop hits its deadline (shortened to
    10ms for the test) and ``sys.exit(1)`` fires.
    """
    _redirect_settings(tmp_path, monkeypatch)

    def always_blocked(_fd: int, _op: int) -> None:
        raise BlockingIOError("EWOULDBLOCK")

    monkeypatch.setattr(hook.fcntl, "flock", always_blocked)
    monkeypatch.setattr(hook, "_LOCK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(hook, "_LOCK_RETRY_INTERVAL", 0.005)

    with pytest.raises(SystemExit) as exc:
        hook.install_hook()
    assert exc.value.code == 1


def test_install_hook_preserves_existing_hooks_with_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G7 regression: locking does not break the G2/Task 2.7 append behavior."""
    target = _redirect_settings(tmp_path, monkeypatch)
    pre_existing = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "http",
                            "url": "http://localhost:7483/hooks/stop",
                        }
                    ]
                }
            ]
        }
    }
    target.write_text(json.dumps(pre_existing))
    hook.install_hook()
    cfg = json.loads(target.read_text())
    # Both entries survive — same assertion as test_install_hook_preserves_existing_hooks.
    stop_list = cfg["hooks"]["Stop"]
    assert len(stop_list) == 2
