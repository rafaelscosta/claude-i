"""Unit tests for ``claude_i.runner``.

STORY-001.1 / Task 2.4 / Gap G4 — env isolation:

- ``test_sentinel_stripped_from_subprocess_env``: the ``env`` kwarg passed to
  ``subprocess.run`` for the tmux ``new-session`` spawn does NOT contain
  ``CLAUDE_I_SENTINEL``.
- ``test_sentinel_still_in_sh_command``: the ``sh -c <claude_cmd>`` argument
  string DOES still start with ``CLAUDE_I_SENTINEL=`` (Layer 1 delivery
  channel to the sub-claude's Stop hook).

Both assertions are required. A passing first test with the sentinel lost
entirely from ``claude_cmd`` would break the entire pipeline silently — the
shell guard in the Stop hook would not fire, the sentinel file would never
be touched, and ``run()`` would deadlock at the wait loop until timeout. The
second test catches that regression.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from claude_i import runner


def _make_subprocess_capture() -> tuple[MagicMock, dict[str, Any]]:
    """Return a ``subprocess.run`` mock that records the FIRST call's args.

    ``run()`` calls ``subprocess.run`` multiple times (new-session, then
    set-buffer / paste-buffer / send-keys / kill-session). We only care about
    the first call — the new-session spawn — since that is the only call
    that should pass a sanitized env. Read-side tmux calls inherit
    ``os.environ`` by design.
    """
    captured: dict[str, Any] = {}
    call_count = {"n": 0}

    def fake_run(*args: Any, **kwargs: Any) -> MagicMock:
        if call_count["n"] == 0:
            captured["args"] = args
            captured["kwargs"] = kwargs
        call_count["n"] += 1
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        return result

    mock = MagicMock(side_effect=fake_run)
    return mock, captured


def _drive_run_until_first_subprocess_call(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """Invoke ``runner.run`` and short-circuit before the sentinel wait.

    The first ``subprocess.run`` invocation happens inside ``tmux("new-session",
    ...)`` at the very top of ``run()``. We arrange for the wait loop to
    detect a "ready" sentinel immediately (via a stubbed ``Path.exists``) and
    a stubbed transcript read so ``run()`` returns cleanly without touching
    real files.
    """
    sub_mock, captured = _make_subprocess_capture()

    # Pretend CLAUDE_I_SENTINEL is in os.environ so the strip is observable.
    # In production this never happens, but the test must construct the
    # scenario where the env-strip is doing real work.
    monkeypatch.setenv("CLAUDE_I_SENTINEL", "/tmp/should-be-stripped")

    # Make Path.exists() True for everything so we skip the wait loop and the
    # payload-not-found branch; make read_text() return an empty transcript
    # spec so run() returns "" quickly.
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *args, **kwargs: '{"transcript_path": "/tmp/dne"}',
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    # STORY-001.6 / Bug 1 — payload.stat().st_size == 0 guard. Stub stat() so
    # the empty-payload branch is skipped (size > 0 means "valid"); the
    # subsequent JSON read_text() stub returns a parseable transcript spec.
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    # STORY-001.6 / Bug 1 — short-circuit the payload grace period to keep
    # tests fast and deterministic.
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    # STORY-001.6 / Bug 4 — short-circuit transcript-retry deadline.
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    # time.sleep should be a no-op so the test runs fast.
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    # G6 — silence reaper registration so test runs don't install a real
    # SIGTERM handler in the process. The G6 test suite verifies wiring
    # explicitly; here we just need run() to succeed.
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _session: None)
    # STORY-001.5 / Task 6.6 — neutralize stale-sentinel cleanup in stubs so
    # tests stay deterministic regardless of /tmp state on the host machine.
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    # ready_wait=0 / timeout=1 keep the call short even if anything else slips.
    # G8: after the four-branch RuntimeError refactor, a stubbed empty
    # transcript triggers Branch 2 (no assistant message). The G4 contract
    # tests assert against captured subprocess args, which are populated by
    # the FIRST subprocess.run call — long before the RuntimeError site.
    # Swallow the expected RuntimeError so the captured kwargs are returned.
    try:
        runner.run(prompt="hi", extra_args=[], verbose=False, ready_wait=0.0, timeout=1)
    except RuntimeError:
        pass
    return captured


def test_sentinel_stripped_from_subprocess_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G4 assertion 1: env kwarg of the tmux-spawning subprocess.run lacks
    ``CLAUDE_I_SENTINEL``."""
    captured = _drive_run_until_first_subprocess_call(monkeypatch)
    env = captured["kwargs"].get("env")
    assert env is not None, (
        "new-session subprocess.run must pass env= (sanitized), not None — "
        "None would inherit os.environ and leak CLAUDE_I_SENTINEL"
    )
    assert "CLAUDE_I_SENTINEL" not in env, (
        f"CLAUDE_I_SENTINEL leaked into env kwarg: keys={list(env.keys())[:5]}..."
    )


