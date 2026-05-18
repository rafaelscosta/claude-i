"""tmux session lifecycle for claude-i.

Verbatim behavioral port of ``seed/claude-i`` lines 68-160 (``tmux``,
``tail_pane``, ``run``), with STORY-001.1 G4 env-isolation layered on top.

Forward-compat: the ``ready_wait: float`` parameter is **transitional** —
STORY-001.5 replaces it with readiness polling (gap G17). Keep the
signature as specified, but do not build features around it.

G4 — env-isolation contract (two layers, both required):

1. **Delivery to sub-claude:** the ``CLAUDE_I_SENTINEL=<path>`` shell prefix
   inside ``claude_cmd`` is the ONLY mechanism that gets the sentinel value
   to the Stop hook's shell guard (``if [ -n "$CLAUDE_I_SENTINEL" ]``). It
   must be preserved verbatim — removing it breaks the hook → sentinel file
   never written → ``run()`` times out → entire pipeline broken.
2. **Isolation from sibling subprocesses:** the ``env`` kwarg passed to
   ``subprocess.run`` for the tmux-spawning call is sanitized via
   ``_sanitized_env()`` so ``CLAUDE_I_SENTINEL`` cannot bleed into Python-side
   sibling processes (claude-i never sets it in its own ``os.environ``, but
   we strip defensively so the guarantee holds even if a caller does).

These solve different problems and are NOT redundant. The test contract in
``tests/test_runner.py`` asserts both: ``CLAUDE_I_SENTINEL`` is absent from
the captured ``env`` kwarg AND the ``sh -c`` argument string still begins
with ``CLAUDE_I_SENTINEL=``.

STORY-001.2 hardens this module further:
- G5: ``tempfile.mktemp`` → ``tempfile.mkstemp`` (atomic, secure)
- G6: ``reaper.register_cleanup`` wired after ``new-session`` succeeds
- G8: parse-failure branches raise ``RuntimeError`` instead of returning
  fake-success strings; caller (``cli.main``) translates to exit codes
- G13: explicit UTF-8 encoding for prompt delivery and subprocess I/O
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

from claude_i import reaper

#: Env vars that must not leak into sibling subprocesses spawned by claude-i.
#: Currently only ``CLAUDE_I_SENTINEL`` — kept as a constant so future stories
#: can extend the strip-list without touching call sites.
_STRIPPED_ENV_VARS: tuple[str, ...] = ("CLAUDE_I_SENTINEL",)


def _sanitized_env() -> dict[str, str]:
    """Return a copy of ``os.environ`` with the G4 strip-list removed.

    Defensive: ``CLAUDE_I_SENTINEL`` is set INSIDE the ``sh -c`` argument
    string (see ``run()`` below), not in claude-i's own environment. So under
    normal operation the strip is a no-op. We do it anyway so the guarantee
    holds even if a future caller (or a test) sets the var on
    ``os.environ``. The strip-list is the single source of truth.
    """
    return {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV_VARS}


def tmux(
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``tmux`` with the given args, capturing stdout/stderr as text.

    ``env`` is passed through to ``subprocess.run`` unchanged. When ``None``
    (the default), the child inherits ``os.environ`` — appropriate for the
    read-side tmux calls (capture-pane, set-buffer, paste-buffer, send-keys,
    kill-session) where leaking env vars is harmless because they spawn
    short-lived tmux client processes, not the sub-claude.

    The single call site that MUST pass ``env=_sanitized_env()`` is the
    ``new-session`` call in ``run()`` — that is the only path that spawns
    a long-lived process tree underneath claude-i. See module docstring.
    """
    return subprocess.run(
        ["tmux", *args],
        capture_output=True,
        text=True,
        check=check,
        env=env,
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
    # G5 — ``tempfile.mkstemp`` is atomic (create+open) and avoids the TOCTOU
    # race that ``tempfile.mktemp`` exposes. The fd is closed immediately
    # because the hook (not claude-i) writes the ``.json`` payload — we only
    # need the path. The companion payload path is still derived by string
    # concatenation; that is safe because the hook also creates it via
    # ``cat > "$CLAUDE_I_SENTINEL.json"`` after the sentinel exists.
    fd, sentinel_str = tempfile.mkstemp(prefix="claude-i-", suffix=".done")
    os.close(fd)
    sentinel = Path(sentinel_str)
    payload = Path(str(sentinel) + ".json")
    session = f"claude-i-{os.getpid()}"

    # Build the claude command for ``sh -c``. ``shlex.quote`` is essential —
    # naive interpolation breaks on prompts containing spaces or shell
    # metachars.
    parts = [f"CLAUDE_I_SENTINEL={shlex.quote(str(sentinel))}", "exec", "claude"]
    parts.extend(shlex.quote(a) for a in extra_args)
    claude_cmd = " ".join(parts)

    # G4 — Layer 2: pass a sanitized env to THIS call only. The sentinel
    # value is still delivered to the sub-claude via the explicit shell
    # prefix inside ``claude_cmd`` above (Layer 1). Stripping it from ``env``
    # ensures the var cannot leak into any future Python-side sibling
    # subprocess that this module spawns.
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
        env=_sanitized_env(),
    )

    # G6 — register an atexit + SIGTERM handler to tear down ``session`` even
    # when the ``finally`` block below is bypassed (abrupt exit, signal).
    # The ``finally`` cleanup remains in place (belt-and-suspenders).
    # SIGKILL is best-effort only and cannot be intercepted — see ``--help``.
    reaper.register_cleanup(session)

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
