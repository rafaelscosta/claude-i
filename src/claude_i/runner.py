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


#: STORY-001.5 / Task 6.6 / Gap G15 — sentinel staleness threshold.
#: Matches the doctor check (e) 24h window so a clean doctor PASS and an
#: in-flight runner.run() coexist without false positives.
_STALE_SENTINEL_SECONDS: float = 86400.0  # 24h


def _cleanup_stale_sentinels() -> None:
    """Delete ``<tempdir>/claude-i-*.done`` files older than 24h.

    STORY-001.5 / Task 6.6 / Gap G15. Best-effort:

    - ``stat()`` failures (symlinks, perms) silently skip the file.
    - ``unlink(missing_ok=True)`` swallows races where another claude-i
      process cleaned the file between glob and unlink.
    - Any unexpected exception is caught and ignored — this is housekeeping,
      not a control-flow gate. ``runner.run`` must NEVER fail because of
      cleanup logic.

    STORY-001.6 / Bug 2 — uses ``tempfile.gettempdir()`` instead of
    hardcoded ``/tmp`` so the cleanup actually runs on macOS, where
    ``tempfile.mkstemp()`` writes to ``$TMPDIR=/var/folders/<hash>/T/``.
    The v0.2.0 form globbed ``/tmp/`` and silently found nothing on macOS,
    letting sentinels accumulate (437 observed in production).

    Companion to ``runner.run``'s ``finally`` block which removes THIS run's
    sentinel + payload; this helper handles the orphan case where a prior
    run crashed before reaching its finally.
    """
    threshold = time.time() - _STALE_SENTINEL_SECONDS
    try:
        candidates = list(Path(tempfile.gettempdir()).glob("claude-i-*.done"))
    except Exception:
        # Glob itself failed (highly unlikely) — give up silently.
        return
    for path in candidates:
        try:
            if path.stat().st_mtime < threshold:
                path.unlink(missing_ok=True)
                # Companion payload file uses the same prefix with .json
                # tacked on. Best-effort removal — it may or may not exist.
                payload_path = Path(str(path) + ".json")
                payload_path.unlink(missing_ok=True)
        except Exception:
            # Per-file failure is silently swallowed — best-effort housekeeping.
            continue


#: STORY-001.5 / Task 6.5 / Gap G17 — readiness poller default poll interval.
#: 250ms balances "responsive" (poller returns shortly after the TUI is ready)
#: against "noisy" (every poll fires a ``tmux capture-pane`` subprocess).
_READY_POLL_INTERVAL: float = 0.25

#: STORY-001.6 / Bug 1 — grace period for the Stop hook payload to appear on
#: disk AFTER the sentinel has been touched. With the v0.2.1 atomic-rename
#: ``HOOK_CMD`` the payload should be visible the instant the sentinel is
#: touched (mv-rename is atomic on POSIX), but we keep a small grace as
#: defense-in-depth for filesystems where cross-process stat() visibility
#: lags. 2s is generous; production observations show <100ms.
_PAYLOAD_GRACE_SECONDS: float = 2.0
_PAYLOAD_POLL_INTERVAL: float = 0.05

#: STORY-001.6 / Bug 4 — Claude Code 2.1.143 sometimes fires the Stop hook
#: BEFORE the final assistant turn is flushed to the transcript JSONL file.
#: The runner polls the transcript for the assistant message with this
#: deadline. 10s covers observed flushes (sub-second in practice) without
#: starving short prompts that legitimately produce no assistant turn.
_TRANSCRIPT_RETRY_SECONDS: float = 10.0
_TRANSCRIPT_POLL_INTERVAL: float = 0.2


#: Literal strings claude-code emits on the title pass for prompts that
#: do not lend themselves to a title (e.g. literal "SKIP" for very short
#: math answers, "PONG"-style replies in some sessions).
_CHAT_TITLE_LITERALS: frozenset[str] = frozenset({"SKIP"})

#: STORY-001.8 / Bug 9 — generic chat-title shape. claude-code 2.1.143 fires
#: the Stop hook TWICE per prompt: once with a title-generation artifact and
#: once with the real response. Titles follow a stable shape:
#:   ``<CapitalizedWord>: <Title Case short phrase>``
#: on a SINGLE line. Observed prefixes are open-ended ("Chat:", "Test:",
#: "Research:", "Risk:", "Docs:", "Analysis:", ...) so a fixed prefix list is
#: whack-a-mole. Instead we match the generic shape with two guards that keep
#: false positives near-zero:
#:   1. single line (no newline) — real multi-paragraph answers have newlines
#:   2. short (<= 60 chars) — titles are terse; real answers rarely are AND
#:      rarely start with "Word: ".
#: The leading token is a single capitalized word followed by ": " and then a
#: capital letter (Title Case). Real answers like "Paris. Fun fact: ..." do
#: not match (they don't START with "Word: "). Markdown answers like
#: "**Atlas ..." do not match (start with "*", not a capital letter).
_CHAT_TITLE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*: [A-Z][^\n]*$")
_CHAT_TITLE_MAX_LEN: int = 60