def test_sentinel_still_in_sh_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """G4 assertion 2: the ``sh -c <claude_cmd>`` arg string still begins with
    ``CLAUDE_I_SENTINEL=``.

    This catches the anti-pattern where someone "fixes" the env leak by
    stripping the shell prefix as well — that would break the Stop hook's
    shell guard and the entire pipeline.
    """
    captured = _drive_run_until_first_subprocess_call(monkeypatch)
    # ``subprocess.run`` is called positionally: subprocess.run([cmd, *args], ...)
    # The first positional arg is the argv list.
    argv = captured["args"][0]
    assert argv[0] == "tmux"
    # Find the ``-c`` flag and inspect the next element (the claude_cmd).
    assert "-c" in argv, f"new-session call should include 'sh -c <claude_cmd>'; argv={argv}"
    c_idx = argv.index("-c")
    claude_cmd = argv[c_idx + 1]
    assert claude_cmd.startswith("CLAUDE_I_SENTINEL="), (
        "sh -c argument must begin with the CLAUDE_I_SENTINEL=<path> shell "
        "prefix — that prefix is the ONLY delivery channel to the sub-claude's "
        f"Stop hook shell guard. Got: {claude_cmd[:80]!r}"
    )


def test_sanitized_env_strips_only_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_sanitized_env`` returns ``os.environ`` minus the strip-list.

    Verifies that we do not accidentally lose other env vars while stripping
    ``CLAUDE_I_SENTINEL``.
    """
    monkeypatch.setenv("CLAUDE_I_SENTINEL", "/tmp/x")
    monkeypatch.setenv("PATH_TO_PRESERVE", "yes")
    env = runner._sanitized_env()
    assert "CLAUDE_I_SENTINEL" not in env
    assert env.get("PATH_TO_PRESERVE") == "yes"


# STORY-001.2 / Task 3.1 / Gap G5 — secure tempfile creation.


def test_sentinel_uses_mkstemp(monkeypatch: pytest.MonkeyPatch) -> None:
    """``runner.run`` uses ``tempfile.mkstemp`` and never calls ``tempfile.mktemp``.

    ``mktemp`` returns a path WITHOUT creating the file — a TOCTOU race that
    allows another process to win the create. ``mkstemp`` is atomic. The G5
    regression test asserts both: ``mkstemp`` is called, and ``mktemp``
    is NEVER called.
    """
    mkstemp_calls: list[tuple[Any, Any]] = []
    mktemp_calls: list[tuple[Any, Any]] = []

    real_mkstemp = runner.tempfile.mkstemp

    def fake_mkstemp(*args: Any, **kwargs: Any) -> tuple[int, str]:
        mkstemp_calls.append((args, kwargs))
        return real_mkstemp(*args, **kwargs)

    def fake_mktemp(*args: Any, **kwargs: Any) -> str:
        mktemp_calls.append((args, kwargs))
        return "/tmp/should-never-be-used"

    monkeypatch.setattr(runner.tempfile, "mkstemp", fake_mkstemp)
    monkeypatch.setattr(runner.tempfile, "mktemp", fake_mktemp)

    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *args, **kwargs: '{"transcript_path": "/tmp/dne"}',
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    # STORY-001.6 / Bug 1 — stub stat() so the empty-payload guard sees a
    # non-zero size (otherwise FileNotFoundError fires on the stubbed payload).
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    # STORY-001.6 / Bug 1 — short-circuit grace period for test speed.
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    # STORY-001.6 / Bug 4 — short-circuit transcript retry for test speed.
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    # G6 — silence reaper registration (see _drive helper).
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _session: None)
    # STORY-001.5 / Task 6.6 — neutralize stale-sentinel cleanup in stubs so
    # tests stay deterministic regardless of /tmp state on the host machine.
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    try:
        runner.run(prompt="hi", extra_args=[], verbose=False, ready_wait=0.0, timeout=1)
    except RuntimeError:
        # G8 — branches may legitimately raise; G5 assertion is about which
        # tempfile API gets called, not whether the run completes.
        pass

    assert len(mkstemp_calls) >= 1, "runner.run must call tempfile.mkstemp"
    assert mktemp_calls == [], (
        f"runner.run must NEVER call tempfile.mktemp; got: {mktemp_calls}"
    )
    _args, kwargs = mkstemp_calls[0]
    # mkstemp signature accepts prefix / suffix kwargs; verify the prefix is
    # passed so on-disk tempfiles are still recognizable as claude-i artifacts.
    assert kwargs.get("prefix") == "claude-i-"
    assert kwargs.get("suffix") == ".done"


# STORY-001.2 / Task 3.3 / Gap G6 — reaper wiring.


def test_cleanup_registered_after_session_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``runner.run`` calls ``reaper.register_cleanup(session)`` once.

    The session name is ``claude-i-<pid>`` and must match the literal that the
    ``new-session`` call uses (otherwise atexit cleanup would target a
    different session than the one actually spawned).
    """
    register_calls: list[str] = []

    def fake_register(session: str) -> None:
        register_calls.append(session)

    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *args, **kwargs: '{"transcript_path": "/tmp/dne"}',
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    # STORY-001.6 / Bug 1 — stub stat() so the empty-payload guard sees a
    # non-zero size for the stubbed payload Path.
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    # STORY-001.6 / Bug 1 — short-circuit grace period for test speed.
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    # STORY-001.6 / Bug 4 — short-circuit transcript retry for test speed.
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", fake_register)

    try:
        runner.run(prompt="hi", extra_args=[], verbose=False, ready_wait=0.0, timeout=1)
    except RuntimeError:
        pass

    assert len(register_calls) == 1, (
        f"runner.run must call reaper.register_cleanup exactly once; "
        f"got {len(register_calls)} calls: {register_calls}"
    )
    # Session names follow the claude-i-<pid> format — must match what
    # new-session actually spawned.
    assert register_calls[0].startswith("claude-i-")


