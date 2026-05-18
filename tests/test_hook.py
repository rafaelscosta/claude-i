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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install_hook`` exits rather than corrupting a malformed settings file."""
    target = _redirect_settings(tmp_path, monkeypatch)
    target.write_text("{not: json")
    with pytest.raises(SystemExit) as exc:
        hook.install_hook()
    assert "not valid JSON" in str(exc.value)


def test_install_then_detect_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: install_hook then hook_installed returns True."""
    _redirect_settings(tmp_path, monkeypatch)
    assert hook.hook_installed() is False
    hook.install_hook()
    assert hook.hook_installed() is True