def _looks_like_chat_title(text: str) -> bool:
    """Return True when ``text`` is a claude-code title-generation artifact.

    STORY-001.8 / Bug 9 — discovered 2026-05-19 via empirical multi-Stop-hook
    observation. claude-code 2.1.143 fires the Stop hook TWICE per prompt:
    once with a chat-title hint (or literal ``"SKIP"``) and once with the
    actual response. The payload-first path must filter the title fire to
    return the real assistant response.

    Title examples observed empirically (2026-05-19/20):
    ``"SKIP"``, ``"Chat: Geography"``, ``"Test: Math Question"``,
    ``"Risk: Claude-i Dependencies"``, ``"Research: Runner.py"``,
    ``"Docs: Isolated Test Notes"``, ``"Risk: Claude-i Dependencies"``.

    Real responses that must NOT match: ``"4"``, ``"Paris."``, ``"Maçã."``,
    ``"PONG"``, ``"Paris. Fun fact: the Eiffel Tower ..."`` (colon present but
    not in "Word: " leading position), ``"**Atlas — Risk: ..."`` (markdown),
    multi-line answers (newline present).

    Detection: literal SKIP, OR the generic ``<Word>: <Title>`` single-line
    shape under ``_CHAT_TITLE_MAX_LEN`` chars. The predicate errs toward
    recall — a false positive costs one extra Stop-hook wait, not data loss
    (the next fire brings the real answer or the same title; the transcript
    fallback still eventually returns the right answer).
    """
    if text in _CHAT_TITLE_LITERALS:
        return True
    if len(text) > _CHAT_TITLE_MAX_LEN:
        return False
    return bool(_CHAT_TITLE_RE.match(text))


#: How long to wait for the SECOND Stop hook fire when the FIRST one
#: was a chat-title. claude-code 2.1.143 has been observed firing the
#: real-response Stop hook 5-15s after the title fire; 30s is generous
#: cap to absorb burst-load slowness without starving genuine timeouts.
_CHAT_TITLE_RETRY_SECONDS: float = 30.0


def _extract_text_from_payload(hook_input: dict[str, object]) -> tuple[str, bool]:
    """Return the assistant response from ``payload["last_assistant_message"]``.

    STORY-001.7 / Bug 4 elimination. Claude Code 2.1.143+ writes the full
    final assistant response to ``last_assistant_message`` in the Stop hook
    payload. When this field is present and is a non-empty string, the
    transcript JSONL is no longer needed — and reading it is unreliable
    because the file may not be flushed yet (Bug 4a) or may never exist
    at all (Bug 4b, observed in ~60% of test runs).

    Returns ``(text, came_from_payload)``:
    - ``came_from_payload=True`` means the caller should USE ``text`` and
      skip the transcript-parsing fallback. ``text`` is guaranteed to be
      a non-empty string in this case.
    - ``came_from_payload=False`` means the field was absent, ``None``, or
      not a non-empty string (incl. empty string — see Dev Notes in the
      story). The caller should fall back to parsing the transcript JSONL.

    Why not accept empty strings? Because an empty ``last_assistant_message``
    could be either (1) older claude-code that uses ``""`` as a default
    sentinel for "field not populated", or (2) a genuine verified-empty
    assistant turn. The fallback path can distinguish these cases via the
    JSONL ``content`` array; payload alone cannot. Falling back is safer.
    """
    value = hook_input.get("last_assistant_message")
    if isinstance(value, str) and value:
        # STORY-001.8 / Bug 9 — filter chat-title generation artifacts.
        if _looks_like_chat_title(value):
            return "", False
        return value, True
    return "", False


def _read_last_assistant_from_transcript(
    transcript: Path,
) -> dict[str, object] | None:
    """Return the last ``role == "assistant"`` message from a transcript JSONL.

    STORY-001.6 / Bug 4 — helper for the transcript-retry loop in ``run()``.
    Returns ``None`` when the transcript has no assistant message yet (so the
    caller can retry) or when the file vanished between checks. Malformed
    JSON lines are skipped silently (matches the seed's tolerant parse).
    """
    try:
        text = transcript.read_text()
    except (OSError, FileNotFoundError):
        return None
    last: dict[str, object] | None = None
    for line in text.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("message", {}).get("role") == "assistant":
            last = msg["message"]
    return last


