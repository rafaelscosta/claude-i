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


# STORY-001.5 / Task 6.2 / Q-1 + Q-2 — remove_hook() unit tests.


def test_remove_hook_removes_only_claude_i_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``remove_hook`` drops claude-i leaves and preserves foreign hooks.

    Setup: settings.json with a claude-i Stop hook AND a foreign http Stop
    hook from another tool. Expected: after ``remove_hook()`` returns,
    the foreign http entry survives byte-identical and the claude-i entry
    is gone. Return value is the count of removed leaves (1).
    """
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
                },
                {
                    "hooks": [
                        {"type": "command", "command": settings.HOOK_CMD}
                    ]
                },
            ]
        }
    }
    target.write_text(json.dumps(pre_existing))

    removed = hook.remove_hook()
    assert removed == 1, f"expected 1 claude-i leaf removed; got {removed}"

    cfg = json.loads(target.read_text())
    stop_list = cfg["hooks"]["Stop"]
    # Foreign http hook must survive verbatim.
    http_entries = [
        leaf
        for group in stop_list
        for leaf in group.get("hooks", [])
        if isinstance(leaf, dict) and leaf.get("type") == "http"
    ]
    assert len(http_entries) == 1
    assert http_entries[0]["url"] == "http://localhost:7483/hooks/stop"
    # No claude-i command entries should remain.
    claude_entries = [
        leaf
        for group in stop_list
        for leaf in group.get("hooks", [])
        if isinstance(leaf, dict)
        and leaf.get("type") == "command"
        and leaf.get("command") == settings.HOOK_CMD
    ]
    assert claude_entries == [], (
        "remove_hook left a claude-i entry behind"
    )


def test_remove_hook_noop_when_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``remove_hook`` returns 0 without raising when no hook is installed.

    Covers two no-op shapes:
    1. settings.json does not exist (returns 0 immediately, no lock acquired).
    2. settings.json exists but has no Stop hooks (returns 0, file untouched).
    """
    target = _redirect_settings(tmp_path, monkeypatch)

    # Shape 1: file absent.
    assert not target.exists()
    assert hook.remove_hook() == 0

    # Shape 2: file present, no Stop hooks at all.
    target.write_text(json.dumps({"hooks": {}}))
    assert hook.remove_hook() == 0
    # File content must remain valid JSON with the original shape — we never
    # rewrite when removed == 0.
    cfg = json.loads(target.read_text())
    assert cfg == {"hooks": {}}


# STORY-001.5 / Task 6.7 / Q-1 (G14) — deferral marker test (AC-8 G14 portion).


def test_subagent_stop_deferred() -> None:
    """G14 deferral is documented in NOTES.md (AC-8 acknowledgement).

    AC-8 requires tests cover G14. The G14 investigation (Task 6.7) concluded
    that no distinct ``SubagentStop`` event is currently observable in
    claude-code 2.1.143's hook payload, so the implementation was deferred
    with a structured record in ``NOTES.md``. This test pins that record:
    if someone later removes the deferral section without implementing G14
    handling, this assertion fires and re-opens the gap.
    """
    notes_path = Path(__file__).parent.parent / "NOTES.md"
    assert notes_path.exists(), "NOTES.md is the G14 deferral record"
    content = notes_path.read_text()
    # Section header pins the deferral location (renames/reorgs trip this).
    assert "STORY-001.5 — G14 SubagentStop Deferred" in content, (
        "G14 deferral section header missing from NOTES.md"
    )
    # Keyword presence: SubagentStop is the deferred event name; DEFERRED is
    # the canonical status label used in NOTES.md headers.
    assert "SubagentStop" in content
    assert "DEFERRED" in content


# ---------------------------------------------------------------------------
# STORY-001.6 / Bug 1 — legacy v0.2.0 hook detection, atomic-rename writes,
# silent upgrade path
# ---------------------------------------------------------------------------


def test_hook_installed_detects_legacy_v020_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy v0.2.0 HOOK_CMD is recognised as installed (backwards compat).

    Upgrading users had the legacy single-step command written by an older
    ``install_hook``. ``hook_installed()`` must return True so they are NOT
    re-prompted; ``ensure_hook`` then triggers the silent upgrade path.
    """
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": settings.HOOK_CMD_LEGACY}
                            ]
                        }
                    ]
                }
            }
        )
    )
    assert hook.hook_installed() is True


def test_install_hook_writes_atomic_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install_hook`` always writes the atomic-rename HOOK_CMD, not the legacy form."""
    target = _redirect_settings(tmp_path, monkeypatch)
    hook.install_hook()
    cfg = json.loads(target.read_text())
    written_cmd = cfg["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert written_cmd == settings.HOOK_CMD, (
        "install_hook must write the current HOOK_CMD (atomic-rename form)"
    )
    assert written_cmd != settings.HOOK_CMD_LEGACY, (
        "install_hook must NOT write the legacy form"
    )
    # The atomic-rename form has 'mv' and '.json.tmp' as structural markers.
    assert "mv" in written_cmd
    assert ".json.tmp" in written_cmd


