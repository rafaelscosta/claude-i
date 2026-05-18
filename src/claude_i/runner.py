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
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import TypedDict

from claude_i import reaper
from claude_i.settings import TUI_READY_PATTERN


class RunMetadata(TypedDict):
    """Metadata returned by ``runner.run`` alongside the assistant text.

    STORY-001.5 / Task 6.4a — Gap G11 signature migration.

    ``duration_ms`` is always populated (wall time from session start to Stop
    hook fire). The cost/token fields are nullable because the Stop hook
    payload shape depends on the upstream ``claude`` version — older versions
    do not surface these. ``cli.main`` serializes the metadata when the caller
    passes ``--output-format json`` (Task 6.4 / AC-5).
    """

    duration_ms: int
    cost_usd: float | None
    tokens_in: int | None
    tokens_out: int | None

#: Env vars that must not leak into sibling subprocesses spawned by claude-i.
#: Currently only ``CLAUDE_I_SENTINEL`` — kept as a constant so future stories
#: can extend the strip-list without touching call sites.
_STRIPPED_ENV_VARS: tuple[str, ...] = ("CLAUDE_I_SENTINEL",)


def _build_metadata(
    start_time: float, hook_input: dict[str, object]
) -> RunMetadata:
    """Construct a ``RunMetadata`` from the start time and Stop hook payload.

    STORY-001.5 / Task 6.4 / Gap G11.

    ``duration_ms`` is the wall-clock time from ``runner.run`` entry to this
    helper call (i.e., to the Stop hook fire). Cost / token fields are pulled
    best-effort from the hook payload; missing fields produce ``None`` rather
    than zeros so consumers can distinguish "not reported" from "zero usage".

    Tolerated payload shapes (probed in order):
    - top-level ``cost_usd`` / ``tokens_in`` / ``tokens_out``
    - nested under ``usage`` (Claude SDK convention): ``usage.cost_usd``,
      ``usage.input_tokens``, ``usage.output_tokens``

    No type coercion beyond ``int()`` / ``float()`` casts — malformed values
    become ``None`` rather than raising.
    """
    duration_ms = int((time.monotonic() - start_time) * 1000)

    def _maybe_float(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float, str)):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    def _maybe_int(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            # ``bool`` is a subclass of ``int`` in Python; reject it explicitly
            # so a stray ``True``/``False`` in the payload doesn't become 1/0.
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, (float, str)):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return None

    raw_usage = hook_input.get("usage") if isinstance(hook_input, dict) else None
    usage: dict[str, object] = raw_usage if isinstance(raw_usage, dict) else {}

    cost = _maybe_float(hook_input.get("cost_usd")) or _maybe_float(
        usage.get("cost_usd")
    )
    tokens_in = _maybe_int(hook_input.get("tokens_in")) or _maybe_int(
        usage.get("input_tokens")
    )
    tokens_out = _maybe_int(hook_input.get("tokens_out")) or _maybe_int(
        usage.get("output_tokens")
    )
    return RunMetadata(
        duration_ms=duration_ms,
        cost_usd=cost,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


#: STORY-001.5 / Task 6.5 / Gap G17 — readiness poller default poll interval.
#: 250ms balances "responsive" (poller returns shortly after the TUI is ready)
#: against "noisy" (every poll fires a ``tmux capture-pane`` subprocess).
_READY_POLL_INTERVAL: float = 0.25


def _wait_for_tui_ready(
    session: str,
    timeout: float,
    interval: float = _READY_POLL_INTERVAL,
) -> None:
    """Block until the claude TUI in ``session`` shows a prompt indicator.

    STORY-001.5 / Task 6.5 / Gap G17 — replaces the seed's fixed
    ``time.sleep(ready_wait)``. The poller probes ``tmux capture-pane`` at
    ``interval`` seconds and returns AS SOON AS the captured pane content
    matches ``TUI_READY_PATTERN`` (ASCII ``>`` or the U+276F glyph). On
    ``timeout`` exceeded, raises ``TimeoutError("TUI did not become ready")``
    which the caller (``runner.run`` → ``cli.main``) translates to
    ``RUNTIME_ERROR``.

    Why poll: the seed's fixed sleep had two failure modes — too short (TUI
    not ready yet, prompt vanishes into the void), too long (every run pays
    the worst-case startup time even on fast machines). Polling fixes both:
    we wait exactly as long as needed, with a generous cap.

    Implementation notes:
    - ``check=False`` on the capture-pane call so a transiently-missing
      session (race during new-session startup) does not crash the poller;
      next iteration retries.
    - The regex is compiled once per call. ``TUI_READY_PATTERN`` is exposed
      via ``settings.py`` so operators can monkeypatch if upstream changes.
    - ``timeout <= 0`` returns immediately without probing — useful for
      tests that want to short-circuit the poller. Production callers
      always pass a positive timeout from ``--ready-wait``.
    """
    if timeout <= 0:
        return
    pattern = re.compile(TUI_READY_PATTERN)
    deadline = time.monotonic() + timeout
    while True:
        result = tmux("capture-pane", "-pt", session, check=False)
        if pattern.search(result.stdout):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"TUI did not become ready within {timeout}s. Likely causes:\n"
                f"  - claude binary failed to start (run `claude` interactively to test)\n"
                f"  - --ready-wait too short; try doubling it\n"
                f"  - Re-run with --verbose to watch the tmux pane"
            )
        time.sleep(interval)


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

    G13 — explicit ``encoding="utf-8"`` and ``errors="replace"`` ensure
    PT-BR accents and other multi-byte chars survive the prompt → tmux
    set-buffer round trip even on headless Linux systems where the
    default locale is ASCII. ``errors="replace"`` is best-effort: a
    truly un-encodable byte becomes ``U+FFFD`` rather than crashing the
    subprocess pipe.
    """
    return subprocess.run(
        ["tmux", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
) -> tuple[str, RunMetadata]:
    """Drive an interactive ``claude`` session via tmux and return the final
    assistant text along with run metadata.

    STORY-001.5 / Task 6.4a / Gap G11 — signature migration. Returns
    ``(text, metadata)`` instead of bare ``text``. The metadata always
    contains ``duration_ms``; ``cost_usd`` / ``tokens_in`` / ``tokens_out``
    are ``None`` when the Stop hook payload does not surface them (older
    upstream ``claude`` versions).

    Return / raise contract (STORY-001.2 / Gap G8 — AC-7, four branches):

    1. **Verified-empty assistant turn** — transcript parsed, assistant
       turn exists, but the ``content`` list yields no ``type=="text"``
       blocks. ``run()`` returns ``("", metadata)``. ``cli.main`` translates:
       exit 0 if ``--allow-empty``, otherwise exit ``RUNTIME_ERROR``.
    2. **No assistant turn found** — transcript parsed but no message with
       ``role == "assistant"``. ``run()`` raises
       ``RuntimeError("no assistant message in transcript")``.
    3. **Payload file never written** — Stop hook fired (sentinel exists)
       but ``<sentinel>.json`` is missing. ``run()`` raises
       ``RuntimeError("hook fired but no payload written")``. (Replaces
       the seed's fake-success ``return "(hook fired but no payload written)"``.)
    4. **Transcript path missing** — the payload references a transcript
       file that does not exist on disk. ``run()`` raises
       ``RuntimeError(f"transcript missing: {transcript}")``. (Replaces
       the seed's fake-success ``return f"(transcript missing: ...)"``.)

    Pre-existing branches: ``TimeoutError`` on Stop-hook timeout
    propagates to ``cli.main`` which translates to ``RUNTIME_ERROR``.
    """
    # STORY-001.5 / Task 6.4 — wall-clock timing for ``duration_ms`` in
    # ``RunMetadata``. Captured at the top so the metric covers the full
    # session lifecycle including TUI startup, prompt delivery, and the
    # Stop-hook wait. ``time.monotonic()`` is the right primitive — immune
    # to wall-clock jumps and only goes forward.
    start_time = time.monotonic()

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
        # STORY-001.5 / Task 6.5 / Gap G17 — readiness poll replaces the
        # seed's fixed ``time.sleep(ready_wait)``. ``ready_wait`` is now the
        # MAX wait, not a fixed delay; the poller returns as soon as the TUI
        # prompt indicator is detected. On poller timeout, propagate the
        # TimeoutError to cli.main → RUNTIME_ERROR.
        _wait_for_tui_ready(session, ready_wait)

        # G13 — best-effort UTF-8 round-trip check on the prompt. If the
        # string cannot be encoded in UTF-8 (extremely rare — would
        # require lone surrogates), log a warning and proceed; the
        # subprocess pipe is configured with errors="replace" so the
        # downstream call will not crash.
        try:
            prompt.encode("utf-8")
        except UnicodeEncodeError as err:
            print(
                f"claude-i: warning — prompt contains characters that "
                f"cannot be encoded as UTF-8 (will be replaced): {err}",
                file=sys.stderr,
            )

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

        # G8 — Branch 3: payload file never written. Replaces the seed's
        # fake-success return that printed an error string as if the run
        # had succeeded (then exit 0). RuntimeError signals failure to the
        # caller, which translates to RUNTIME_ERROR.
        if not payload.exists():
            raise RuntimeError("hook fired but no payload written")
        hook_input = json.loads(payload.read_text())
        transcript = Path(hook_input.get("transcript_path", ""))
        # G8 — Branch 4: transcript path missing.
        if not transcript.exists():
            raise RuntimeError(f"transcript missing: {transcript}")

        # Task 6.4 — extract optional cost/token metrics from the hook
        # payload. Field names follow the upstream Stop hook contract; when
        # absent (older claude versions), fall back to ``None`` so callers
        # can still serialize ``--output-format json`` without crashing.
        metadata = _build_metadata(start_time, hook_input)

        last: dict[str, object] | None = None
        for line in transcript.read_text().splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("message", {}).get("role") == "assistant":
                last = msg["message"]
        # G8 — Branch 2: no assistant turn was ever recorded. Distinct from
        # Branch 1 (verified-empty), where the assistant turn exists but
        # yielded no text blocks. Callers can tell them apart.
        if not last:
            raise RuntimeError("no assistant message in transcript")
        content = last.get("content", [])
        # G8 — Branch 1: verified-empty. content is not a list, OR content
        # has no type=="text" blocks → empty string return. cli.main routes
        # this through --allow-empty.
        if not isinstance(content, list):
            return "", metadata
        text = "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
        return text, metadata
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