# STORY-001.2 / Task 3.5 / Gap G8 — four-branch parse-failure contract.


def _stub_runner_io(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload_text: str = '{"transcript_path": "/tmp/dne"}',
    transcript_lines: list[str] | None = None,
    payload_exists: bool = True,
    transcript_exists: bool = True,
) -> None:
    """Common stubs for the four-branch tests.

    Skips real subprocess / tempfile work and lets the test drive ``run()``
    deterministically to a chosen branch. ``payload_exists`` /
    ``transcript_exists`` toggle the Branch 3 / Branch 4 paths.
    """
    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))

    transcript_text = "\n".join(transcript_lines or [])

    # Track which paths exist — sentinel always, payload + transcript per args.
    # Order of branches in run(): sentinel → payload → transcript.
    def fake_exists(self: Any) -> bool:
        s = str(self)
        if s.endswith(".json"):
            return payload_exists
        # Anything that is NOT a sentinel-style claude-i tmpfile is treated
        # as the transcript path (the test supplies "/tmp/dne", "/tmp/never",
        # etc. via payload_text).
        if "claude-i-" not in s:
            return transcript_exists
        # The sentinel itself — always exists in tests so the wait loop
        # exits immediately.
        return True

    def fake_read_text(self: Any, *args: Any, **kwargs: Any) -> str:
        s = str(self)
        if s.endswith(".json"):
            return payload_text
        return transcript_text

    monkeypatch.setattr(runner.Path, "exists", fake_exists)
    monkeypatch.setattr(runner.Path, "read_text", fake_read_text)
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    # STORY-001.6 / Bug 1 — stub stat() to a non-zero size so the
    # empty-payload guard does not interfere with branch-specific tests.
    # The "test_empty_payload_raises_clean_runtime_error" test overrides this
    # by setting stat().st_size = 0 explicitly via its own monkeypatch.
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    # STORY-001.6 / Bug 1 — neutralize the payload grace period in tests so
    # Branch 3 / Branch 4 raise immediately without burning 2s of wallclock.
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    # STORY-001.6 / Bug 4 — neutralize the transcript-retry deadline in tests
    # so Branch 2 ("no assistant message") raises immediately without burning
    # the 10s default retry window.
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)


def test_payload_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Branch 3 — payload file never written → RuntimeError.

    Replaces the seed's fake-success
    ``return "(hook fired but no payload written)"`` at runner.py:185-186.
    """
    _stub_runner_io(monkeypatch, payload_exists=False)
    with pytest.raises(RuntimeError, match="hook fired but no payload written"):
        runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=1)


def test_transcript_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Branch 4 — payload references a non-existent transcript → RuntimeError.

    Replaces the seed's fake-success
    ``return f"(transcript missing: {transcript})"`` at runner.py:189-190.
    """
    _stub_runner_io(
        monkeypatch,
        payload_text='{"transcript_path": "/tmp/never"}',
        transcript_exists=False,
    )
    with pytest.raises(RuntimeError, match="transcript missing"):
        runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=1)


def test_no_assistant_message_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Branch 2 — transcript has no ``role == "assistant"`` message → RuntimeError.

    Distinct from Branch 1 (assistant turn exists but yields no text).
    """
    _stub_runner_io(
        monkeypatch,
        transcript_lines=[
            json.dumps({"message": {"role": "user", "content": "hi"}}),
        ],
    )
    with pytest.raises(RuntimeError, match="no assistant message in transcript"):
        runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=1)


def test_empty_response_returns_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 1 — assistant turn exists but content yields no text → return ``""``.

    cli.main translates this to exit 0 (with --allow-empty) or exit 1
    (without). The runner itself returns the empty string verbatim.

    STORY-001.5 / Task 6.4a — ``runner.run`` now returns
    ``(text, RunMetadata)``. Branch 1 still emits ``""`` as the text; the
    metadata accompanies it so ``--output-format json`` can serialize.
    """
    _stub_runner_io(
        monkeypatch,
        transcript_lines=[
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "id": "x"}],
                    }
                }
            ),
        ],
    )
    text, metadata = runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=1)
    assert text == ""
    # G11 contract: ``duration_ms`` is always populated; cost/token fields
    # may be ``None`` when the hook payload doesn't surface them.
    assert isinstance(metadata["duration_ms"], int)
    assert metadata["duration_ms"] >= 0
    assert "cost_usd" in metadata
    assert "tokens_in" in metadata
    assert "tokens_out" in metadata