def test_remove_hook_removes_legacy_and_new(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``remove_hook`` removes BOTH HOOK_CMD and HOOK_CMD_LEGACY entries.

    A user who installed v0.2.0 and then v0.2.1 via the upgrade path should
    end up with only the new form (upgrade removes legacy first). But if
    settings.json was hand-edited or some other tool inserted both forms,
    ``claude-i uninstall`` should clean BOTH up.
    """
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": settings.HOOK_CMD_LEGACY},
                                {"type": "command", "command": settings.HOOK_CMD},
                            ]
                        }
                    ]
                }
            }
        )
    )
    removed = hook.remove_hook()
    assert removed == 2, f"both entries must be removed; got {removed}"


def test_only_legacy_hook_installed_distinguishes_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_only_legacy_hook_installed`` returns True iff legacy present AND new absent."""
    target = _redirect_settings(tmp_path, monkeypatch)

    # State 1: only legacy installed → True
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": settings.HOOK_CMD_LEGACY}
                            ]
                        }
                    ]
                }
            }
        )
    )
    assert hook._only_legacy_hook_installed() is True

    # State 2: only new installed → False
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": settings.HOOK_CMD}
                            ]
                        }
                    ]
                }
            }
        )
    )
    assert hook._only_legacy_hook_installed() is False

    # State 3: both installed → False (upgrade not needed; uninstall handles both)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": settings.HOOK_CMD_LEGACY},
                                {"type": "command", "command": settings.HOOK_CMD},
                            ]
                        }
                    ]
                }
            }
        )
    )
    assert hook._only_legacy_hook_installed() is False

    # State 4: neither installed → False
    target.write_text(json.dumps({"hooks": {"Stop": []}}))
    assert hook._only_legacy_hook_installed() is False


def test_ensure_hook_upgrades_silently_from_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A settings file with only the legacy hook triggers a silent upgrade.

    No ``input()`` is called (so no EOFError in non-TTY contexts). After
    ``ensure_hook`` returns, settings.json contains the NEW atomic-rename
    HOOK_CMD, not the legacy form. A stderr line documents the upgrade.
    """
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": settings.HOOK_CMD_LEGACY}
                            ]
                        }
                    ]
                }
            }
        )
    )

    # If input() were called, this would crash with EOFError — guarding it.
    def _fail_input(_prompt: str) -> str:
        raise AssertionError("ensure_hook must NOT prompt during legacy upgrade")

    monkeypatch.setattr("builtins.input", _fail_input)
    # Pretend stdin is not a TTY — to verify upgrade path bypasses TTY check
    # entirely (it should — the legacy upgrade happens via the hook_installed
    # short-circuit BEFORE the TTY guard).
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    hook.ensure_hook()

    # Settings now contain only the new HOOK_CMD.
    cfg = json.loads(target.read_text())
    leaves = cfg["hooks"]["Stop"][0]["hooks"]
    assert len(leaves) == 1
    assert leaves[0]["command"] == settings.HOOK_CMD
    # Stderr confirms the upgrade happened.
    captured = capsys.readouterr()
    assert "upgrading" in captured.err.lower()


def test_ensure_hook_no_tty_exits_with_helpful_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """STORY-001.6 / Bug 3 — non-TTY stdin without auto-install env var → exit 2.

    The seed crashed with ``EOFError: EOF when reading a line`` here. The fix
    exits with CONFIG_ERROR and prints a structured remediation message that
    names the env var explicitly so users know how to opt in.
    """
    _redirect_settings(tmp_path, monkeypatch)
    # No hook installed yet, stdin not a TTY, env var unset.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.delenv(hook.AUTO_INSTALL_ENV_VAR, raising=False)

    with pytest.raises(SystemExit) as exc:
        hook.ensure_hook()
    assert exc.value.code == 2, (
        f"non-TTY install must exit CONFIG_ERROR (2); got {exc.value.code}"
    )
    captured = capsys.readouterr()
    # Remediation message must name the env var so users know how to opt in.
    assert hook.AUTO_INSTALL_ENV_VAR in captured.err
    # Three remediation paths must be listed.
    assert "interactive" in captured.err.lower()
    assert "manually" in captured.err.lower()


def test_ensure_hook_no_tty_with_auto_install_env_var(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """STORY-001.6 / Bug 3 — ``CLAUDE_I_AUTO_INSTALL_HOOK=1`` auto-installs silently.

    Opt-in script-friendly path: when the env var is set and stdin is not a
    TTY, the hook is installed without prompting and ``ensure_hook`` returns
    normally. A stderr line documents the auto-install.
    """
    target = _redirect_settings(tmp_path, monkeypatch)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setenv(hook.AUTO_INSTALL_ENV_VAR, "1")

    # input() must NOT be called.
    def _fail_input(_prompt: str) -> str:
        raise AssertionError("ensure_hook must NOT prompt with auto-install env var")

    monkeypatch.setattr("builtins.input", _fail_input)

    hook.ensure_hook()

    # Hook should now be installed.
    assert hook.hook_installed() is True
    cfg = json.loads(target.read_text())
    assert cfg["hooks"]["Stop"][0]["hooks"][0]["command"] == settings.HOOK_CMD
    # Stderr documents the auto-install.
    captured = capsys.readouterr()
    assert "automatically" in captured.err.lower()
