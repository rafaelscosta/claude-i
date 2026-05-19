"""End-to-end integration tests for ``claude-i`` — NOT mocked.

STORY-001.6 / AC-5 — opt-in suite that drives the real ``claude`` binary
through a real ``tmux`` session via the real Stop hook. This is the test
that closes the gap which hid Bug 1 (touch/cat race) for the entire EPIC-001
mocked suite (89 tests) — those tests stub ``Path.exists`` / ``subprocess.run``
and therefore could not detect a real race between the sentinel touch and
the payload write.

This file is gated on THREE conditions; all three must hold or the test is
skipped:

1. ``shutil.which("tmux")`` must succeed.
2. ``shutil.which("claude")`` must succeed.
3. ``os.environ.get("CLAUDE_I_RUN_INTEGRATION") == "1"``.

The env-var gate keeps ``pytest tests/`` fast for normal development. CI
workflows do NOT set the var by default (so CI without ``claude`` installed
still passes). Local opt-in:

    CLAUDE_I_RUN_INTEGRATION=1 pytest tests/test_integration_e2e.py -v

The subprocess invocation passes ``CLAUDE_I_AUTO_INSTALL_HOOK=1`` through
the env so the Bug 3 fix auto-installs the Stop hook on first run without
prompting (subprocess.run inherits no TTY).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _skip_unless_runnable() -> None:
    """Raise ``pytest.skip`` if integration prerequisites are not met."""
    if os.environ.get("CLAUDE_I_RUN_INTEGRATION") != "1":
        pytest.skip("opt-in: set CLAUDE_I_RUN_INTEGRATION=1 to run")
    if shutil.which("tmux") is None:
        pytest.skip("tmux not on PATH")
    if shutil.which("claude") is None:
        pytest.skip("claude not on PATH")


def _claude_i_entrypoint() -> str:
    """Return the path to a runnable ``claude-i`` binary for this Python env.

    Prefers the entrypoint installed in this venv's ``bin/`` directory so the
    test does not depend on the user's PATH ordering. Falls back to whatever
    ``shutil.which("claude-i")`` finds.
    """
    venv_bin = Path(sys.executable).parent / "claude-i"
    if venv_bin.exists():
        return str(venv_bin)
    found = shutil.which("claude-i")
    if found is None:
        pytest.skip("claude-i not installed in this venv or on PATH")
    return found


#: Max retries for the E2E test. Claude Code 2.1.143 occasionally takes
#: >10s to flush the transcript JSONL after the Stop hook fires (Bug 4 in
#: STORY-001.6). The runner already retries internally; the test retries at
#: a higher level so a single transient flake does not fail CI without
#: hiding a real Bug 1 regression — failure of ALL retries is still a hard
#: assertion failure with full diagnostic output.
_E2E_RETRIES: int = 3


def _run_claude_i_once(entrypoint: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Single subprocess invocation. Helper for the retry loop in the test."""
    return subprocess.run(
        [
            entrypoint,
            "--timeout",
            "90",
            "--ready-wait",
            "25",
            "Reply with the word PONG, nothing else.",
        ],
        capture_output=True,
        text=True,
        timeout=120,  # outer guard: pytest hangs no longer than 120s on a wedge
        env=env,
    )


def test_e2e_simple_prompt_returns_text() -> None:
    """Real E2E — claude-i with a trivial prompt returns non-empty assistant text.

    The simplest possible smoke: ask the model to reply with one short token,
    bound the run with tight timeouts, and assert that stdout contains
    SOMETHING. We deliberately do NOT assert specific content because the
    model can rephrase; the point is that the full pipeline
    (claude-i → tmux → claude → Stop hook → payload → transcript → stdout)
    completes without hitting any of the 3 bugs.

    Retries up to 3 times to absorb Bug 4 flakiness (Claude Code 2.1.143
    transcript-flush race). A SINGLE pass within retries is enough to
    declare success — but Bug 1 / Bug 3b regression checks are evaluated on
    EVERY attempt so they catch the regression even when retries succeed.

    Asserts (per attempt):
        - stderr does NOT contain "hook fired but no payload written"  (Bug 1)
        - stderr does NOT contain "hook fired but payload empty"       (Bug 3b)

    Asserts (after retries):
        - At least one attempt returned exit 0 and non-empty stdout.
    """
    _skip_unless_runnable()
    entrypoint = _claude_i_entrypoint()
    env = os.environ.copy()
    # STORY-001.6 / Bug 3 — auto-install the Stop hook if missing so the
    # subprocess does not crash with EOFError on no-TTY stdin.
    env["CLAUDE_I_AUTO_INSTALL_HOOK"] = "1"

    attempts: list[subprocess.CompletedProcess[str]] = []
    for attempt in range(1, _E2E_RETRIES + 1):
        result = _run_claude_i_once(entrypoint, env)
        attempts.append(result)

        # Bug 1 / Bug 3b regression checks run EVERY attempt — if the race
        # were back the test would fail loudly instead of being absorbed.
        assert "hook fired but no payload written" not in result.stderr, (
            f"Bug 1 regression on attempt {attempt}: Stop hook race detected.\n"
            f"stderr:\n{result.stderr}"
        )
        assert "hook fired but payload empty" not in result.stderr, (
            f"Bug 1/3b regression on attempt {attempt}: empty payload detected.\n"
            f"stderr:\n{result.stderr}"
        )

        if result.returncode == 0 and result.stdout.strip():
            return  # success — bail out of retry loop

    # All retries exhausted without a green run.
    report = "\n\n".join(
        f"--- attempt {i + 1} (rc={a.returncode}) ---\n"
        f"stdout: {a.stdout!r}\n"
        f"stderr: {a.stderr[:500]}"
        for i, a in enumerate(attempts)
    )
    raise AssertionError(
        f"claude-i E2E failed all {_E2E_RETRIES} attempts:\n{report}"
    )
