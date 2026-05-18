"""tmux session lifecycle for claude-i.

Verbatim behavioral port of ``seed/claude-i`` lines 68-160 (``tmux``,
``tail_pane``, ``run``). No hardening lives here in STORY-001.0 —
``tempfile.mktemp`` is preserved on purpose so STORY-001.2 can replace it
in a single, auditable patch (gap G5).

Forward-compat: the ``ready_wait: float`` parameter is **transitional** —
STORY-001.5 replaces it with readiness polling (gap G17). Keep the
signature as specified, but do not build features around it.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run ``tmux`` with the given args, capturing stdout/stderr as text."""
    return subprocess.run(
        ["tmux", *args],
        capture_output=True,
        text=True,
        check=check,
    )


def tail_pane(session: str, stop_event: threading.Event) -> None:
    """Stream tmux pane content to stderr until ``stop_event`` is set."""
    last = ""
    while not stop_event.is_set():
        try:
            out = tmux("capture-pane", "-pt", session, check=False).stdout
        except Exception:
            # Best-effort tail — never fatal. Any exception ends the loop.
            break
        if out != last:
            sys.stderr.write("\033[2J\033[H")  # clear + reprint pane snapshot
            sys.stderr.write(out)
            sys.stderr.flush()
            last = out
        time.sleep(0.3)


def run(
    prompt: str,
    extra_args: list[str],
    verbose: bool,
    ready_wait: float,
    timeout: int,
) -> str:
    """Drive an interactive ``claude`` session via tmux and return the final
    assistant text.

    Mirrors the seed's behavior 1:1. Hardening (secure tempfile, signal
    handlers, exit-code differentiation) lands in STORY-001.2.
    """
    # NOTE: ``tempfile.mktemp`` is deprecated and insecure. Preserved
    # intentionally for STORY-001.0 (verbatim seed behavior); STORY-001.2
    # replaces it with ``tempfile.mkstemp`` (gap G5).
    sentinel = Path(tempfile.mktemp(prefix="claude-i-", suffix=".done"))
    payload = Path(str(sentinel) + ".json")
    session = f"claude-i-{os.getpid()}"

    # Build the claude command for ``sh -c``. ``shlex.quote`` is essential —
    # naive interpolation breaks on prompts containing spaces or shell
    # metachars.
    parts = [f"CLAUDE_I_SENTINEL={shlex.quote(str(sentinel))}", "exec", "claude"]
    parts.extend(shlex.quote(a) for a in extra_args)
    claude_cmd = " ".join(parts)

    tmux(
        "new-session",
        "-d",
        "-s",
        session,
        "-x",
        "220",
        "-y",
        "50",
        "sh",
        "-c",
        claude_cmd,
    )

    tail_stop = threading.Event()
    tail_thread: threading.Thread | None = None
    if verbose:
        tail_thread = threading.Thread(
            target=tail_pane,
            args=(session, tail_stop),
            daemon=True,
        )
        tail_thread.start()

    try:
        # Let the TUI come up.
        time.sleep(ready_wait)

        # Paste the prompt (multiline-safe) and submit.
        tmux("set-buffer", "-b", session, prompt)
        tmux("paste-buffer", "-t", session, "-b", session)
        tmux("send-keys", "-t", session, "Enter")

        # Wait for Stop hook.
        deadline = time.time() + timeout
        while not sentinel.exists():
            if time.time() > deadline:
                raise TimeoutError(
                    f"No Stop hook signal after {timeout}s. Likely causes:\n"
                    f"  - Hook not yet active (run `claude` once, /hooks, acknowledge)\n"
                    f"  - TUI never received the prompt (try --ready-wait 8)\n"
                    f"  - Re-run with --verbose to watch the tmux pane"
                )
            time.sleep(0.3)

        # Parse hook payload → transcript → last assistant text.
        if not payload.exists():
            return "(hook fired but no payload written)"
        hook_input = json.loads(payload.read_text())
        transcript = Path(hook_input.get("transcript_path", ""))
        if not transcript.exists():
            return f"(transcript missing: {transcript})"

        last: dict[str, object] | None = None
        for line in transcript.read_text().splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("message", {}).get("role") == "assistant":
                last = msg["message"]
        if not last:
            return ""
        content = last.get("content", [])
        if not isinstance(content, list):
            return ""
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    finally:
        tail_stop.set()
        if tail_thread:
            tail_thread.join(timeout=1)
        # The whole point: kill-session reaps the entire process tree.
        tmux("kill-session", "-t", session, check=False)
        for p in (sentinel, payload):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
