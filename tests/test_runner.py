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
    # time.sleep should be a no-op so the test runs fast.
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    # G6 — silence reaper registration so test runs don't install a real
    # SIGTERM handler in the process. The G6 test suite verifies wiring
    # explicitly; here we just need run() to succeed.
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _session: None)

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
    monkeypatch.setattr(runner.time, "sleep", lambda *_a, **_kw: None)
    # G6 — silence reaper registration (see _drive helper).
    monkeypatch.setattr(runner.reaper, "register_cleanup", lambda _session: None)

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
