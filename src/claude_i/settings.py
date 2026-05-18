"""Settings I/O for claude-i.

Owns all access to ``~/.claude/settings.json`` and the canonical ``HOOK_CMD``
constant used by the Stop hook installer. Other modules MUST import from here
rather than redefining either symbol.

Forward-compat note: STORY-001.2 will introduce ``fcntl.flock`` around mutations
(gap G7). The current implementation is intentionally minimal — a faithful port
of the seed's behavior — so the hardening can land in one place later.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Canonical Stop hook command. Sourced from ``seed/claude-i`` lines 17-22.
# Single source of truth for all modules — never duplicate this string.
HOOK_CMD: str = (
    'if [ -n "$CLAUDE_I_SENTINEL" ]; then '
    'cat > "$CLAUDE_I_SENTINEL.json"; '
    'touch "$CLAUDE_I_SENTINEL"; '
    "fi"
)

# Path to Claude Code's user-level settings file.
SETTINGS: Path = Path.home() / ".claude" / "settings.json"

# STORY-001.5 / Task 6.5 / Gap G17 — TUI readiness probe heuristic.
#
# ``runner._wait_for_tui_ready`` polls ``tmux capture-pane`` at fixed intervals
# and checks the captured pane content against this regex. Matches detect a
# claude TUI prompt indicator and signal "ready to receive input". The
# pattern is intentionally permissive — both ``>`` (ASCII greater-than) and
# the Unicode powerline-style prompt glyph (``U+276F``) are accepted because
# the upstream TUI rendering is an implementation detail (DEP-3 in the gap
# inventory) and could change.
#
# Stored here (not in ``runner.py``) so future tuning is a single-file edit
# and so users can monkeypatch this constant in tests without touching the
# poller logic. The U+276F char is intentional — escape sequence form keeps
# ruff's ambiguous-glyph linter happy without losing the literal match.
TUI_READY_PATTERN: str = "[>❯]"  # noqa: RUF001


def load_settings() -> dict[str, Any]:
    """Load ``SETTINGS`` and return its parsed contents.

    Returns an empty dict when the file does not exist. Raises
    ``json.JSONDecodeError`` when the file exists but is not valid JSON —
    callers are expected to refuse to mutate a malformed settings file.
    """
    if not SETTINGS.exists():
        return {}
    raw = SETTINGS.read_text()
    parsed: Any = json.loads(raw)
    if not isinstance(parsed, dict):
        # Settings should be a JSON object at the top level; a list/string
        # would not match Claude Code's contract. Treat as empty rather than
        # silently corrupting the structure.
        return {}
    return parsed


def write_settings(cfg: dict[str, Any]) -> None:
    """Write ``cfg`` to ``SETTINGS`` as JSON, creating parents as needed.

    Forward-compat: STORY-001.2 will wrap this in an ``fcntl.flock`` advisory
    lock (gap G7). For now, mirror the seed's plain write.
    """
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(cfg, indent=2))
