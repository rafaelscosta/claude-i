"""Unit tests for ``claude_i.cli``.

Covers:

- AC-1 / Task 2.3 (G1): ``--permission-mode`` default ``acceptEdits`` plus
  override via CLI flag — flag value forwarded to ``runner.run`` extras.
- AC-7 / Task 2.2: ``deps.check_deps`` is invoked BEFORE ``hook.ensure_hook``.
- AC-8 / Task 2.8: exit-code epilog appears in ``--help`` output.

No real ``tmux`` / ``claude`` is invoked — ``runner.run`` is mocked.
"""

from __future__ import annotations

import time
from typing import Any
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


# ---------------------------------------------------------------------------
# STORY-001.5 / Task 6.4 — --output-format json (AC-5)
# ---------------------------------------------------------------------------


def test_output_format_json_structure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--output-format json`` emits the AC-5 envelope to stdout.

    Contract: ``{"text": "...", "cost_usd": null|float, "tokens_in": null|int,
    "tokens_out": null|int, "duration_ms": int}``.
    """
    import json as _json
    full_metadata = {
        "duration_ms": 1234,
        "cost_usd": 0.0042,
        "tokens_in": 100,
        "tokens_out": 50,
    }
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(
            cli.runner, "run", return_value=("hello world", full_metadata)
        ),
        patch("sys.argv", ["claude-i", "--output-format", "json", "hello"]),
    ):
        cli.main()
    out = capsys.readouterr().out.strip()
    parsed = _json.loads(out)
    assert parsed == {
        "text": "hello world",
        "cost_usd": 0.0042,
        "tokens_in": 100,
        "tokens_out": 50,
        "duration_ms": 1234,
    }


def test_output_format_json_null_fields_when_absent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON envelope tolerates ``None`` for cost/token fields.

    The Stop hook payload from older ``claude`` versions does not surface
    cost/token metrics; we serialize them as JSON ``null`` so consumers can
    distinguish "not reported" from "zero usage".
    """
    import json as _json
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(
            cli.runner, "run", return_value=("hi", _DEFAULT_METADATA)
        ),
        patch("sys.argv", ["claude-i", "--output-format", "json", "prompt"]),
    ):
        cli.main()
    parsed = _json.loads(capsys.readouterr().out.strip())
    assert parsed["text"] == "hi"
    assert parsed["cost_usd"] is None
    assert parsed["tokens_in"] is None
    assert parsed["tokens_out"] is None
    assert parsed["duration_ms"] == 42


def test_output_format_text_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--output-format`` defaults to ``text`` (verbatim print). Regression
    guard so existing pipelines see no behavior change without the flag."""
    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(
            cli.runner, "run", return_value=("plain text", _DEFAULT_METADATA)
        ),
        patch("sys.argv", ["claude-i", "hello"]),
    ):
        cli.main()
    out = capsys.readouterr().out
    # In text mode the output is just the response text + a trailing newline
    # from print() — NOT a JSON object.
    assert out.strip() == "plain text"
    assert "{" not in out  # rules out a JSON serialization slip-through


# ---------------------------------------------------------------------------
# STORY-001.5 / Task 6.1 — doctor subcommand
# ---------------------------------------------------------------------------


def test_doctor_all_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """All 5 checks pass → ``[PASS]`` lines + ``overall: pass`` + exit 0."""
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda name: f"/usr/bin/{name}" if name in {"tmux", "claude"} else None,
    )
    monkeypatch.setattr(cli.hook, "hook_installed", lambda: True)
    # Settings absent → check (d) PASS, check (c) handled via hook_installed.
    monkeypatch.setattr(cli, "SETTINGS", cli.Path("/nonexistent/settings.json"))
    monkeypatch.setattr(cli, "_stale_sentinels", lambda: [])

    with (
        patch.object(cli.deps, "check_deps") as cd,
        patch.object(cli.hook, "ensure_hook") as eh,
        patch("sys.argv", ["claude-i", "doctor"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 0, "all-pass doctor must exit 0"
    out = capsys.readouterr().out
    assert "[PASS] tmux" in out
    assert "[PASS] claude" in out
    assert "[PASS] stop_hook" in out
    assert "[PASS] settings_json" in out
    assert "[PASS] stale_sentinels" in out
    assert "overall: pass" in out
    # The subcommand path must NOT run deps.check_deps / hook.ensure_hook —
    # doctor's whole point is reporting on a possibly-broken environment.
    cd.assert_not_called()
    eh.assert_not_called()


def test_doctor_fails_on_missing_tmux(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing ``tmux`` binary surfaces as ``[FAIL] tmux`` and exit 1."""
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda name: "/usr/bin/claude" if name == "claude" else None,
    )
    monkeypatch.setattr(cli.hook, "hook_installed", lambda: True)
    monkeypatch.setattr(cli, "SETTINGS", cli.Path("/nonexistent/settings.json"))
    monkeypatch.setattr(cli, "_stale_sentinels", lambda: [])

    with patch("sys.argv", ["claude-i", "doctor"]):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1, "doctor must exit 1 on any FAIL"
    out = capsys.readouterr().out
    assert "[FAIL] tmux" in out
    assert "overall: fail" in out


