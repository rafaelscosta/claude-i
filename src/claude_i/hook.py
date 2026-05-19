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
import os
import sys
import time
from typing import Any

from claude_i.exit_codes import CONFIG_ERROR, RUNTIME_ERROR
from claude_i.settings import (
    HOOK_CMD,
    HOOK_CMD_LEGACY,
    SETTINGS,
    load_settings,
    write_settings,
)

#: STORY-001.6 / Bug 3 — env var that opts a non-TTY (script/CI) invocation
#: into auto-installing the Stop hook instead of failing with a structured
#: error. Documented in NOTES.md and README. Default: unset (interactive
#: invocations get the prompt; non-interactive ones fail loud).
AUTO_INSTALL_ENV_VAR: str = "CLAUDE_I_AUTO_INSTALL_HOOK"

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

    A correct entry has ``type == "command"`` and ``command`` equal to
    EITHER the current ``HOOK_CMD`` (atomic-rename form, v0.2.1+) OR
    ``HOOK_CMD_LEGACY`` (single-step form, v0.2.0). Accepting both is what
    lets v0.2.0 users upgrade without being re-prompted to install — the
    silent upgrade path in ``ensure_hook`` handles the actual migration.

    The seed's looser check (``command == HOOK_CMD`` only) would mis-classify
    an entry with the right command string but a different ``type`` (e.g.
    ``http``) as installed; we tighten that.
    """
    if entry.get("type") != "command":
        return False
    return entry.get("command") in (HOOK_CMD, HOOK_CMD_LEGACY)


def _is_legacy_hook_entry(entry: dict[str, Any]) -> bool:
    """Return True when ``entry`` is specifically the v0.2.0 legacy hook.

    Used by ``_only_legacy_hook_installed`` to detect when a silent upgrade
    is needed. Distinct from ``_is_claude_i_hook_entry`` which accepts either
    form for the "already installed" check.
    """
    return entry.get("type") == "command" and entry.get("command") == HOOK_CMD_LEGACY


def _is_current_hook_entry(entry: dict[str, Any]) -> bool:
    """Return True when ``entry`` is specifically the v0.2.1+ atomic-rename hook."""
    return entry.get("type") == "command" and entry.get("command") == HOOK_CMD


def _iter_stop_hook_leaves() -> list[dict[str, Any]]:
    """Return all well-formed leaf-dict entries from settings.json Stop hooks.

    Filters out malformed entries (non-dict groups, non-list leaves, etc.) so
    callers can iterate the result without re-doing the structural defense.
    Returns an empty list when settings.json is missing or malformed JSON —
    never raises.
    """
    if not SETTINGS.exists():
        return []
    try:
        cfg = load_settings()
    except json.JSONDecodeError:
        return []
    stop_groups = cfg.get("hooks", {}).get("Stop", [])
    if not isinstance(stop_groups, list):
        return []
    leaves: list[dict[str, Any]] = []
    for group in stop_groups:
        if not isinstance(group, dict):
            continue
        group_leaves = group.get("hooks", [])
        if not isinstance(group_leaves, list):
            continue
        for entry in group_leaves:
            if isinstance(entry, dict):
                leaves.append(entry)
    return leaves


def hook_installed() -> bool:
    """Return ``True`` when the Stop hook is already present in settings.

    Accepts either the current atomic-rename ``HOOK_CMD`` (v0.2.1+) or the
    legacy single-step ``HOOK_CMD_LEGACY`` (v0.2.0). The silent upgrade path
    in ``ensure_hook`` migrates legacy installs in-place; this check is
    deliberately permissive so upgrading users see ``True`` and skip the
    interactive install prompt.

    Safe against a missing or malformed settings file: returns ``False``
    rather than raising.

    G2: the ``matcher`` field at the group level is NOT checked here because
    ``Stop`` hooks have no documented ``matcher`` schema (see ``NOTES.md``).
    Future stories may extend this check when / if Anthropic publishes a
    Stop-event matcher format.
    """
    return any(_is_claude_i_hook_entry(leaf) for leaf in _iter_stop_hook_leaves())


def _only_legacy_hook_installed() -> bool:
    """Return ``True`` when settings.json has the v0.2.0 hook but NOT the v0.2.1 hook.

    STORY-001.6 / Bug 1 — used by ``ensure_hook`` to detect when a silent
    upgrade is warranted. Returning True triggers ``remove_hook() +
    install_hook()`` without prompting the user; returning False means
    either everything is current (no-op) or nothing is installed (interactive
    prompt path).
    """
    leaves = _iter_stop_hook_leaves()
    has_legacy = any(_is_legacy_hook_entry(leaf) for leaf in leaves)
    has_current = any(_is_current_hook_entry(leaf) for leaf in leaves)
    return has_legacy and not has_current


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
                # G8 — migrated from bare sys.exit(1) to named constant.
                sys.exit(RUNTIME_ERROR)
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
                # G8 — migrated from string-form ``sys.exit(msg)`` (code 1)
                # to ``print + sys.exit(CONFIG_ERROR)`` (code 2). Malformed
                # settings is a config error, not a runtime error — the 1→2
                # semantic change is intentional per story Task 3.8.
                print(
                    f"claude-i: {SETTINGS} is not valid JSON; refusing to touch it",
                    file=sys.stderr,
                )
                sys.exit(CONFIG_ERROR)
        hooks_section = cfg.setdefault("hooks", {})
        assert isinstance(hooks_section, dict)
        stop_list = hooks_section.setdefault("Stop", [])
        assert isinstance(stop_list, list)
        # Append-only — never replace. Existing groups (from other tools) survive.
        stop_list.append({"hooks": [{"type": "command", "command": HOOK_CMD}]})
        write_settings(cfg)
    finally:
        _release_lock(lock_handle)


def remove_hook() -> int:
    """Remove every claude-i Stop hook entry from ``SETTINGS``.

    STORY-001.5 / Task 6.2 — paired with ``cli.cmd_uninstall``. Acquires the
    same G7 flock as ``install_hook`` so concurrent invocations cannot race.

    Filters every ``Stop`` hook group's ``hooks`` list by
    ``_is_claude_i_hook_entry``: claude-i leaves are dropped, every other
    leaf (including http hooks belonging to other tools, malformed entries,
    or unrelated commands) survives verbatim. Empty groups (where claude-i
    was the only leaf) are also dropped to keep ``settings.json`` tidy.

    Returns the number of claude-i hook entries removed. ``0`` means the
    hook was not installed (no-op success — same exit code, different
    operator-facing message). Raises ``json.JSONDecodeError`` on malformed
    settings; the caller (``cmd_uninstall``) translates to CONFIG_ERROR.
    """
    if not SETTINGS.exists():
        # No file → no hook → no-op. Mirrors the seed's hook_installed()
        # branch where absence is not an error.
        return 0
    lock_handle = _acquire_lock_with_retry()
    try:
        cfg = load_settings()  # may raise json.JSONDecodeError — caller handles
        hooks_section = cfg.get("hooks", {})
        if not isinstance(hooks_section, dict):
            return 0
        stop_groups = hooks_section.get("Stop", [])
        if not isinstance(stop_groups, list):
            return 0
        removed = 0
        new_groups: list[Any] = []
        for group in stop_groups:
            if not isinstance(group, dict):
                # Preserve unknown group shapes verbatim — we own claude-i
                # entries only.
                new_groups.append(group)
                continue
            leaves = group.get("hooks", [])
            if not isinstance(leaves, list):
                new_groups.append(group)
                continue
            kept_leaves: list[Any] = []
            for entry in leaves:
                if isinstance(entry, dict) and _is_claude_i_hook_entry(entry):
                    removed += 1
                    continue
                kept_leaves.append(entry)
            if kept_leaves:
                # Group still has live leaves → keep it with the new list.
                new_group = dict(group)
                new_group["hooks"] = kept_leaves
                new_groups.append(new_group)
            elif not leaves:
                # Group was empty to begin with — preserve verbatim so we
                # do not silently restructure an unrelated config shape.
                new_groups.append(group)
            # else: every leaf was a claude-i entry → drop the empty group.
        hooks_section["Stop"] = new_groups
        cfg["hooks"] = hooks_section
        if removed:
            write_settings(cfg)
        return removed
    finally:
        _release_lock(lock_handle)


def _upgrade_legacy_hook() -> None:
    """Silently remove the v0.2.0 hook and install the v0.2.1 atomic-rename hook.

    STORY-001.6 / Bug 1 — called from ``ensure_hook`` when
    ``_only_legacy_hook_installed()`` returns True. Does NOT prompt the user;
    emits one stderr line so the upgrade is visible in logs.
    """
    print(
        "claude-i: detected legacy v0.2.0 Stop hook, upgrading to atomic-rename form",
        file=sys.stderr,
    )
    remove_hook()  # removes BOTH forms; safe because we'll re-install immediately
    install_hook()


def ensure_hook() -> None:
    """Ensure the Stop hook is installed in settings, prompting or auto-installing.

    Flow (priority order):

    1. **Already installed (current form)** → no-op return.
    2. **Only legacy v0.2.0 installed** → silent upgrade (``_upgrade_legacy_hook``),
       no prompt.
    3. **Not installed + non-TTY stdin + ``CLAUDE_I_AUTO_INSTALL_HOOK=1``** →
       auto-install silently (script-friendly opt-in).
    4. **Not installed + non-TTY stdin + env var unset** → print structured
       error to stderr listing 3 remediation paths and ``sys.exit(CONFIG_ERROR)``.
       Replaces the EOFError crash that the seed's bare ``input()`` produced.
    5. **Not installed + TTY stdin** → original interactive prompt.

    ``cli.main`` must short-circuit on ``--version`` BEFORE invoking this
    function — argparse handles that automatically.
    """
    if hook_installed():
        if _only_legacy_hook_installed():
            _upgrade_legacy_hook()
        return

    # Not installed at all. Branch on TTY vs non-TTY before any input() call —
    # the seed's bare input() crashed with EOFError when stdin was redirected.
    auto_install = os.environ.get(AUTO_INSTALL_ENV_VAR) == "1"
    if not sys.stdin.isatty():
        if auto_install:
            print(
                "claude-i: installing Stop hook automatically "
                f"({AUTO_INSTALL_ENV_VAR}=1, stdin is not a TTY)",
                file=sys.stderr,
            )
            install_hook()
            return
        print(
            f"claude-i: Stop hook not installed in {SETTINGS} and stdin is not a TTY.\n"
            "Options:\n"
            "  1. Run `claude-i doctor` (or any claude-i command) from an interactive\n"
            "     shell once to confirm the install prompt.\n"
            f"  2. Set {AUTO_INSTALL_ENV_VAR}=1 in your environment to auto-install\n"
            "     on the first non-TTY invocation (script / CI friendly).\n"
            f"  3. Edit {SETTINGS} manually and add the Stop hook entry.\n"
            f"     command: {HOOK_CMD}",
            file=sys.stderr,
        )
        # CONFIG_ERROR (2) — missing required configuration. The user has to
        # take an action before claude-i can proceed; this is not a transient
        # runtime error.
        sys.exit(CONFIG_ERROR)

    # TTY path — original interactive prompt.
    print(f"claude-i needs a Stop hook in {SETTINGS}.", file=sys.stderr)
    print(
        "Gated on $CLAUDE_I_SENTINEL, so it won't affect normal Claude use.",
        file=sys.stderr,
    )
    print(f"  command: {HOOK_CMD}", file=sys.stderr)
    if input("Install it now? [y/N] ").strip().lower() != "y":
        # G8 — migrated from string-form ``sys.exit("aborted")`` (code 1)
        # to ``print + sys.exit(RUNTIME_ERROR)`` (still code 1, but via
        # named constant for consistency).
        print("claude-i: aborted", file=sys.stderr)
        sys.exit(RUNTIME_ERROR)
    install_hook()
    print("Installed. Active on the next Claude session.", file=sys.stderr)
    print(
        "If the first run hangs, run `claude` interactively once, type /hooks,",
        file=sys.stderr,
    )
    print("acknowledge the change, then exit and retry.", file=sys.stderr)