#: STORY-001.8 / Bug 6 — pane-content confirmation poll defaults.
#:
#: After ``send-keys -l <prompt>``, the prompt keystrokes flow into the TUI
#: asynchronously. We poll ``tmux capture-pane`` until the prompt is visibly
#: present, then dispatch Enter. ``timeout`` caps the wait; in production
#: observation, even long prompts arrive in <200ms.
_PROMPT_VISIBLE_TIMEOUT: float = 10.0
_PROMPT_VISIBLE_INTERVAL: float = 0.05
#: How many trailing characters of the prompt must appear in the pane to
#: confirm landing. Suffix-match (vs full-match) is robust to:
#:   - TUI line wrapping (long prompts wrap; full-string match fails on
#:     wrapped output even when the prompt is present).
#:   - Newlines in the prompt (each line rendered separately).
#:   - Leading whitespace stripping by some terminals.
#: 24 chars is enough to be confident the full prompt arrived without
#: requiring the full match. For prompts shorter than 24 chars, the helper
#: uses the entire prompt as the suffix.
_PROMPT_VISIBLE_SUFFIX_LEN: int = 24


def _wait_for_pane_to_contain(
    session: str,
    prompt: str,
    timeout: float = _PROMPT_VISIBLE_TIMEOUT,
    interval: float = _PROMPT_VISIBLE_INTERVAL,
) -> bool:
    """Block until a recognizable suffix of ``prompt`` appears in the tmux pane.

    STORY-001.8 / Bug 6 — companion to the ``send-keys -l`` prompt delivery.
    Returns True when the prompt's trailing ``_PROMPT_VISIBLE_SUFFIX_LEN``
    characters are observed via ``tmux capture-pane``, False on timeout.

    Why suffix-matching: ``tmux capture-pane`` returns the pane content with
    line wrapping applied by the terminal renderer. A 100-char prompt may
    show across 2-3 visual rows separated by spaces — a substring match on
    the full prompt fails even when the prompt is fully present. The
    trailing N chars (after the last newline in the prompt, if any) are
    almost always rendered on one row, so a substring match on those is
    reliable.

    Best-effort: returns False on timeout but does NOT raise. The caller
    (``runner.run``) treats False as "submit anyway and hope for the best"
    — the orthogonal Bug 5 retry safety net still applies if the submit
    silently failed.
    """
    if not prompt:
        return True
    # Use the last logical line of the prompt for suffix matching — multiline
    # prompts render the lines separately and we only need to confirm the last
    # one landed (the others necessarily landed before).
    last_line = prompt.splitlines()[-1] if "\n" in prompt else prompt
    needle = last_line[-_PROMPT_VISIBLE_SUFFIX_LEN:] if len(last_line) > _PROMPT_VISIBLE_SUFFIX_LEN else last_line
    if timeout <= 0:
        result = tmux("capture-pane", "-pt", session, check=False)
        return needle in result.stdout
    deadline = time.monotonic() + timeout
    while True:
        result = tmux("capture-pane", "-pt", session, check=False)
        if needle in result.stdout:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def _wait_for_payload(
    payload: Path,
    timeout: float = _PAYLOAD_GRACE_SECONDS,
    interval: float = _PAYLOAD_POLL_INTERVAL,
) -> bool:
    """Block up to ``timeout`` seconds for ``payload`` to appear on disk.

    STORY-001.6 / Bug 1 — companion to the sentinel-watch loop in
    ``runner.run``. Once the sentinel exists, this helper polls for the
    payload file. Returns True on success, False on grace exhaustion.

    The caller decides what to do with False (typically raise
    ``RuntimeError("hook fired but no payload written")``). Caller-side
    raise (instead of in-helper) keeps the "what to raise" decision next
    to the surrounding 4-branch contract docstring.

    ``timeout <= 0`` short-circuits: returns ``payload.exists()`` immediately.
    """
    if timeout <= 0:
        return payload.exists()
    deadline = time.monotonic() + timeout
    while True:
        if payload.exists():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


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

    STORY-001.7 / Bug 4 elimination — payload-first response extraction.
    When the Stop hook payload contains a non-empty
    ``last_assistant_message`` field (Claude Code 2.1.143+), the runner
    uses that value directly and SKIPS the transcript JSONL read
    entirely. This bypasses both Bug 4a (transcript flush race) and Bug
    4b (transcript file never written) for the vast majority of runs.
    The transcript-parsing fallback is preserved for older claude-code
    versions and the verified-empty (Branch 1) case.

    Return / raise contract (STORY-001.2 / Gap G8 — AC-7, four branches):

    1. **Verified-empty assistant turn** — transcript parsed, assistant
       turn exists, but the ``content`` list yields no ``type=="text"``
       blocks. ``run()`` returns ``("", metadata)``. ``cli.main`` translates:
       exit 0 if ``--allow-empty``, otherwise exit ``RUNTIME_ERROR``.
    2. **No assistant turn found** — transcript parsed but no message with
       ``role == "assistant"``. ``run()`` raises
       ``RuntimeError("no assistant message in transcript")``.
    3. **Payload file never written** — Stop hook fired (sentinel exists)
       but ``<sentinel>.json`` is missing AFTER the STORY-001.6 grace period
       (2s, polled at 50ms). ``run()`` raises ``RuntimeError("hook fired
       but no payload written")``. (Replaces the seed's fake-success
       ``return "(hook fired but no payload written)"``.) The v0.2.1
       atomic-rename ``HOOK_CMD`` should make this branch unreachable in
       practice; the grace + raise remain as defense-in-depth.
    3b. **Payload empty** — payload file exists but is 0 bytes (e.g. the
       hook's ``cat`` ran with closed stdin and produced no content).
       ``run()`` raises ``RuntimeError("hook fired but payload empty")``
       — a friendlier surface than the bare ``JSONDecodeError`` that
       ``json.loads("")`` would otherwise propagate to ``cli.main``.
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

    # STORY-001.5 / Task 6.6 / Gap G15 — best-effort cleanup of stale
    # sentinel files left behind by prior crashed / SIGKILLed claude-i runs.
    # Runs before any new mkstemp to ensure /tmp stays tidy on systems
    # without aggressive tmpfs cleanup. Errors are silenced — this is a
    # housekeeping nicety, never blocking.
    _cleanup_stale_sentinels()

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

    # STORY-001.6 / Bug 1 — REAL ROOT CAUSE: the v0.2.0 code waited for
    # ``sentinel.exists()`` to become True, BUT ``mkstemp`` already created
    # the sentinel above. The wait loop exited immediately, BEFORE the Stop
    # hook ever fired, then raised "hook fired but no payload written"
    # because the payload truly had not been written yet. The handoff
    # diagnosed this as a touch/cat race; empirically it is a sentinel-
    # already-existed bug masked by accident-of-timing.
    #
    # Fix: unlink the sentinel here so the wait loop's ``not sentinel.exists()``
    # is True until the hook re-touches it. We only need the PATH from
    # mkstemp (claim-and-release pattern); the atomicity of mkstemp still
    # protects us from another process claiming the same name in the
    # microsecond between unlink and the hook's touch — that race is now
    # extremely unlikely (mkstemp uses unique random suffixes) and would
    # at worst cause a TimeoutError, never a fake-success.
    sentinel.unlink(missing_ok=True)

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

        # STORY-001.8 / Bug 6 — Deliver the prompt via ``send-keys -l`` + a
        # pane-content confirmation poll + ``send-keys Enter``. Together these
        # three steps eliminate the paste/Enter race that made any prompt
        # longer than ~40 chars silently no-op on v0.2.2.
        #
        # The seed's paste-buffer mechanism is asynchronous from the TUI's
        # point of view: bytes flow into ``claude``'s input field over multiple
        # frames. ``send-keys -l`` improves on paste-buffer because each
        # character is a discrete keystroke event, but it is STILL async — for
        # long prompts the final keystroke can arrive at the input field after
        # ``send-keys Enter`` is dispatched. Result: Enter is interpreted
        # against a partial buffer → silent no-op, claude stays ``AGT idle``,
        # Stop hook never fires.
        #
        # Defense: ``_wait_for_pane_to_contain`` polls ``tmux capture-pane``
        # until a recognizable suffix of the prompt appears inside the input
        # area. Only then do we dispatch Enter. The suffix-matching strategy
        # is robust against TUI wrapping (long prompts get visually wrapped
        # across multiple display rows) — we just need to see the last few
        # chars on screen, which proves the full prompt landed in the input
        # field.
        tmux("send-keys", "-t", session, "-l", prompt)
        _wait_for_pane_to_contain(session, prompt, timeout=10.0)
        tmux("send-keys", "-t", session, "Enter")

        # STORY-001.8 / Bug 9 — Wait for the Stop hook + filter chat-title
        # generation fires. claude-code 2.1.143 fires the Stop hook TWICE
        # per prompt: once with a title hint (``"Chat: X"``, ``"SKIP"``,
        # etc.) and once with the real response. We loop until we see a
        # NON-title payload or the user-supplied ``timeout`` is exhausted.
        deadline = time.time() + timeout
        hook_input: dict[str, object] | None = None
        title_fires_observed = 0
        while True:
            # Wait for sentinel to be touched.
            while not sentinel.exists():
                if time.time() > deadline:
                    raise TimeoutError(
                        f"No Stop hook signal after {timeout}s. Likely causes:\n"
                        f"  - Hook not yet active (run `claude` once, /hooks, acknowledge)\n"
                        f"  - TUI never received the prompt (try --ready-wait 8)\n"
                        f"  - Re-run with --verbose to watch the tmux pane"
                    )
                time.sleep(0.3)

            # G8 — Branch 3: payload file never written.
            # STORY-001.6 / Bug 1 — 2s grace via _wait_for_payload.
            if not _wait_for_payload(payload):
                raise RuntimeError("hook fired but no payload written")
            # STORY-001.6 / Branch 3b — empty payload guard.
            if payload.stat().st_size == 0:
                raise RuntimeError("hook fired but payload empty")

            candidate = json.loads(payload.read_text())
            candidate_msg = candidate.get("last_assistant_message")
            if isinstance(candidate_msg, str) and _looks_like_chat_title(candidate_msg):
                # STORY-001.8 / Bug 9 — title fire. Clear sentinel+payload
                # and continue polling for the next Stop hook. The
                # remaining ``timeout`` budget covers both the current and
                # the upcoming real-response fire.
                title_fires_observed += 1
                # Reset sentinel + payload so the inner while-loop blocks
                # again until claude-code re-touches them.
                for p in (sentinel, payload):
                    try:
                        p.unlink()
                    except FileNotFoundError:
                        pass
                # Cap how long we tolerate consecutive title fires. After
                # _CHAT_TITLE_RETRY_SECONDS without seeing a real response,
                # fall through with what we have (the title) — better to
                # surface a bizarre but real value than to spin forever.
                if title_fires_observed * _CHAT_TITLE_RETRY_SECONDS > _CHAT_TITLE_RETRY_SECONDS * 2:
                    hook_input = candidate
                    break
                continue

            hook_input = candidate
            break

        # The loop only exits via ``break`` with ``hook_input`` set (or by
        # raising). This assert narrows the type for mypy and documents the
        # invariant.
        assert hook_input is not None

        # Task 6.4 — extract optional cost/token metrics from the hook
        # payload. Field names follow the upstream Stop hook contract; when
        # absent (older claude versions), fall back to ``None`` so callers
        # can still serialize ``--output-format json`` without crashing.
        metadata = _build_metadata(start_time, hook_input)

        # STORY-001.7 / Bug 4 ELIMINATION — payload-first response extraction.
        # STORY-001.8 / Bug 9 — _extract_text_from_payload also filters
        # title patterns as a belt-and-suspenders defense; the wait loop
        # above already drops them but the helper rejecting titles makes
        # the contract obvious at the call site.
        text_from_payload, came_from_payload = _extract_text_from_payload(hook_input)
        if came_from_payload:
            return text_from_payload, metadata

        # Fallback path — older claude-code versions, or empty
        # ``last_assistant_message``. Parse the transcript JSONL the v0.2.1
        # way (with Bug 4 retry as defense-in-depth) to preserve backwards
        # compatibility and the verified-empty branch semantics.
        transcript = Path(str(hook_input.get("transcript_path", "")))
        # G8 — Branch 4: transcript path missing.
        #
        # STORY-001.6 / Bug 4 mitigation (still relevant on the fallback
        # path) — poll for the transcript file within the retry window
        # before declaring it truly missing.
        if not transcript.exists():
            transcript_deadline = time.time() + _TRANSCRIPT_RETRY_SECONDS
            while not transcript.exists() and time.time() < transcript_deadline:
                time.sleep(_TRANSCRIPT_POLL_INTERVAL)
        if not transcript.exists():
            raise RuntimeError(f"transcript missing: {transcript}")

        # STORY-001.6 / Bug 4 retry on assistant-message-not-flushed-yet.
        last = _read_last_assistant_from_transcript(transcript)
        transcript_deadline = time.time() + _TRANSCRIPT_RETRY_SECONDS
        while last is None and time.time() < transcript_deadline:
            time.sleep(_TRANSCRIPT_POLL_INTERVAL)
            last = _read_last_assistant_from_transcript(transcript)
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
