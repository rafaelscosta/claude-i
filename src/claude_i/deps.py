"""Runtime dependency checks.

Implements gap G3: verify that required external binaries (``tmux`` and
``claude``) are on ``$PATH`` and emit OS-specific install hints when they are
not. Exits with code ``2`` on missing dependency (POSIX convention for misuse
of shell command / config error).

OS detection cascade:

1. ``platform.system() == "Darwin"`` → ``brew install tmux``
2. ``/etc/os-release`` ``ID`` or ``ID_LIKE`` is ``ubuntu`` / ``debian`` →
   ``sudo apt install tmux``
3. ``/etc/os-release`` ``ID`` or ``ID_LIKE`` is ``fedora`` / ``rhel`` /
   ``centos`` → ``sudo dnf install tmux``
4. Anything else → generic "install tmux via your system package manager".

STORY-001.2 will layer ``assert_not_windows`` on top of this (gap G9).
"""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path

from claude_i.exit_codes import CONFIG_ERROR, PLATFORM_ERROR

# External binaries that claude-i shells out to. The full list is the source
# of truth for ``check_deps``.
EXPECTED_BINARIES: tuple[str, ...] = ("tmux", "claude")

# Canonical install-docs URL for the official Claude Code CLI. Used in the
# missing-``claude`` hint. Stable enough to bake in; revisit if the docs move.
CLAUDE_INSTALL_URL: str = "https://docs.claude.com/en/docs/claude-code/setup"

# Path probed for Linux distribution identification (per
# https://www.freedesktop.org/software/systemd/man/os-release.html).
_OS_RELEASE_PATH: Path = Path("/etc/os-release")


def _parse_os_release(text: str) -> dict[str, str]:
    """Parse ``/etc/os-release`` content into a ``dict``.

    Each line is ``KEY=VALUE`` with optional double-quotes around VALUE. Lines
    that don't match are skipped silently — we never raise on a malformed
    ``os-release``.
    """
    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _linux_distro_ids() -> tuple[str, ...]:
    """Return ``(ID, ID_LIKE…)`` ids from ``/etc/os-release`` lowercased.

    Returns an empty tuple when the file is absent or unreadable. ``ID_LIKE``
    is space-separated per the spec — we split and flatten.
    """
    if not _OS_RELEASE_PATH.exists():
        return ()
    try:
        text = _OS_RELEASE_PATH.read_text()
    except OSError:
        return ()
    parsed = _parse_os_release(text)
    ids: list[str] = []
    primary = parsed.get("ID", "").lower()
    if primary:
        ids.append(primary)
    like = parsed.get("ID_LIKE", "").lower()
    if like:
        ids.extend(part for part in like.split() if part)
    return tuple(ids)


def _tmux_install_hint() -> str:
    """Return an OS-appropriate ``tmux`` install hint.

    macOS first, then Linux distro families via ``/etc/os-release``, then a
    generic fallback.
    """
    if platform.system() == "Darwin":
        return "Install tmux: brew install tmux"
    ids = _linux_distro_ids()
    if any(d in ids for d in ("ubuntu", "debian")):
        return "Install tmux: sudo apt install tmux"
    if any(d in ids for d in ("fedora", "rhel", "centos")):
        return "Install tmux: sudo dnf install tmux"
    return "Install tmux via your system package manager."


def _claude_install_hint() -> str:
    """Return the install hint for the official ``claude`` CLI."""
    return f"Install the official Claude Code CLI: {CLAUDE_INSTALL_URL}"


def check_deps() -> None:
    """Verify that every binary in ``EXPECTED_BINARIES`` is on ``$PATH``.

    Exits with ``CONFIG_ERROR`` (2) and prints an OS-specific install hint to
    stderr when a binary is missing. Order matters:

    - G9 — ``assert_not_windows()`` runs FIRST. On native Windows we exit
      with ``PLATFORM_ERROR`` (3) before probing for tmux/claude, since
      neither binary is available there.
    - ``tmux`` next — its install hint requires OS detection (apt / dnf /
      brew), so checking it before ``claude`` (single URL hint) keeps the
      decision tree shallow.
    """
    assert_not_windows()
    if shutil.which("tmux") is None:
        print(f"claude-i: tmux not found on PATH. {_tmux_install_hint()}", file=sys.stderr)
        sys.exit(CONFIG_ERROR)
    if shutil.which("claude") is None:
        print(
            f"claude-i: claude CLI not found on PATH. {_claude_install_hint()}",
            file=sys.stderr,
        )
        sys.exit(CONFIG_ERROR)


def assert_not_windows() -> None:
    """Exit with a WSL2 hint when running on native Windows.

    STORY-001.2 / Task 3.6 / Gap G9 — full implementation. ``sys.platform``
    on native Windows is the literal ``"win32"``. WSL2 reports ``"linux"``,
    so the strict equality check correctly allows WSL2 through.

    Exits with ``PLATFORM_ERROR`` (3), distinct from runtime/config errors,
    so monitoring tools can recognize "claude-i declined to run here"
    versus "claude-i ran and failed". The message is verbatim per AC-5.
    """
    if sys.platform == "win32":
        print(
            "claude-i requires Linux or macOS. On Windows, use WSL2: "
            "https://docs.microsoft.com/windows/wsl/",
            file=sys.stderr,
        )
        sys.exit(PLATFORM_ERROR)
