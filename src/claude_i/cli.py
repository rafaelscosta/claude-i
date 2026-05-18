"""argparse entry point for claude-i.

Thin wiring layer over ``hook``, ``runner``, ``deps``, and ``reaper``. The
``--version`` flag uses argparse's native ``action="version"`` recipe so it
short-circuits BEFORE ``parse_args`` returns and BEFORE ``ensure_hook`` runs.
This is the safety contract for CI (which cannot answer ``ensure_hook``'s
``y/N`` prompt).

Subcommands ``doctor`` / ``uninstall`` / ``reap`` are placeholders here —
full implementations land in STORY-001.5.
"""

from __future__ import annotations

import argparse
from importlib.metadata import version as _pkg_version

from claude_i import hook, runner


def _version_string() -> str:
    """Read the installed package version from metadata.

    Falls back to the in-tree ``__version__`` if the package is not installed
    (e.g. running directly from a checkout without ``pip install -e .``).
    Argparse will prefix this with ``%(prog)s `` to produce ``claude-i X.Y.Z``.
    """
    try:
        return _pkg_version("claude-i")
    except Exception:
        # Best-effort fallback when running from a non-installed checkout.
        from claude_i import __version__ as fallback

        return fallback


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="claude-i",
        description=(
            "claude-i: like `claude -p`, but driven through an interactive "
            "Claude session."
        ),
    )
    # CRITICAL: action="version" handles --version BEFORE parse_args returns,
    # so ensure_hook() never runs on a --version invocation. Format string
    # uses %(prog)s so the output is exactly "claude-i <version>".
    ap.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_version_string()}",
    )
    ap.add_argument("prompt")
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="tail the tmux pane to stderr (debug hangs)",
    )
    ap.add_argument(
        "--ready-wait",
        type=float,
        default=4.0,
        help="seconds to let the TUI start before sending prompt",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="seconds to wait for Stop hook before failing",
    )
    ap.add_argument(
        "extra",
        nargs=argparse.REMAINDER,
        help="extra args forwarded to claude",
    )
    return ap


def main() -> None:
    """Entry point registered as ``claude-i`` in ``pyproject.toml``."""
    parser = _build_parser()
    # argparse short-circuits on --version here, exiting before parse_args()
    # returns. ensure_hook() must NEVER run before this line.
    args = parser.parse_args()

    hook.ensure_hook()
    print(
        runner.run(
            args.prompt,
            args.extra,
            args.verbose,
            args.ready_wait,
            args.timeout,
        )
    )


# --- Subcommand placeholders (full implementations in STORY-001.5) ---


def doctor() -> None:
    """``claude-i doctor`` — runtime self-diagnostic. Placeholder."""
    raise NotImplementedError("`claude-i doctor` lands in STORY-001.5 (gap G16)")


def uninstall() -> None:
    """``claude-i uninstall`` — remove Stop hook from settings. Placeholder."""
    raise NotImplementedError("`claude-i uninstall` lands in STORY-001.5 (gap G16)")


def reap() -> None:
    """``claude-i reap`` — kill orphaned tmux sessions. Placeholder."""
    raise NotImplementedError("`claude-i reap` lands in STORY-001.5 (gap G15)")


if __name__ == "__main__":
    main()
