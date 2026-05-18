"""Unit tests for ``claude_i.deps``.

Covers STORY-001.1 gap G3: ``check_deps`` exits with code ``2`` when ``tmux``
or ``claude`` is missing, with OS-specific install hints.

All tests are pure mocks — no real ``tmux`` / ``claude`` invoked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from claude_i import deps


def _which_factory(present: set[str]) -> Any:
    """Return a ``shutil.which`` replacement that maps ``present`` → path."""

    def fake_which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in present else None

    return fake_which


def test_missing_tmux_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    """``check_deps`` exits with code 2 and a hint when ``tmux`` is absent."""
    with patch.object(deps.shutil, "which", _which_factory(set())):
        with pytest.raises(SystemExit) as exc:
            deps.check_deps()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "tmux" in captured.err
    assert "Install tmux" in captured.err


def test_missing_claude_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    """``check_deps`` exits 2 when only ``claude`` is missing.

    The ``claude`` branch is only reached when ``tmux`` is present, so the
    fake ``which`` declares tmux available.
    """
    with patch.object(deps.shutil, "which", _which_factory({"tmux"})):
        with pytest.raises(SystemExit) as exc:
            deps.check_deps()
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "claude" in captured.err
    assert deps.CLAUDE_INSTALL_URL in captured.err


def test_both_present_no_exit() -> None:
    """When both binaries are on PATH, ``check_deps`` returns without exiting."""
    with patch.object(deps.shutil, "which", _which_factory({"tmux", "claude"})):
        # Should not raise.
        deps.check_deps()


def test_tmux_hint_macos() -> None:
    """On macOS the hint mentions ``brew``."""
    with patch.object(deps.platform, "system", return_value="Darwin"):
        hint = deps._tmux_install_hint()
    assert "brew install tmux" in hint


def test_tmux_hint_ubuntu(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """An ``ID=ubuntu`` ``/etc/os-release`` produces an ``apt`` hint."""
    fake_release = tmp_path / "os-release"
    fake_release.write_text('ID=ubuntu\nID_LIKE=debian\nNAME="Ubuntu"\n')
    monkeypatch.setattr(deps, "_OS_RELEASE_PATH", fake_release)
    with patch.object(deps.platform, "system", return_value="Linux"):
        hint = deps._tmux_install_hint()
    assert "apt install tmux" in hint


def test_tmux_hint_fedora(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """An ``ID=fedora`` ``/etc/os-release`` produces a ``dnf`` hint."""
    fake_release = tmp_path / "os-release"
    fake_release.write_text('ID=fedora\nID_LIKE="rhel centos"\nNAME="Fedora"\n')
    monkeypatch.setattr(deps, "_OS_RELEASE_PATH", fake_release)
    with patch.object(deps.platform, "system", return_value="Linux"):
        hint = deps._tmux_install_hint()
    assert "dnf install tmux" in hint


def test_tmux_hint_generic_fallback(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrecognized distro falls back to the generic message."""
    fake_release = tmp_path / "os-release"
    fake_release.write_text('ID=arch\nNAME="Arch Linux"\n')
    monkeypatch.setattr(deps, "_OS_RELEASE_PATH", fake_release)
    with patch.object(deps.platform, "system", return_value="Linux"):
        hint = deps._tmux_install_hint()
    assert "package manager" in hint


def test_tmux_hint_no_os_release(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing ``/etc/os-release`` does not crash; falls back to generic."""
    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr(deps, "_OS_RELEASE_PATH", missing)
    with patch.object(deps.platform, "system", return_value="Linux"):
        hint = deps._tmux_install_hint()
    assert "package manager" in hint
