"""Unit tests for ``claude_i.cli``.

Covers:

- AC-1 / Task 2.3 (G1): ``--permission-mode`` default ``acceptEdits`` plus
  override via CLI flag — flag value forwarded to ``runner.run`` extras.
- AC-7 / Task 2.2: ``deps.check_deps`` is invoked BEFORE ``hook.ensure_hook``.
- AC-8 / Task 2.8: exit-code epilog appears in ``--help`` output.

No real ``tmux`` / ``claude`` is invoked — ``runner.run`` is mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from claude_i import cli

#: Default metadata stub returned by mocked ``runner.run`` calls in CLI tests.
#: STORY-001.5 / Task 6.4a — signature is ``(text, RunMetadata)``; tests that
#: don't care about metadata still need to return a well-formed tuple so
#: ``cli.main`` can destructure without error.
_DEFAULT_METADATA = {
    "duration_ms": 42,
    "cost_usd": None,
    "tokens_in": None,
    "tokens_out": None,
}


def _invoke_main(argv: list[str]) -> MagicMock:
    """Run ``cli.main`` with the given argv, patching deps/hook/runner.

    Returns the ``runner.run`` mock so callers can introspect the call args.
    """
    with (
        patch.object(cli.deps, "check_deps") as _cd,
        patch.object(cli.hook, "ensure_hook") as _eh,
        patch.object(
            cli.runner, "run", return_value=("ok", _DEFAULT_METADATA)
        ) as run_mock,
        patch("sys.argv", ["claude-i", *argv]),
    ):
        cli.main()
        # Sanity: both pre-run hooks were called exactly once.
        _cd.assert_called_once()
        _eh.assert_called_once()
    return run_mock


def test_permission_mode_default() -> None:
    """``--permission-mode`` defaults to ``acceptEdits`` and is passed through."""
    run_mock = _invoke_main(["hello"])
    # Signature: run(prompt, extra_args, verbose, ready_wait, timeout)
    _prompt, extra_args, *_rest = run_mock.call_args.args
    assert "--permission-mode" in extra_args
    idx = extra_args.index("--permission-mode")
    assert extra_args[idx + 1] == "acceptEdits"


def test_permission_mode_override() -> None:
    """``--permission-mode bypassPermissions`` propagates verbatim."""
    run_mock = _invoke_main(["--permission-mode", "bypassPermissions", "hello"])
    _prompt, extra_args, *_rest = run_mock.call_args.args
    idx = extra_args.index("--permission-mode")
    assert extra_args[idx + 1] == "bypassPermissions"


def test_permission_mode_precedes_user_extras() -> None:
    """Default ``--permission-mode`` is injected before user-supplied extras.

    Verifies the wiring order: our injected flag pair lands at index 0/1 so
    the user can still override by passing their own ``--permission-mode``
    later (claude's CLI parser takes the last occurrence).
    """
    run_mock = _invoke_main(["hello", "--", "--model", "sonnet"])
    _prompt, extra_args, *_rest = run_mock.call_args.args
    assert extra_args[0] == "--permission-mode"
    assert extra_args[1] == "acceptEdits"
    assert "--model" in extra_args
    assert "sonnet" in extra_args


def test_deps_called_before_hook() -> None:
    """``deps.check_deps`` must run BEFORE ``hook.ensure_hook`` in ``main``."""
    call_order: list[str] = []

    def record_deps() -> None:
        call_order.append("deps")

    def record_hook() -> None:
        call_order.append("hook")

    with (
        patch.object(cli.deps, "check_deps", side_effect=record_deps),
        patch.object(cli.hook, "ensure_hook", side_effect=record_hook),
        patch.object(cli.runner, "run", return_value=("ok", _DEFAULT_METADATA)),
        patch("sys.argv", ["claude-i", "hello"]),
    ):
        cli.main()
    assert call_order == ["deps", "hook"], (
        f"deps.check_deps must run before hook.ensure_hook; got: {call_order}"
    )


def test_help_contains_exit_code_epilog(capsys: pytest.CaptureFixture[str]) -> None:
    """``claude-i --help`` displays the exit-code epilog (AC-8)."""
    with patch("sys.argv", ["claude-i", "--help"]):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    # --help exits with code 0 by argparse convention.
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Exit codes:" in captured.out
    assert "0  success" in captured.out
    assert "1  runtime error" in captured.out
    assert "2  missing dependency" in captured.out


def test_version_still_works(capsys: pytest.CaptureFixture[str]) -> None:
    """Regression: ``--version`` short-circuits before deps/hook callbacks."""
    with (
        patch.object(cli.deps, "check_deps") as cd,
        patch.object(cli.hook, "ensure_hook") as eh,
        patch.object(cli.runner, "run") as run_mock,
        patch("sys.argv", ["claude-i", "--version"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "claude-i" in captured.out
    # The whole point: none of these may run on --version.
    cd.assert_not_called()
    eh.assert_not_called()
    run_mock.assert_not_called()


# STORY-001.2 / Task 3.5 + 3.8 / Gap G8 — --allow-empty + ExitCode + epilog.


def test_help_lists_all_four_exit_codes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--help`` epilog enumerates codes 0/1/2/3 (G8 extends 001.1's 0/1/2)."""
    with patch("sys.argv", ["claude-i", "--help"]):
        with pytest.raises(SystemExit):
            cli.main()
    out = capsys.readouterr().out
    assert "0  success" in out
    assert "1  runtime error" in out
    assert "2  missing dependency" in out
    assert "3  unsupported platform" in out


def test_runtime_error_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    """A ``RuntimeError`` from ``runner.run`` translates to exit 1 (RUNTIME_ERROR).

    Covers Branches 2-4 of the AC-7 contract — payload missing, transcript
    missing, no assistant message all surface via RuntimeError and exit 1.
    """
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(
            cli.runner, "run", side_effect=RuntimeError("hook fired but no payload written")
        ),
        patch("sys.argv", ["claude-i", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1
    assert "hook fired but no payload written" in capsys.readouterr().err


def test_timeout_error_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    """A ``TimeoutError`` from ``runner.run`` also maps to RUNTIME_ERROR."""
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(cli.runner, "run", side_effect=TimeoutError("Stop hook timeout")),
        patch("sys.argv", ["claude-i", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1
    assert "Stop hook timeout" in capsys.readouterr().err


def test_no_allow_empty_rejects_empty(capsys: pytest.CaptureFixture[str]) -> None:
    """Empty response without ``--allow-empty`` exits 1 with the canonical message."""
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(cli.runner, "run", return_value=("", _DEFAULT_METADATA)),
        patch("sys.argv", ["claude-i", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "empty response" in err
    assert "--allow-empty" in err


def test_allow_empty_accepts_empty(capsys: pytest.CaptureFixture[str]) -> None:
    """Empty response WITH ``--allow-empty`` exits 0 cleanly."""
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(cli.runner, "run", return_value=("", _DEFAULT_METADATA)),
        patch("sys.argv", ["claude-i", "--allow-empty", "hello"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 0


def test_non_empty_response_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    """Happy path: non-empty response prints to stdout and exits 0 implicitly."""
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(
            cli.runner, "run", return_value=("hello world", _DEFAULT_METADATA)
        ),
        patch("sys.argv", ["claude-i", "hello"]),
    ):
        # main() does not call sys.exit in the happy path; it just prints.
        cli.main()
    assert "hello world" in capsys.readouterr().out
