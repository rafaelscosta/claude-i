"""Runtime dependency checks.

Stubs for STORY-001.0. Full implementations land in STORY-001.1 (gap G3 — dep
check) and STORY-001.2 (gap G9 — platform guard). Keep this module minimal so
the downstream stories can choose the final shape without conflict.
"""

from __future__ import annotations

import shutil
import sys

# External binaries that claude-i shells out to. The full list is the source
# of truth for STORY-001.1's ``check_deps`` implementation.
EXPECTED_BINARIES: tuple[str, ...] = ("tmux", "claude")


def check_deps() -> None:
    """Verify that every binary in ``EXPECTED_BINARIES`` is on ``$PATH``.

    Exits with a non-zero status and a per-OS install hint when a binary is
    missing. STORY-001.0 ships a minimal implementation that mirrors the
    seed's implicit contract (``tmux`` and ``claude`` must be present);
    STORY-001.1 will refine the error message with OS-specific hints
    (``apt`` / ``dnf`` / ``brew``).
    """
    missing = [b for b in EXPECTED_BINARIES if shutil.which(b) is None]
    if not missing:
        return
    names = ", ".join(missing)
    sys.exit(
        f"claude-i: required binary not found on PATH: {names}. "
        "Install tmux and the official `claude` CLI, then retry."
    )


def assert_not_windows() -> None:
    """Exit with a WSL2 hint when running on native Windows.

    Stub — STORY-001.2 implements the full platform guard (gap G9). For now
    this is a no-op everywhere; the function exists so downstream modules
    can import a stable symbol.
    """
    if sys.platform.startswith("win"):
        sys.exit(
            "claude-i does not support native Windows in v0.2.0. "
            "Use WSL2 (Ubuntu) instead."
        )
