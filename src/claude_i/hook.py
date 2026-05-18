"""Stop-hook installer for claude-i.

Verbatim behavioral port of ``seed/claude-i`` lines 26-65 (``hook_installed``,
``install_hook``, ``ensure_hook``). No hardening lives here in STORY-001.0 —
STORY-001.1 introduces ``matcher`` / sentinel-keyed scoping (gap G2) and
STORY-001.2 adds ``fcntl.flock`` around mutations (gap G7). Keep the hook
block shape minimal until then.
"""

from __future__ import annotations

import json
import sys

from claude_i.settings import HOOK_CMD, SETTINGS, load_settings, write_settings


def hook_installed() -> bool:
    """Return ``True`` when the Stop hook is already present in settings.

    Safe against a missing or malformed settings file: returns ``False``
    rather than raising.
    """
    if not SETTINGS.exists():
        return False
    try:
        cfg = load_settings()
    except json.JSONDecodeError:
        return False
    stop_groups = cfg.get("hooks", {}).get("Stop", [])
    return any(
        h.get("command") == HOOK_CMD
        for g in stop_groups
        for h in g.get("hooks", [])
    )


def install_hook() -> None:
    """Append the Stop hook to ``SETTINGS``.

    Refuses to mutate a file that does not parse as JSON. Creates the parent
    directory and an empty config when needed.
    """
    cfg: dict[str, object] = {}
    if SETTINGS.exists():
        try:
            cfg = load_settings()
        except json.JSONDecodeError:
            sys.exit(f"{SETTINGS} is not valid JSON; refusing to touch it")
    hooks_section = cfg.setdefault("hooks", {})
    assert isinstance(hooks_section, dict)
    stop_list = hooks_section.setdefault("Stop", [])
    assert isinstance(stop_list, list)
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
