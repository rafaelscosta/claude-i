"""Stop-hook installer for claude-i.

Behavioral port of ``seed/claude-i`` lines 26-65 with STORY-001.1 G2 hardening
layered on top:

- ``hook_installed()`` does a structural check (correct group shape + correct
  command string) rather than a loose substring compare. This catches legacy
  malformed entries that the seed's check would have treated as valid.
- ``install_hook()`` APPENDS to the existing ``Stop`` list, preserving any
  pre-existing hooks from other tools.

G2 matcher field — investigation outcome (see ``NOTES.md`` → "Hook Matcher
Support"): ``matcher`` is a tool-name regex for ``PreToolUse`` /
``PostToolUse`` hooks. ``Stop`` is session-level and has no documented
``matcher`` field. We rely on the existing shell guard
(``if [ -n "$CLAUDE_I_SENTINEL" ]``) inside ``HOOK_CMD`` for isolation —
that has always been the working mechanism in the seed and remains
sufficient. AC-5's fallback clause covers this.

STORY-001.2 / Task 3.4 / Gap G7: ``install_hook`` now acquires an exclusive
``fcntl.flock`` on a sibling lock file before mutating ``settings.json``.
``fcntl`` is POSIX-only; the conditional import lets the module load on
Windows even though ``assert_not_windows()`` blocks reaching the install
path. If the lock cannot be acquired within 5 seconds, claude-i exits.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from claude_i.settings import HOOK_CMD, SETTINGS, load_settings, write_settings

# G7 — fcntl is POSIX-only. On Windows, ``assert_not_windows()`` exits at
# startup so this code path is unreachable; the conditional import keeps the
# module loadable for static analysis and import-only smoke tests.
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:  # pragma: no cover — Windows fallback
    fcntl = None  # type: ignore[assignment]
    HAS_FCNTL = False

# G7 — advisory lock for settings.json mutation. We lock a sibling file
# (settings.json.lock) rather than the settings file itself so an aborted
# lock acquire never partially-truncates the settings on a flock(LOCK_EX|O_CREAT)
# race. Acquire is non-blocking with retry (max 5s, 100ms sleep).
_LOCK_TIMEOUT_SECONDS: float = 5.0
_LOCK_RETRY_INTERVAL: float = 0.1


def _is_claude_i_hook_entry(entry: dict[str, Any]) -> bool:
    """Return True when ``entry`` is a well-formed claude-i Stop-hook leaf.

    A correct entry has ``type == "command"`` and ``command == HOOK_CMD``.
    The seed's looser check (``command == HOOK_CMD`` only) would mis-classify
    an entry with the right command string but a different ``type`` (e.g.
    ``http``) as installed; we tighten that.
    """
    return entry.get("type") == "command" and entry.get("command") == HOOK_CMD


def hook_installed() -> bool:
    """Return ``True`` when the Stop hook is already present in settings.

    Safe against a missing or malformed settings file: returns ``False``
    rather than raising. Looks specifically for a well-formed claude-i
    hook entry (correct ``type`` AND correct ``command``), not just any
    entry whose command happens to match.

    G2: the ``matcher`` field at the group level is NOT checked here
    because ``Stop`` hooks have no documented ``matcher`` schema (see
    ``NOTES.md``). Future stories may extend this check when / if
    Anthropic publishes a Stop-event matcher format.
    """
    if not SETTINGS.exists():
        return False
    try:
        cfg = load_settings()
    except json.JSONDecodeError:
        return False
    stop_groups = cfg.get("hooks", {}).get("Stop", [])
    if not isinstance(stop_groups, list):
        return False
    for group in stop_groups:
        if not isinstance(group, dict):
            continue
        leaves = group.get("hooks", [])
        if not isinstance(leaves, list):
            continue
        for entry in leaves:
            if isinstance(entry, dict) and _is_claude_i_hook_entry(entry):
                return True
    return False


def _acquire_lock_with_retry() -> Any | None:
    """Acquire an exclusive flock on the settings-sibling lock file.

    Returns the open lock-file handle (a real file object — we MUST keep it
    alive until release; ``fcntl`` locks the underlying kernel fd, and the
    Python wrapper closes the fd when GC'd, which releases the lock).

    Returns ``None`` when ``fcntl`` is not available (Windows; unreachable
    when ``assert_not_windows()`` runs first). Exits the process when the
    lock cannot be acquired within ``_LOCK_TIMEOUT_SECONDS``.

    The lock file lives at ``SETTINGS.parent / "claude-i.lock"``. We never
    lock the settings file directly — that would risk truncating it on a
    racy open with ``O_CREAT``.
    """
    if not HAS_FCNTL:
        # Unreachable on supported platforms; assert_not_windows() exits
        # before any hook code runs on Windows.
        return None

    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    lock_path = SETTINGS.parent / "claude-i.lock"

    # Open the lock file in append mode (creates if missing) — we never
    # write to it, only flock the fd. Caller keeps the handle alive until
    # _release_lock runs.
    assert fcntl is not None
    lock_handle = lock_path.open("a+")
    deadline = time.time() + _LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_handle
        except BlockingIOError:
            if time.time() >= deadline:
                lock_handle.close()
                print(
                    f"claude-i: settings.json is locked by another process "
                    f"(waited {_LOCK_TIMEOUT_SECONDS}s).",
                    file=sys.stderr,
                )
                sys.exit(1)
            time.sleep(_LOCK_RETRY_INTERVAL)


def _release_lock(lock_handle: Any | None) -> None:
    """Release the advisory flock and close the lock file handle."""
    if lock_handle is None or not HAS_FCNTL:
        return
    assert fcntl is not None
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        # Best-effort — closing the handle releases the kernel lock anyway.
        pass
    try:
        lock_handle.close()
    except OSError:
        pass


def install_hook() -> None:
    """Append the claude-i Stop hook to ``SETTINGS``.

    Preserves all pre-existing ``Stop`` hook groups (Task 2.7): if other
    tools have already registered Stop hooks, this function only adds the
    claude-i entry rather than replacing the list.

    Refuses to mutate a file that does not parse as JSON. Creates the parent
    directory and an empty config when needed.

    G7: acquires an exclusive ``fcntl.flock`` on a sibling lock file before
    reading or writing ``SETTINGS``. The lock prevents concurrent ``claude-i``
    invocations from clobbering each other; it is advisory and does NOT
    coordinate with Claude Code's own writes to ``settings.json``.
    """
    lock_handle = _acquire_lock_with_retry()
    try:
        cfg: dict[str, Any] = {}
        if SETTINGS.exists():
            try:
                cfg = load_settings()
            except json.JSONDecodeError:
                sys.exit(f"{SETTINGS} is not valid JSON; refusing to touch it")
        hooks_section = cfg.setdefault("hooks", {})
        assert isinstance(hooks_section, dict)
        stop_list = hooks_section.setdefault("Stop", [])
        assert isinstance(stop_list, list)
        # Append-only — never replace. Existing groups (from other tools) survive.
        stop_list.append({"hooks": [{"type": "command", "command": HOOK_CMD}]})
        write_settings(cfg)
    finally:
        _release_lock(lock_handle)


def ensure_hook() -> None:
    """Prompt the user to install the Stop hook if it is missing.

    Behavioral parity with the seed: prints to ``stderr`` and reads from
    ``stdin``. ``cli.main`` must short-circuit on ``--version`` BEFORE
    invoking this function (otherwise CI hangs on ``input()``).
    """
    if hook_installed():
        return
    print(f"claude-i needs a Stop hook in {SETTINGS}.", file=sys.stderr)
    print(
        "Gated on $CLAUDE_I_SENTINEL, so it won't affect normal Claude use.",
        file=sys.stderr,
    )
    print(f"  command: {HOOK_CMD}", file=sys.stderr)
    if input("Install it now? [y/N] ").strip().lower() != "y":
        sys.exit("aborted")
    install_hook()
    print("Installed. Active on the next Claude session.", file=sys.stderr)
    print(
        "If the first run hangs, run `claude` interactively once, type /hooks,",
        file=sys.stderr,
    )
    print("acknowledge the change, then exit and retry.", file=sys.stderr)
