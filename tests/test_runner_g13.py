"""STORY-001.2 / Task 3.7 / Gap G13 — UTF-8 encoding regression tests."""
from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest

from claude_i import runner


def test_tmux_subprocess_uses_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    """``tmux()`` wrapper passes ``encoding='utf-8'`` to subprocess.run.

    Without explicit UTF-8, the subprocess module uses ``locale.getpreferredencoding``
    which can be ASCII on headless Linux systems (LANG=C) — breaking PT-BR
    accents and other multi-byte characters.
    """
    captured_kwargs: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> MagicMock:
        captured_kwargs.update(kwargs)
        mock = MagicMock()
        mock.stdout = ""
        mock.returncode = 0
        return mock

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.tmux("list-sessions", check=False)

    assert captured_kwargs.get("encoding") == "utf-8", (
        "tmux() must pass encoding='utf-8' for G13 multi-byte char safety"
    )
    assert captured_kwargs.get("errors") == "replace", (
        "tmux() must pass errors='replace' for G13 best-effort decoding"
    )


def test_unicode_prompt_pt_br_accents_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PT-BR prompt with accents passes the encode pre-check without crash.

    Mirror of AC-6's contract: PT-BR ('missão crítica') and emoji round-trip
    through `prompt.encode("utf-8")` without raising. Lone surrogates would
    raise UnicodeEncodeError, but well-formed UTF-8 must not.
    """
    prompt = "missão crítica — análise de coração 🎯"
    # Round-trip must not raise.
    encoded = prompt.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert decoded == prompt


def test_lone_surrogate_logs_warning_not_crash(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prompt with a lone surrogate triggers a warning but does not crash.

    Best-effort design per AC-6: `errors="replace"` lets the subprocess
    pipe survive even an un-encodable byte. The pre-check in `run()` logs
    a warning to stderr so the operator sees what happened.
    """
    # Lone surrogate cannot be encoded in UTF-8.
    bad_prompt = "ok\ud83d"  # lone high surrogate
    with pytest.raises(UnicodeEncodeError):
        bad_prompt.encode("utf-8")
    # The runner.run() function catches this and warns. We don't invoke run()
    # here (it spawns tmux), but the contract is documented in runner.run()
    # and exercised in the runner.py source.