def test_non_empty_response_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path — assistant turn with text blocks returns concatenated text."""
    _stub_runner_io(
        monkeypatch,
        transcript_lines=[
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "hello "},
                            {"type": "text", "text": "world"},
                        ],
                    }
                }
            ),
        ],
    )
    text, _metadata = runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=1)
    assert text == "hello world"


# STORY-001.2 / Task 3.7 / Gap G13 — UTF-8 encoding for tmux IPC.


def test_tmux_subprocess_uses_utf8_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``runner.tmux`` passes ``encoding="utf-8"`` to ``subprocess.run``.

    On headless Linux systems where the locale defaults to ASCII, the
    absence of an explicit encoding causes ``subprocess.run(..., text=True)``
    to crash on multi-byte input. G13 forces UTF-8 at every tmux call site.
    """
    captured: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        captured["kwargs"] = kwargs
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        return result

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.tmux("list-sessions", check=False)
    assert captured["kwargs"].get("encoding") == "utf-8"
    assert captured["kwargs"].get("errors") == "replace"


def test_unicode_prompt_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prompt with PT-BR accents + emoji + CJK survives the round trip."""
    _stub_runner_io(
        monkeypatch,
        transcript_lines=[
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "ok"}],
                    }
                }
            ),
        ],
    )
    prompt = "missão crítica — 漢字 — \U0001F680"
    text, _metadata = runner.run(prompt, [], verbose=False, ready_wait=0.0, timeout=1)
    assert text == "ok"


def test_unicode_encode_warning_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A lone-surrogate prompt logs a warning but does not crash."""
    _stub_runner_io(
        monkeypatch,
        transcript_lines=[
            json.dumps(
                {
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "ok"}],
                    }
                }
            ),
        ],
    )
    bad_prompt = "broken: \ud83d"
    runner.run(bad_prompt, [], verbose=False, ready_wait=0.0, timeout=1)
    err = capsys.readouterr().err
    assert "cannot be encoded as UTF-8" in err


# ---------------------------------------------------------------------------
# STORY-001.5 / Task 6.5 / Gap G17 — readiness poller
# ---------------------------------------------------------------------------


def test_readiness_poller_returns_on_prompt_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_wait_for_tui_ready`` returns as soon as the pane shows the prompt.

    Mocks ``tmux capture-pane`` to first return empty content, then content
    containing ``>``. Asserts the poller iterates and returns without
    raising once the prompt indicator appears.
    """
    pane_outputs = ["", "\n\n", "claude>\n"]
    call_count = {"n": 0}

    def fake_tmux(*args: Any, **kwargs: Any) -> Any:
        idx = min(call_count["n"], len(pane_outputs) - 1)
        call_count["n"] += 1
        result = MagicMock()
        result.stdout = pane_outputs[idx]
        result.returncode = 0
        return result

    monkeypatch.setattr(runner, "tmux", fake_tmux)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    # No raise expected — poller returns cleanly on prompt detection.
    runner._wait_for_tui_ready("claude-i-123", timeout=5.0, interval=0.01)
    assert call_count["n"] >= 2, "poller must iterate at least twice before match"


def test_readiness_poller_raises_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_wait_for_tui_ready`` raises ``TimeoutError`` when the pane never
    shows the prompt indicator within the deadline."""
    def fake_tmux(*args: Any, **kwargs: Any) -> Any:
        result = MagicMock()
        result.stdout = ""  # never matches TUI_READY_PATTERN
        result.returncode = 0
        return result

    monkeypatch.setattr(runner, "tmux", fake_tmux)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    with pytest.raises(TimeoutError, match="TUI did not become ready"):
        runner._wait_for_tui_ready("claude-i-456", timeout=0.05, interval=0.01)


def test_readiness_poller_zero_timeout_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_wait_for_tui_ready`` with ``timeout <= 0`` returns immediately
    without calling tmux — preserves backward compat with tests that pass
    ``ready_wait=0.0`` to short-circuit the poller.
    """
    call_count = {"n": 0}

    def fake_tmux(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        return MagicMock(stdout=">", returncode=0)

    monkeypatch.setattr(runner, "tmux", fake_tmux)
    runner._wait_for_tui_ready("session", timeout=0.0)
    assert call_count["n"] == 0, "zero-timeout poller must not call tmux"


def test_readiness_poller_accepts_unicode_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ASCII ``>`` and U+276F are both recognized prompt indicators (TUI_READY_PATTERN)."""
    def fake_tmux(*args: Any, **kwargs: Any) -> Any:
        result = MagicMock()
        result.stdout = "❯ "  # noqa: RUF001
        result.returncode = 0
        return result

    monkeypatch.setattr(runner, "tmux", fake_tmux)
    runner._wait_for_tui_ready("claude-i-789", timeout=1.0, interval=0.01)
    # No exception → poller detected the powerline prompt glyph.


