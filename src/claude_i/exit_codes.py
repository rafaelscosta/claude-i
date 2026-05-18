"""Exit code constants for claude-i.

STORY-001.2 / Task 3.8 / Gap G8 — uniform, machine-readable exit codes.

Lives in its own module (not ``cli.py``) so ``deps.py`` and ``hook.py`` can
import it without creating a circular dependency through ``cli``.

Codes:

- ``SUCCESS = 0`` — successful extraction of a non-empty response, OR an
  explicitly empty response when the caller passed ``--allow-empty``.
- ``RUNTIME_ERROR = 1`` — timeout waiting for Stop hook, transcript parse
  failure, empty response without ``--allow-empty``, unhandled
  ``RuntimeError`` from ``runner.run``, user-aborted hook install.
- ``CONFIG_ERROR = 2`` — missing external dependency (``tmux`` / ``claude``)
  or malformed configuration file (``settings.json`` not valid JSON).
- ``PLATFORM_ERROR = 3`` — running on an unsupported platform (native
  Windows; WSL2 reports ``linux`` and is supported).

The values match POSIX conventions: ``0`` success, ``1`` general failure,
``2`` "misuse of shell command / config" — and we extend with ``3`` for
platform-specific refusal so monitoring tools can distinguish "claude-i
declined to run here" from "claude-i ran and failed".
"""

from __future__ import annotations

from typing import Final

SUCCESS: Final[int] = 0
RUNTIME_ERROR: Final[int] = 1
CONFIG_ERROR: Final[int] = 2
PLATFORM_ERROR: Final[int] = 3
