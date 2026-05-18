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

from claude_i import deps, hook, runner


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
        # AC-8 / Task 2.8 — document exit codes in --help output. The epilog
        # renders verbatim after the standard options block.
        epilog=(
            "Exit codes:\n"
            "  0  success\n"
            "  1  runtime error (timeout, parse failure)\n"
            "  2  missing dependency or config error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    # AC-1 / Task 2.3 — G1: forward a safe permission mode to the sub-claude
    # by default. ``acceptEdits`` skips the per-edit permission prompt but
    # does not bypass all safety checks. The value is passed through verbatim
    # to ``claude --permission-mode <mode>``; ``claude`` validates the choice.
    ap.add_argument(
        "--permission-mode",
        default="acceptEdits",
        metavar="MODE",
        help=(
            "Claude permission mode forwarded to the sub-claude "
            "(default: acceptEdits). Common values: acceptEdits, auto, "
            "bypassPermissions, default, plan."
        ),
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

    # AC-7 / Task 2.2 — verify external binaries BEFORE prompting the user to
    # install the Stop hook. A missing-dep failure should surface immediately
    # rather than after the user has answered the ``y/N`` install prompt.
    deps.check_deps()
    hook.ensure_hook()
    # AC-1 / Task 2.3 — prepend ``--permission-mode <mode>`` to extra args so
    # ``runner.run`` forwards it to the sub-claude. Listed BEFORE user-supplied
    # extras so the user can still override by passing their own
    # ``--permission-mode`` later (claude's CLI parser takes the last
    # occurrence).
    extra_args = ["--permission-mode", args.permission_mode, *args.extra]
    print(
        runner.run(
            args.prompt,
            extra_args,
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
