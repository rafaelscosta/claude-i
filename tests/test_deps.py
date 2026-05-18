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


# STORY-001.2 / Task 3.6 / Gap G9 — Windows platform guard.


def test_windows_guard_exits_3(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """On native Windows (``sys.platform == "win32"``), exit with code 3.

    The seed's stub used ``startswith("win")``, exited with code 1, and
    had the wrong message. G9 fixes all three: strict equality to
    ``"win32"``, exit code 3 (PLATFORM_ERROR), and the AC-5 verbatim
    message including the WSL2 docs URL.
    """
    monkeypatch.setattr(deps.sys, "platform", "win32")
    with pytest.raises(SystemExit) as exc:
        deps.assert_not_windows()
    assert exc.value.code == 3, (
        f"native Windows must exit PLATFORM_ERROR (3); got {exc.value.code}"
    )
    err = capsys.readouterr().err
    assert "requires Linux or macOS" in err
    assert "WSL2" in err
    assert "https://docs.microsoft.com/windows/wsl/" in err


def test_windows_guard_allows_wsl2(monkeypatch: pytest.MonkeyPatch) -> None:
    """WSL2 reports ``sys.platform == "linux"`` — must NOT trigger the guard."""
    monkeypatch.setattr(deps.sys, "platform", "linux")
    # Must not raise.
    deps.assert_not_windows()


def test_windows_guard_allows_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    """macOS (``darwin``) passes the guard."""
    monkeypatch.setattr(deps.sys, "platform", "darwin")
    deps.assert_not_windows()


def test_check_deps_runs_windows_guard_first(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """``check_deps`` calls ``assert_not_windows`` BEFORE the shutil.which probes.

    Stubs ``sys.platform = "win32"`` and asserts:
    1. ``shutil.which`` was never called (guard short-circuited).
    2. Exit code is 3 (PLATFORM_ERROR), not 2 (CONFIG_ERROR).
    """
    monkeypatch.setattr(deps.sys, "platform", "win32")
    which_calls: list[str] = []

    def fake_which(name: str) -> None:
        which_calls.append(name)
        return None

    monkeypatch.setattr(deps.shutil, "which", fake_which)

    with pytest.raises(SystemExit) as exc:
        deps.check_deps()
    assert exc.value.code == 3, (
        "Windows guard must fire BEFORE shutil.which checks"
    )
    assert which_calls == [], (
        f"shutil.which must not be called on Windows; got: {which_calls}"
    )
    assert "WSL2" in capsys.readouterr().err