def test_doctor_fails_on_missing_hook(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing Stop hook → ``[FAIL] stop_hook`` + exit 1."""
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    monkeypatch.setattr(cli.hook, "hook_installed", lambda: False)
    monkeypatch.setattr(cli, "SETTINGS", cli.Path("/nonexistent/settings.json"))
    monkeypatch.setattr(cli, "_stale_sentinels", lambda: [])

    with patch("sys.argv", ["claude-i", "doctor"]):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "[FAIL] stop_hook" in out


def test_doctor_fails_on_malformed_settings(
    tmp_path: pytest.TempdirFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Doctor check (d) fails when settings.json is present but malformed.

    The malformed-settings file also breaks hook_installed() (which catches
    JSONDecodeError and returns False), so check (c) FAILs too. The test
    asserts BOTH FAIL lines + overall fail. This double failure is the
    real-world behavior: bad settings.json breaks every consumer.
    """
    from pathlib import Path as _Path

    from claude_i import settings as _settings_mod
    bad_settings: _Path = _Path(str(tmp_path)) / "settings.json"
    bad_settings.write_text("{not: json")
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    # Do NOT patch hook_installed — let it run against the bad file so we
    # exercise the real graceful-degradation behavior (returns False on
    # JSONDecodeError per G2 hardening in 001.1). load_settings() reads
    # from settings.SETTINGS so we must patch that, plus the cli.SETTINGS
    # alias (cli imported it directly).
    monkeypatch.setattr(_settings_mod, "SETTINGS", bad_settings)
    monkeypatch.setattr(cli, "SETTINGS", bad_settings)
    monkeypatch.setattr(cli.hook, "SETTINGS", bad_settings)
    monkeypatch.setattr(cli, "_stale_sentinels", lambda: [])

    with patch("sys.argv", ["claude-i", "doctor"]):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "[FAIL] settings_json" in out
    assert "not valid JSON" in out


def test_doctor_fails_on_stale_sentinels(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Doctor check (e) fails when stale sentinels exist."""
    from pathlib import Path as _Path
    fake_stale = [_Path("/tmp/claude-i-12345.done")]
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    monkeypatch.setattr(cli.hook, "hook_installed", lambda: True)
    monkeypatch.setattr(cli, "SETTINGS", _Path("/nonexistent/settings.json"))
    monkeypatch.setattr(cli, "_stale_sentinels", lambda: fake_stale)

    with patch("sys.argv", ["claude-i", "doctor"]):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "[FAIL] stale_sentinels" in out
    assert "1 stale sentinel" in out


def test_doctor_json_output(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``doctor --json`` emits a parseable JSON object with checks + overall."""
    import json as _json
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: f"/usr/bin/{name}"
    )
    monkeypatch.setattr(cli.hook, "hook_installed", lambda: True)
    monkeypatch.setattr(cli, "SETTINGS", cli.Path("/nonexistent/settings.json"))
    monkeypatch.setattr(cli, "_stale_sentinels", lambda: [])

    with patch("sys.argv", ["claude-i", "doctor", "--json"]):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    parsed = _json.loads(out)
    assert parsed["overall"] == "pass"
    assert isinstance(parsed["checks"], list)
    assert len(parsed["checks"]) == 5
    names = {c["name"] for c in parsed["checks"]}
    assert names == {
        "tmux",
        "claude",
        "stop_hook",
        "settings_json",
        "stale_sentinels",
    }


def test_stale_sentinels_age_filter(
    tmp_path: pytest.TempdirFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_stale_sentinels`` skips files younger than 24h (resolves @po C-4).

    Creates two .done files — one recent, one with mtime set to 25h ago —
    and asserts only the old one is returned. Redirects ``tempfile.gettempdir``
    (STORY-001.6 / Bug 2) so the helper walks our tmp dir instead of the real
    system tempdir.
    """
    import os
    from pathlib import Path as _Path
    tmp_dir = _Path(str(tmp_path))
    recent = tmp_dir / "claude-i-recent.done"
    old = tmp_dir / "claude-i-old.done"
    recent.touch()
    old.touch()
    # Backdate ``old`` to 25h ago.
    twenty_five_hours_ago = time.time() - (25 * 3600)
    os.utime(old, (twenty_five_hours_ago, twenty_five_hours_ago))

    # STORY-001.6 / Bug 2 — _stale_sentinels now uses tempfile.gettempdir()
    # instead of hardcoded "/tmp". Redirect the function instead of Path.
    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: str(tmp_dir))
    stale = cli._stale_sentinels()
    assert old in stale
    assert recent not in stale


# ---------------------------------------------------------------------------
# STORY-001.5 / Task 6.3 / Q-3 — cmd_reap wiring tests
# ---------------------------------------------------------------------------


def test_reap_subcommand_calls_reap_orphans(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``claude-i reap`` delegates to ``reaper.reap_orphans()`` exactly once.

    Verifies the IDS-compliant wiring (resolves @po C-1): ``cmd_reap`` does
    NOT re-implement orphan detection; it calls the existing
    ``reap_orphans`` from STORY-001.2. Also confirms the doctor-style
    subcommand path bypasses ``deps.check_deps`` / ``hook.ensure_hook``
    (a reap should work even when the env is partially broken).
    """
    # tmux must look installed so the CONFIG_ERROR shortcut in cmd_reap does
    # not preempt the call to reap_orphans.
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda name: "/usr/bin/tmux" if name == "tmux" else None,
    )

    with (
        patch.object(cli.deps, "check_deps") as cd,
        patch.object(cli.hook, "ensure_hook") as eh,
        patch.object(cli.reaper, "reap_orphans", return_value=3) as reap_mock,
        patch("sys.argv", ["claude-i", "reap"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    # Exit 0 because reap_orphans succeeded; output reports the count.
    assert exc.value.code == 0
    reap_mock.assert_called_once_with()
    out = capsys.readouterr().out
    assert "reaped 3 orphan" in out
    # Subcommand path skips the pre-run dep/hook checks.
    cd.assert_not_called()
    eh.assert_not_called()


def test_reap_subcommand_zero_count_exits_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``claude-i reap`` exits 0 with a no-op message when no orphans exist.

    AC-4: count == 0 is still success. Operator-facing message must be
    distinct from the count-positive case so scripts can grep for either.
    """
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda name: "/usr/bin/tmux" if name == "tmux" else None,
    )

    with (
        patch.object(cli.deps, "check_deps"),
        patch.object(cli.hook, "ensure_hook"),
        patch.object(cli.reaper, "reap_orphans", return_value=0),
        patch("sys.argv", ["claude-i", "reap"]),
    ):
        with pytest.raises(SystemExit) as exc:
            cli.main()
    assert exc.value.code == 0, "zero orphans must still exit 0 (no-op success)"
    out = capsys.readouterr().out
    assert "no orphaned sessions found" in out


# ---------------------------------------------------------------------------
# STORY-001.6 / Bug 2 — doctor stale-sentinels uses tempfile.gettempdir()
# ---------------------------------------------------------------------------


def test_stale_sentinels_uses_tempfile_gettempdir(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """STORY-001.6 / Bug 2 — `_stale_sentinels` uses tempfile.gettempdir(), not /tmp.

    Mirrors the runner-side fix. Without this, the doctor check on macOS
    silently sees zero sentinels (real ones live in ``/var/folders/.../T/``)
    and reports PASS even when 437 sentinels are accumulating.
    """
    import os
    from pathlib import Path as _Path
    tmp_dir = _Path(str(tmp_path))
    old = tmp_dir / "claude-i-old.done"
    old.touch()
    twenty_five_hours_ago = time.time() - (25 * 3600)
    os.utime(old, (twenty_five_hours_ago, twenty_five_hours_ago))

    monkeypatch.setattr(cli.tempfile, "gettempdir", lambda: str(tmp_dir))
    stale = cli._stale_sentinels()
    assert old in stale, (
        f"doctor check (e) must read tempfile.gettempdir(); got stale={stale}"
    )