# ---------------------------------------------------------------------------
# STORY-001.5 / Task 6.6 / Gap G15 — stale sentinel cleanup
# ---------------------------------------------------------------------------


def test_stale_sentinels_cleaned_on_run(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_cleanup_stale_sentinels`` deletes files older than 24h (G15)."""
    import os
    import time as _time
    from pathlib import Path as _Path

    tmp_dir = _Path(str(tmp_path))
    recent = tmp_dir / "claude-i-recent.done"
    old = tmp_dir / "claude-i-old.done"
    old_payload = tmp_dir / "claude-i-old.done.json"
    recent.touch()
    old.touch()
    old_payload.touch()
    twenty_five_hours_ago = _time.time() - (25 * 3600)
    os.utime(old, (twenty_five_hours_ago, twenty_five_hours_ago))
    os.utime(old_payload, (twenty_five_hours_ago, twenty_five_hours_ago))

    # STORY-001.6 / Bug 2 — _cleanup_stale_sentinels uses tempfile.gettempdir()
    # instead of hardcoded "/tmp". Redirect that function so the helper walks
    # our tmp_dir instead of the system tempdir.
    monkeypatch.setattr(runner.tempfile, "gettempdir", lambda: str(tmp_dir))
    runner._cleanup_stale_sentinels()
    assert not old.exists(), "stale sentinel must be deleted"
    assert not old_payload.exists(), "stale payload sidecar must be deleted"
    assert recent.exists(), "fresh sentinel must NOT be deleted (in-flight run)"


def test_stale_sentinels_silently_swallows_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cleanup must NEVER raise — best-effort housekeeping only.

    Stubs ``Path(tempfile.gettempdir()).glob`` to raise. The helper must
    catch and return without propagating; ``runner.run`` depends on this
    contract because the cleanup runs BEFORE the session is created (a
    raise here would abort the run before any useful work).
    """

    class BoomPath:
        def __init__(self, _arg: str) -> None: ...
        def glob(self, _pattern: str) -> None:
            raise OSError("boom")

    def fake_path(arg: str) -> Any:
        # STORY-001.6 / Bug 2 — match whichever value tempfile.gettempdir()
        # returns at runtime instead of hardcoding "/tmp". This test
        # short-circuits the helper by making any Path() call return a Boom
        # so the test focuses on "the helper does not raise".
        return BoomPath(arg)

    monkeypatch.setattr(runner, "Path", fake_path)
    # Must not raise.
    runner._cleanup_stale_sentinels()


# ---------------------------------------------------------------------------
# STORY-001.6 / Bug 1 — payload grace period + empty payload guard
# ---------------------------------------------------------------------------


def test_payload_grace_period_succeeds_when_payload_appears_late(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """``_wait_for_payload`` returns True when payload appears within timeout."""
    from pathlib import Path as _Path
    payload = _Path(str(tmp_path)) / "claude-i-test.done.json"

    # First call: not yet on disk. Second call: present.
    poll_count = {"n": 0}

    def fake_exists(self: Any) -> bool:
        poll_count["n"] += 1
        if poll_count["n"] < 2:
            return False
        return True

    monkeypatch.setattr(runner.Path, "exists", fake_exists)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)

    assert runner._wait_for_payload(payload, timeout=1.0, interval=0.01) is True
    assert poll_count["n"] >= 2, "must poll at least twice (initial false then true)"


def test_payload_grace_period_returns_false_after_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """``_wait_for_payload`` returns False after grace exhaustion."""
    from pathlib import Path as _Path
    payload = _Path(str(tmp_path)) / "claude-i-test.done.json"

    # Always return False — payload never appears.
    monkeypatch.setattr(runner.Path, "exists", lambda self: False)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)

    # Short timeout for test speed; the helper uses time.monotonic() which is
    # not stubbed, so the deadline is real but tiny.
    assert runner._wait_for_payload(payload, timeout=0.05, interval=0.01) is False


def test_payload_grace_period_short_circuits_on_zero_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """``_wait_for_payload`` with timeout<=0 returns ``payload.exists()`` immediately."""
    from pathlib import Path as _Path
    payload = _Path(str(tmp_path)) / "claude-i-test.done.json"

    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    assert runner._wait_for_payload(payload, timeout=0.0, interval=0.01) is True

    monkeypatch.setattr(runner.Path, "exists", lambda self: False)
    assert runner._wait_for_payload(payload, timeout=0.0, interval=0.01) is False


