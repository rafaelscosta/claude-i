"""argparse entry point for claude-i.

Thin wiring layer over ``hook``, ``runner``, ``deps``, and ``reaper``. The
``--version`` flag uses argparse's native ``action="version"`` recipe so it
short-circuits BEFORE ``parse_args`` returns and BEFORE ``ensure_hook`` runs.
This is the safety contract for CI (which cannot answer ``ensure_hook``'s
``y/N`` prompt).

STORY-001.5 adds three subcommands: ``doctor`` (self-diagnostic),
``uninstall`` (remove Stop hook), ``reap`` (kill orphan tmux sessions).
The positional ``prompt`` is optional now — subcommands are dispatched via
``args.cmd`` BEFORE the main prompt flow, and the main flow rejects an empty
prompt explicitly with CONFIG_ERROR (2).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Any

from claude_i import deps, hook, reaper, runner
from claude_i.exit_codes import (
    CONFIG_ERROR,
    PLATFORM_ERROR,
    RUNTIME_ERROR,
    SUCCESS,
)
from claude_i.settings import SETTINGS, load_settings

# Re-export so test_cli.py can monkeypatch through the cli module if it wants.
__all__ = [
    "CONFIG_ERROR",
    "PLATFORM_ERROR",
    "RUNTIME_ERROR",
    "SUCCESS",
    "cmd_doctor",
    "cmd_reap",
    "cmd_uninstall",
    "main",
]

#: STORY-001.5 / Task 6.1 — stale sentinel age threshold for the doctor check.
#: Matches AC-7's cleanup window so a doctor PASS implies a clean /tmp state.
#: Sentinels younger than this are considered "in-flight" (a concurrent
#: claude-i run wrote them) and are not flagged.
_STALE_SENTINEL_SECONDS: float = 86400.0  # 24h


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


# STORY-001.5 — argparse cannot cleanly disambiguate ``nargs="?"`` positional +
# closed-choice subparsers (it tries to bind the positional against the
# subparser choice list before falling through). We solve this by argv
# pre-dispatch BEFORE argparse runs: peek at the first non-flag positional,
# and if it matches a known subcommand, route to ``_build_subcommand_parser``;
# otherwise route to ``_build_prompt_parser``. Both parsers share the epilog
# and ``--version`` so help and version-print work in either path.

_KNOWN_SUBCMDS: frozenset[str] = frozenset({"doctor", "uninstall", "reap"})

#: Long-form options that consume a value (so the value itself is not the
#: first non-flag positional). Keep in sync with the prompt parser below.
_FLAGS_WITH_VALUE: frozenset[str] = frozenset(
    {"--ready-wait", "--timeout", "--permission-mode", "--output-format"}
)

_EPILOG: str = (
    "Exit codes:\n"
    "  0  success\n"
    "  1  runtime error (timeout, parse failure, doctor FAIL)\n"
    "  2  missing dependency or config error\n"
    "  3  unsupported platform (native Windows; use WSL2)\n"
    "\n"
    "Subcommands (STORY-001.5):\n"
    "  doctor      runtime self-diagnostic (--json for machine-readable)\n"
    "  uninstall   remove the claude-i Stop hook from settings.json\n"
    "  reap        kill orphaned claude-i-* tmux sessions\n"
    "\n"
    "Notes:\n"
    "  On normal exit, KeyboardInterrupt, or SIGTERM, the tmux session\n"
    "  claude-i-<pid> is reaped automatically. SIGKILL cannot be\n"
    "  intercepted — use `claude-i reap` to clean up after SIGKILL."
)


def _first_nonflag_arg(argv: list[str]) -> str | None:
    """Return the first non-flag positional in ``argv[1:]``, or ``None``.

    Skips values consumed by long options in ``_FLAGS_WITH_VALUE`` and stops
    at the ``--`` end-of-options sentinel. Used by ``main()`` to decide
    whether to build the subcommand parser or the prompt parser.

    Examples:
        ``[claude-i, doctor]`` → ``"doctor"``
        ``[claude-i, --ready-wait, 10, doctor]`` → ``"doctor"``
        ``[claude-i, hello]`` → ``"hello"``
        ``[claude-i, --version]`` → ``None``
        ``[claude-i, --, doctor]`` → ``None`` (``--`` ends option parsing)
    """
    skip_next = False
    for arg in argv[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            return None
        if arg.startswith("-"):
            if arg in _FLAGS_WITH_VALUE:
                skip_next = True
            continue
        return arg
    return None


def _add_version_flag(ap: argparse.ArgumentParser) -> None:
    """Wire ``--version`` so it short-circuits before parse_args returns.

    Both parsers register it independently so ``claude-i --version`` and
    ``claude-i doctor --version`` both work — argparse's ``action="version"``
    exits immediately, which keeps the pre-args-hook safety contract intact.
    """
    ap.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_version_string()}",
    )


def _build_prompt_parser() -> argparse.ArgumentParser:
    """Parser for the main prompt flow (no subcommands).

    Activated when the first non-flag positional is anything OTHER than a
    known subcommand. Owns ``prompt`` + all main-flow flags.
    """
    ap = argparse.ArgumentParser(
        prog="claude-i",
        description=(
            "claude-i: like `claude -p`, but driven through an interactive "
            "Claude session."
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_version_flag(ap)
    ap.add_argument("prompt")
    ap.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="tail the tmux pane to stderr (debug hangs)",
    )
    # STORY-001.5 / Task 6.5 — default raised from 4.0 to 10.0 because the
    # readiness poller (G17) probes the pane and returns AS SOON AS the TUI
    # prompt indicator is detected. The flag now caps the MAX wait, not a
    # fixed sleep — bigger headroom is safe because we no longer pay the
    # full timeout on every run.
    ap.add_argument(
        "--ready-wait",
        type=float,
        default=10.0,
        help=(
            "MAX seconds to wait for the TUI to become ready (poller returns "
            "as soon as the prompt indicator is detected). Default: 10."
        ),
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
    # G8 — caller opts into accepting an explicitly-empty assistant response.
    # Without this flag, an empty response from runner.run() exits 1 with a
    # descriptive error so empty results never silently pass as success.
    ap.add_argument(
        "--allow-empty",
        action="store_true",
        default=False,
        help=(
            "treat an explicitly-empty assistant response as success "
            "(exit 0). Default: exit 1 with an error message."
        ),
    )
    # STORY-001.5 / Task 6.4 — AC-5: serialize text + metadata as JSON.
    # ``text`` mode (default) prints the assistant text to stdout as before;
    # ``json`` mode prints a single-line JSON object suitable for piping into
    # ``jq``, pipelines, or test harnesses.
    ap.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
        help=(
            "stdout format for the assistant response. ``text`` (default) "
            "prints the text verbatim; ``json`` emits {text, cost_usd, "
            "tokens_in, tokens_out, duration_ms}."
        ),
    )
    ap.add_argument(
        "extra",
        nargs=argparse.REMAINDER,
        help="extra args forwarded to claude",
    )
    return ap


def _build_subcommand_parser() -> argparse.ArgumentParser:
    """Parser for ``doctor`` / ``uninstall`` / ``reap``.

    Activated when the first non-flag positional matches ``_KNOWN_SUBCMDS``.
    Each subparser owns its own flags (currently only ``doctor --json``).
    """
    ap = argparse.ArgumentParser(
        prog="claude-i",
        description=(
            "claude-i subcommands: doctor (self-diagnostic), uninstall "
            "(remove Stop hook), reap (kill orphan tmux sessions)."
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_version_flag(ap)
    subparsers = ap.add_subparsers(dest="cmd", required=True)
    doctor_p = subparsers.add_parser(
        "doctor",
        help="runtime self-diagnostic (pass/fail per check)",
        description=(
            "Check tmux / claude on PATH, Stop hook installed, settings.json "
            "valid JSON, and absence of stale sentinel files. Exit 0 on all "
            "pass, exit 1 on any fail."
        ),
    )
    doctor_p.add_argument(
        "--json",
        action="store_true",
        default=False,
        dest="doctor_json",
        help="emit the report as a JSON object",
    )
    subparsers.add_parser(
        "uninstall",
        help="remove the claude-i Stop hook from settings.json",
        description=(
            "Remove all claude-i Stop hook entries from "
            "~/.claude/settings.json. Preserves hook entries belonging to "
            "other tools. Exits 0 even when no hook is present (no-op)."
        ),
    )
    subparsers.add_parser(
        "reap",
        help="kill orphaned claude-i-* tmux sessions",
        description=(
            "Find tmux sessions named claude-i-<pid> whose owning PID is no "
            "longer alive and kill them. Sessions with live owners (concurrent "
            "claude-i runs) are NOT touched."
        ),
    )
    return ap


# ---------------------------------------------------------------------------
# Subcommand: doctor (Task 6.1)
# ---------------------------------------------------------------------------


def _check_binary(name: str) -> dict[str, str]:
    """Doctor check (a/b) — is the named binary on ``$PATH``?"""
    path = shutil.which(name)
    if path:
        return {"name": name, "status": "pass", "detail": path}
    return {
        "name": name,
        "status": "fail",
        "detail": f"{name} not found on PATH",
    }


def _check_hook_installed() -> dict[str, str]:
    """Doctor check (c) — is the claude-i Stop hook installed correctly?

    Uses ``hook.hook_installed()`` which does the structural check (right
    type + right command) that landed in G2 (STORY-001.1). A malformed
    legacy entry with the right command but wrong type returns False here
    even though it might look "installed" to a naive grep.
    """
    if hook.hook_installed():
        return {
            "name": "stop_hook",
            "status": "pass",
            "detail": f"installed in {SETTINGS}",
        }
    return {
        "name": "stop_hook",
        "status": "fail",
        "detail": (
            f"claude-i Stop hook missing from {SETTINGS} "
            "(run `claude-i <prompt>` once to install)"
        ),
    }


def _check_settings_json_valid() -> dict[str, str]:
    """Doctor check (d) — does ``settings.json`` parse as JSON?

    A missing file is a PASS (Claude Code creates it lazily; absence is not
    an error). A present-but-malformed file is a FAIL because it blocks
    ``install_hook`` and ``remove_hook`` deterministically.
    """
    if not SETTINGS.exists():
        return {
            "name": "settings_json",
            "status": "pass",
            "detail": f"{SETTINGS} does not exist (will be created on install)",
        }
    try:
        load_settings()
    except json.JSONDecodeError as err:
        return {
            "name": "settings_json",
            "status": "fail",
            "detail": f"{SETTINGS} is not valid JSON: {err}",
        }
    return {
        "name": "settings_json",
        "status": "pass",
        "detail": f"{SETTINGS} parses as JSON",
    }


def _stale_sentinels(now: float | None = None) -> list[Path]:
    """Return the list of ``<tempdir>/claude-i-*.done`` files older than 24h.

    ``now`` is overridable for tests; defaults to ``time.time()``. Younger
    files are considered "in-flight" and excluded — matches AC-7 cleanup
    semantics. Symlinks and broken stat() calls are silently skipped.

    STORY-001.6 / Bug 2 — uses ``tempfile.gettempdir()`` instead of
    hardcoded ``/tmp`` so the doctor check actually finds sentinels on
    macOS (where ``$TMPDIR`` defaults to ``/var/folders/<hash>/T/``).
    Mirrors the same fix in ``runner._cleanup_stale_sentinels``.
    """
    threshold = (now if now is not None else time.time()) - _STALE_SENTINEL_SECONDS
    stale: list[Path] = []
    for path in Path(tempfile.gettempdir()).glob("claude-i-*.done"):
        try:
            if path.stat().st_mtime < threshold:
                stale.append(path)
        except OSError:
            # Best-effort — stat() may fail on symlinks or perms.
            continue
    return stale


def _check_stale_sentinels() -> dict[str, str]:
    """Doctor check (e) — count of ``/tmp/claude-i-*.done`` older than 24h.

    Resolves @po C-4: AC-1(e) and Task 6.1(e) now agree on the 24h window.
    Sentinels younger than 24h are not flagged — they are likely owned by an
    in-flight ``claude-i`` invocation and would generate noisy false positives.
    """
    stale = _stale_sentinels()
    tempdir = tempfile.gettempdir()
    if not stale:
        return {
            "name": "stale_sentinels",
            "status": "pass",
            "detail": f"no stale sentinel files in {tempdir}",
        }
    sample = ", ".join(str(p) for p in stale[:3])
    suffix = "..." if len(stale) > 3 else ""
    return {
        "name": "stale_sentinels",
        "status": "fail",
        "detail": (
            f"{len(stale)} stale sentinel file(s) older than 24h: "
            f"{sample}{suffix} (run `claude-i reap` or delete manually)"
        ),
    }


def cmd_doctor(args: argparse.Namespace) -> int:
    """``claude-i doctor`` — runtime self-diagnostic (STORY-001.5 / Task 6.1).

    Returns the exit code so ``main`` can ``sys.exit`` uniformly. ``0`` on all
    checks pass, ``RUNTIME_ERROR`` (1) on any failure. The ``--json`` flag
    swaps the human-readable lines for a JSON object suitable for scripting.
    """
    checks = [
        _check_binary("tmux"),
        _check_binary("claude"),
        _check_hook_installed(),
        _check_settings_json_valid(),
        _check_stale_sentinels(),
    ]
    overall = "pass" if all(c["status"] == "pass" for c in checks) else "fail"

    if getattr(args, "doctor_json", False):
        sys.stdout.write(
            json.dumps({"checks": checks, "overall": overall}) + "\n"
        )
    else:
        for check in checks:
            marker = "[PASS]" if check["status"] == "pass" else "[FAIL]"
            print(f"{marker} {check['name']}: {check['detail']}")
        print(f"\noverall: {overall}")

    return SUCCESS if overall == "pass" else RUNTIME_ERROR


# ---------------------------------------------------------------------------
# Subcommand: uninstall (Task 6.2)
# ---------------------------------------------------------------------------


def cmd_uninstall(args: argparse.Namespace) -> int:
    """``claude-i uninstall`` — remove Stop hook from settings.json.

    Delegates to ``hook.remove_hook()`` which acquires the G7 flock and
    filters out claude-i hook entries while preserving everything else.
    Exits 0 on success (including the no-op case where nothing was removed)
    and CONFIG_ERROR (2) when settings.json is malformed.
    """
    del args  # unused — uninstall takes no flags
    try:
        removed = hook.remove_hook()
    except json.JSONDecodeError as err:
        # ``hook.remove_hook`` re-raises the underlying decode error when the
        # settings file is malformed. Surface it via stderr + CONFIG_ERROR
        # (parity with install_hook's behavior — see test_install_hook_refuses_malformed_json).
        print(
            f"claude-i: {SETTINGS} is not valid JSON; refusing to touch it ({err.msg})",
            file=sys.stderr,
        )
        return CONFIG_ERROR
    if removed == 0:
        print(f"claude-i: no Stop hook to remove from {SETTINGS}")
    else:
        suffix = "entries" if removed != 1 else "entry"
        print(f"claude-i: removed {removed} Stop hook {suffix} from {SETTINGS}")
    return SUCCESS


# ---------------------------------------------------------------------------
# Subcommand: reap (Task 6.3)
# ---------------------------------------------------------------------------


def cmd_reap(args: argparse.Namespace) -> int:
    """``claude-i reap`` — kill orphaned ``claude-i-*`` tmux sessions.

    WIRES the existing ``reaper.reap_orphans()`` (landed in STORY-001.2);
    does NOT re-implement it (resolves @po validation C-1 — IDS principle:
    ADAPT > CREATE). Live sessions of concurrent runs are LEFT INTACT per
    AC-4 because ``reap_orphans`` already filters via ``_pid_alive``.

    Exits 0 even when no orphans were found (no-op is success). Exits
    CONFIG_ERROR (2) only when ``tmux`` is not on PATH — per AC-4 a
    missing dependency is a config error.
    """
    del args  # unused — reap takes no flags
    if shutil.which("tmux") is None:
        print(
            f"claude-i: tmux not found on PATH. {deps._tmux_install_hint()}",
            file=sys.stderr,
        )
        return CONFIG_ERROR
    killed = reaper.reap_orphans()
    if killed == 0:
        print("claude-i: no orphaned sessions found")
    else:
        suffix = "sessions" if killed != 1 else "session"
        print(f"claude-i: reaped {killed} orphan {suffix}")
    return SUCCESS


# ---------------------------------------------------------------------------
# main() — dispatch
# ---------------------------------------------------------------------------


def _dispatch_subcommand(args: argparse.Namespace) -> int:
    """Route to the matching ``cmd_*`` handler.

    Always returns an int — the subcommand parser is marked ``required=True``
    so ``args.cmd`` is always set when this is reached.
    """
    if args.cmd == "doctor":
        return cmd_doctor(args)
    if args.cmd == "uninstall":
        return cmd_uninstall(args)
    if args.cmd == "reap":
        return cmd_reap(args)
    # Defensive — _build_subcommand_parser sets required=True so this is
    # unreachable. Keep the fallback for static analysis / future additions.
    raise AssertionError(f"unknown subcommand: {args.cmd!r}")


def main() -> None:
    """Entry point registered as ``claude-i`` in ``pyproject.toml``.

    Two-parser pattern (see ``_first_nonflag_arg`` docstring): peek at argv
    to decide whether to parse as a subcommand invocation or as a prompt
    invocation. ``--version`` and ``--help`` short-circuit BEFORE either
    parse_args returns, so deps/hook checks never run for those.
    """
    if _first_nonflag_arg(sys.argv) in _KNOWN_SUBCMDS:
        # STORY-001.5 — subcommand path. doctor / uninstall / reap must work
        # even when the environment is broken (that is the whole point of
        # doctor). We skip deps.check_deps + hook.ensure_hook here; each
        # subcommand handles its own dependencies (cmd_reap checks tmux on
        # PATH and emits CONFIG_ERROR if missing).
        sub_parser = _build_subcommand_parser()
        sub_args = sub_parser.parse_args()
        sys.exit(_dispatch_subcommand(sub_args))

    parser = _build_prompt_parser()
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

    # G8 — translate runner.run's return / raise contract into exit codes.
    # See runner.run docstring for the four-branch contract (AC-7).
    # STORY-001.5 / Task 6.4a — runner.run returns ``(text, metadata)``;
    # Task 6.4 wires the metadata into ``--output-format json``.
    try:
        response, metadata = runner.run(
            args.prompt,
            extra_args,
            args.verbose,
            args.ready_wait,
            args.timeout,
        )
    except RuntimeError as err:
        # Branches 2-4: no assistant turn / payload missing / transcript
        # missing. All map to RUNTIME_ERROR with the error message echoed
        # to stderr so users can see the diagnostic.
        print(f"claude-i: {err}", file=sys.stderr)
        sys.exit(RUNTIME_ERROR)
    except TimeoutError as err:
        # Pre-existing branch: Stop hook never fired in time.
        print(f"claude-i: {err}", file=sys.stderr)
        sys.exit(RUNTIME_ERROR)

    # Branch 1: verified-empty — empty string returned. cli.main translates
    # to exit 0 only if the caller passed --allow-empty.
    if response == "":
        if args.allow_empty:
            _emit_response("", metadata, args.output_format)
            sys.exit(SUCCESS)
        print(
            "claude-i: empty response (use --allow-empty to accept)",
            file=sys.stderr,
        )
        sys.exit(RUNTIME_ERROR)

    _emit_response(response, metadata, args.output_format)


def _emit_response(text: str, metadata: Any, fmt: str) -> None:
    """Print the response to stdout in the requested format.

    STORY-001.5 / Task 6.4 / AC-5 — JSON envelope contract:
    ``{"text": "...", "cost_usd": null|float, "tokens_in": null|int,
       "tokens_out": null|int, "duration_ms": int}``.
    Text mode preserves the seed's verbatim ``print(response)`` behavior.
    """
    if fmt == "json":
        sys.stdout.write(
            json.dumps(
                {
                    "text": text,
                    "cost_usd": metadata.get("cost_usd"),
                    "tokens_in": metadata.get("tokens_in"),
                    "tokens_out": metadata.get("tokens_out"),
                    "duration_ms": metadata.get("duration_ms"),
                }
            )
            + "\n"
        )
    else:
        print(text)


if __name__ == "__main__":
    main()
