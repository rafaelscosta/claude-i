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

STORY-001.2 will add ``fcntl.flock`` around mutations (gap G7). Keep the
hook block shape minimal until then.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from claude_i.settings import HOOK_CMD, SETTINGS, load_settings, write_settings


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


def install_hook() -> None:
    """Append the claude-i Stop hook to ``SETTINGS``.

    Preserves all pre-existing ``Stop`` hook groups (Task 2.7): if other
    tools have already registered Stop hooks, this function only adds the
    claude-i entry rather than replacing the list.

    Refuses to mutate a file that does not parse as JSON. Creates the parent
    directory and an empty config when needed.
    """
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