def test_empty_payload_raises_clean_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STORY-001.6 / Bug 1 / Branch 3b — 0-byte payload raises RuntimeError, not JSONDecodeError.

    Reproduces the secondary failure mode where the hook script's ``cat``
    received closed stdin and produced a 0-byte payload. Without the guard,
    ``json.loads("")`` would raise ``JSONDecodeError`` which ``cli.main``
    does NOT catch (only ``RuntimeError`` + ``TimeoutError``), producing a
    raw stack trace. The guard converts it to the friendly Branch 3b error.
    """
    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    # Stub stat() to return 0-byte size for the payload (triggers Branch 3b).
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 0})(),
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: True,
    )
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    with pytest.raises(RuntimeError, match="hook fired but payload empty"):
        runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=1)


def test_cleanup_stale_sentinels_uses_tempfile_gettempdir(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """STORY-001.6 / Bug 2 — `_cleanup_stale_sentinels` uses tempfile.gettempdir().

    Validates the macOS fix: on macOS the system tempdir is
    ``/var/folders/<hash>/T/``, not ``/tmp``. The v0.2.0 hardcoded ``/tmp``
    silently found nothing and left sentinels to accumulate.
    """
    import os
    import time as _time
    from pathlib import Path as _Path

    tmp_dir = _Path(str(tmp_path))
    old = tmp_dir / "claude-i-old.done"
    old.touch()
    twenty_five_hours_ago = _time.time() - (25 * 3600)
    os.utime(old, (twenty_five_hours_ago, twenty_five_hours_ago))

    # Override tempfile.gettempdir() so the cleanup walks our tmp_dir.
    monkeypatch.setattr(runner.tempfile, "gettempdir", lambda: str(tmp_dir))
    runner._cleanup_stale_sentinels()
    assert not old.exists(), (
        "cleanup must read tempfile.gettempdir(), not hardcoded /tmp/"
    )


# ---------------------------------------------------------------------------
# STORY-001.7 / Bug 4 elimination — payload-first response extraction
# ---------------------------------------------------------------------------


def test_extract_text_from_payload_returns_text_when_field_present() -> None:
    """``_extract_text_from_payload`` returns ``(text, True)`` for a valid field."""
    text, came_from_payload = runner._extract_text_from_payload(
        {"last_assistant_message": "PONG"}
    )
    assert text == "PONG"
    assert came_from_payload is True


def test_extract_text_from_payload_falls_back_on_empty_string() -> None:
    """Empty string in payload falls back so we keep verified-empty semantics."""
    text, came_from_payload = runner._extract_text_from_payload(
        {"last_assistant_message": ""}
    )
    assert text == ""
    assert came_from_payload is False


def test_extract_text_from_payload_falls_back_on_missing_field() -> None:
    """Older claude-code that omits the field → fallback path."""
    text, came_from_payload = runner._extract_text_from_payload(
        {"transcript_path": "/tmp/something"}
    )
    assert text == ""
    assert came_from_payload is False


def test_extract_text_from_payload_falls_back_on_non_string() -> None:
    """Wrong type (dict, list, None, int) → fallback path, never crash."""
    for bad_value in (None, {"role": "assistant"}, ["text"], 42, True):
        text, came_from_payload = runner._extract_text_from_payload(
            {"last_assistant_message": bad_value}
        )
        assert text == ""
        assert came_from_payload is False, (
            f"non-string value {bad_value!r} must trigger fallback"
        )


def test_payload_last_assistant_message_preferred_over_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When payload has last_assistant_message, transcript is never read.

    Critical contract: even if the transcript path is bogus (would normally
    trigger Bug 4b), the run succeeds because the payload-first path
    bypasses transcript entirely.
    """
    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *args, **kwargs: json.dumps(
            {
                "transcript_path": "/nonexistent/path/that/would/bug4",
                "last_assistant_message": "PONG",
                "session_id": "test-001-7",
            }
        ),
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 100})(),
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    # Spy on the transcript reader — it must NEVER be called when payload wins.
    transcript_read_calls = []

    def spy_read(transcript: Any) -> Any:
        transcript_read_calls.append(transcript)
        return None

    monkeypatch.setattr(
        runner, "_read_last_assistant_from_transcript", spy_read
    )

    text, metadata = runner.run(
        "hi", [], verbose=False, ready_wait=0.0, timeout=1
    )
    assert text == "PONG", f"payload-first must return last_assistant_message; got {text!r}"
    assert transcript_read_calls == [], (
        f"transcript reader must NOT be called when payload wins; calls={transcript_read_calls}"
    )
    assert metadata["duration_ms"] >= 0


def test_transcript_fallback_still_works_when_payload_field_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When last_assistant_message is absent, transcript fallback executes.

    Backwards compat: ensures users on older claude-code versions still get
    a working extraction via the transcript-parsing path, including the
    Bug 4 retry window from STORY-001.6.
    """
    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    # Payload has transcript_path but NO last_assistant_message.
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *args, **kwargs: json.dumps(
            {
                "transcript_path": "/tmp/transcript-stub",
                "session_id": "test-001-7-fallback",
            }
        )
        if str(self).endswith(".json")
        else json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "fallback-OK"}],
                }
            }
        ),
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 100})(),
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    text, _metadata = runner.run(
        "hi", [], verbose=False, ready_wait=0.0, timeout=1
    )
    assert text == "fallback-OK", (
        f"transcript fallback must produce text when payload field absent; got {text!r}"
    )


# ---------------------------------------------------------------------------
# STORY-001.8 / Bug 6 — send-keys -l replaces paste-buffer for prompt delivery
# ---------------------------------------------------------------------------


def _capture_all_subprocess_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, dict[str, Any]]]:
    """Capture every ``subprocess.run`` call for full sequence assertions.

    Differs from ``_make_subprocess_capture`` which only records the FIRST
    call. STORY-001.8 unit tests need to assert on the prompt-delivery calls
    that happen AFTER new-session.
    """
    calls: list[tuple[Any, dict[str, Any]]] = []

    def fake_run(*args: Any, **kwargs: Any) -> MagicMock:
        calls.append((args, kwargs))
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        result.returncode = 0
        return result

    monkeypatch.setattr(runner, "subprocess", MagicMock(run=MagicMock(side_effect=fake_run)))
    return calls


def _drive_run_capturing_all(
    monkeypatch: pytest.MonkeyPatch, prompt: str
) -> list[tuple[Any, dict[str, Any]]]:
    """Drive ``runner.run`` to completion-or-error and return all subprocess calls."""
    calls = _capture_all_subprocess_calls(monkeypatch)
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *args, **kwargs: '{"transcript_path": "/tmp/dne", "last_assistant_message": "ok"}',
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_payload",
        lambda payload, timeout=0.0, interval=0.0: payload.exists(),
    )
    # STORY-001.8 / Bug 6 — short-circuit pane-content polling in mocked tests.
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    monkeypatch.setattr(runner, "_TRANSCRIPT_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    try:
        runner.run(prompt=prompt, extra_args=[], verbose=False, ready_wait=0.0, timeout=1)
    except RuntimeError:
        pass
    return calls


def test_prompt_uses_send_keys_literal_not_paste_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STORY-001.8 — prompt delivery uses send-keys -l, NOT set-buffer/paste-buffer.

    Asserts:
    1. NO subprocess.run call contains the argv "set-buffer".
    2. NO subprocess.run call contains the argv "paste-buffer".
    3. EXACTLY ONE call contains both "send-keys" and the literal prompt
       string with the "-l" flag.
    4. EXACTLY ONE call contains "send-keys" + "Enter" (the submit).
    """
    prompt = "What is the capital of France and one fact about it pls"
    calls = _drive_run_capturing_all(monkeypatch, prompt)

    all_argvs = [
        call_args[0] if call_args else None for call_args, _kwargs in calls
    ]
    flat = [tuple(argv) for argv in all_argvs if isinstance(argv, list)]

    set_buffer_calls = [t for t in flat if "set-buffer" in t]
    paste_buffer_calls = [t for t in flat if "paste-buffer" in t]
    literal_send_keys = [t for t in flat if "send-keys" in t and "-l" in t and prompt in t]
    enter_send_keys = [t for t in flat if "send-keys" in t and "Enter" in t]

    assert set_buffer_calls == [], (
        f"Bug 6 regression: set-buffer must NOT be called for prompt delivery; got {set_buffer_calls}"
    )
    assert paste_buffer_calls == [], (
        f"Bug 6 regression: paste-buffer must NOT be called for prompt delivery; got {paste_buffer_calls}"
    )
    assert len(literal_send_keys) == 1, (
        f"Bug 6 fix: expected exactly one 'send-keys -l <prompt>' call; got {len(literal_send_keys)}: {literal_send_keys}"
    )
    assert len(enter_send_keys) == 1, (
        f"Bug 6 fix: expected exactly one 'send-keys Enter' submit; got {len(enter_send_keys)}: {enter_send_keys}"
    )


def test_prompt_send_keys_handles_multiline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-line prompt arrives verbatim through send-keys -l.

    The TUI's input field supports multi-line input, so a newline-bearing
    prompt should be delivered as a single send-keys -l call with the
    literal newline preserved in the argv string.
    """
    multiline_prompt = "first line of prompt\nsecond line with content"
    calls = _drive_run_capturing_all(monkeypatch, multiline_prompt)

    all_argvs = [
        tuple(call_args[0]) for call_args, _kwargs in calls
        if call_args and isinstance(call_args[0], list)
    ]
    literal_calls = [t for t in all_argvs if "send-keys" in t and "-l" in t]

    assert len(literal_calls) == 1
    assert any(multiline_prompt == arg for arg in literal_calls[0]), (
        f"Multi-line prompt not preserved in argv; got: {literal_calls[0]}"
    )


def test_prompt_send_keys_handles_special_chars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Special chars (quotes, backslashes, $, accents) pass verbatim.

    The send-keys -l argument is NOT shell-interpreted by tmux — the -l flag
    treats the value as literal byte injection. The runner passes the raw
    string directly as the argv element, so no shlex.quote is needed for
    the prompt delivery itself.
    """
    # Mix of quoted phrases, backslash, dollar, double quotes, Portuguese accents.
    tricky_prompt = "echo 'hi there' \\$VAR ção é \"quoted\""
    calls = _drive_run_capturing_all(monkeypatch, tricky_prompt)

    all_argvs = [
        tuple(call_args[0]) for call_args, _kwargs in calls
        if call_args and isinstance(call_args[0], list)
    ]
    literal_calls = [t for t in all_argvs if "send-keys" in t and "-l" in t]

    assert len(literal_calls) == 1
    assert any(tricky_prompt == arg for arg in literal_calls[0]), (
        f"Special-char prompt not preserved verbatim; got: {literal_calls[0]}"
    )


# ---------------------------------------------------------------------------
# STORY-001.8 / Bug 9 — chat-title generation filter
# ---------------------------------------------------------------------------


def test_looks_like_chat_title_recognizes_known_patterns() -> None:
    """STORY-001.8 / Bug 9 — title patterns detected, real answers passed."""
    titles = [
        "Chat: Geography",
        "Test: Math Question",
        "Research: Runner.py",
        "Risk: Claude-i Dependencies",
        "Note: Something",
        "Idea: A New Feature",
        "Question: Why Sky Blue",
        "Task: Refactor",
        "Topic: Architecture",
        "Review: PR 42",
        "Analysis: Bottleneck",
        "Docs: Isolated Test Notes",  # observed prefix outside any fixed list
        "SKIP",
    ]
    for t in titles:
        assert runner._looks_like_chat_title(t) is True, f"{t!r} should be a title"

    real_answers = [
        "4",
        "Paris.",
        "Maçã.",
        "PONG",
        "The sky is blue due to Rayleigh scattering.",
        "**Atlas — Risk Assessment:**\n\nThe main risk is...",
        # Edge: colon present but NOT in leading "Word: " position.
        "Here is the answer: 42",
        "Paris. Fun fact: the Eiffel Tower grows in summer.",
        # Edge: lowercase prefix should NOT match (titles are capitalized).
        "chat: this is lowercase so not a title",
        # Edge: multi-line answer (newline present) — never a title.
        "Question: Why?\nBecause of physics.",
        # Edge: "Word: Title" shape but LONGER than the 60-char cap.
        "Summary: this is a very long sentence that exceeds the sixty char cap easily",
    ]
    for a in real_answers:
        assert runner._looks_like_chat_title(a) is False, f"{a!r} should NOT be a title"


def test_extract_text_from_payload_rejects_chat_title() -> None:
    """``_extract_text_from_payload`` returns (\"\", False) for title artifacts."""
    text, came = runner._extract_text_from_payload(
        {"last_assistant_message": "SKIP"}
    )
    assert (text, came) == ("", False)

    text, came = runner._extract_text_from_payload(
        {"last_assistant_message": "Chat: Geography"}
    )
    assert (text, came) == ("", False)

    # Real answer still extracted.
    text, came = runner._extract_text_from_payload(
        {"last_assistant_message": "Paris."}
    )
    assert (text, came) == ("Paris.", True)


def test_run_skips_chat_title_fire_and_returns_real_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """STORY-001.8 / Bug 9 — runner waits past the title fire for the real answer.

    Simulates the two-Stop-hook sequence: first payload read returns a
    title ("SKIP"), second read returns the real answer. The runner must
    loop past the title and return the real answer.
    """
    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)

    # read_text returns title first, real answer second.
    payload_reads = {"n": 0}

    def fake_read_text(self: Any, *args: Any, **kwargs: Any) -> str:
        s = str(self)
        if s.endswith(".json"):
            payload_reads["n"] += 1
            if payload_reads["n"] == 1:
                return '{"last_assistant_message": "SKIP"}'
            return '{"last_assistant_message": "the real answer"}'
        return ""

    monkeypatch.setattr(runner.Path, "read_text", fake_read_text)
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    monkeypatch.setattr(
        runner, "_wait_for_payload", lambda payload, timeout=0.0, interval=0.0: True
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    text, _metadata = runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=10)
    assert text == "the real answer", (
        f"runner must skip the SKIP title fire and return the real answer; got {text!r}"
    )
    assert payload_reads["n"] >= 2, "runner must read the payload at least twice (title then real)"


def test_run_returns_directly_when_no_title_fire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No false-positive retry: a single non-title payload returns immediately."""
    sub_mock, _captured = _make_subprocess_capture()
    monkeypatch.setattr(runner, "subprocess", MagicMock(run=sub_mock))
    monkeypatch.setattr(runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(
        runner.Path,
        "read_text",
        lambda self, *a, **kw: '{"last_assistant_message": "42"}'
        if str(self).endswith(".json") else "",
    )
    monkeypatch.setattr(runner.Path, "unlink", lambda self, *a, **kw: None)
    monkeypatch.setattr(
        runner.Path,
        "stat",
        lambda self, *a, **kw: type("_FakeStat", (), {"st_size": 42})(),
    )
    monkeypatch.setattr(
        runner, "_wait_for_payload", lambda payload, timeout=0.0, interval=0.0: True
    )
    monkeypatch.setattr(
        runner,
        "_wait_for_pane_to_contain",
        lambda session, prompt, timeout=0.0, interval=0.0: True,
    )
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _s: None)
    monkeypatch.setattr(runner, "_cleanup_stale_sentinels", lambda: None)

    text, _metadata = runner.run("hi", [], verbose=False, ready_wait=0.0, timeout=10)
    assert text == "42"
