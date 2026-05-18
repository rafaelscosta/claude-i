# STORY-001.0: Bootstrap — Package Skeleton, pyproject, CI, pytest, Seed Refactor

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Depends on | none |
| Estimated | 5 pts (~2 days) |

## User Story

As a developer cloning `claude-i` for the first time, I want a properly structured Python package with a working `pip install -e .`, a `pytest` scaffold, and CI lint/test on every push, so that I can contribute with confidence and @dev has a stable foundation for all subsequent hardening stories.

## Acceptance Criteria

- AC-1: `pip install -e .` on a clean clone of `main` (Python 3.11+, no virtualenv pre-existing) exits 0 and places `claude-i` on `$PATH` within the activated environment.
- AC-2: `claude-i --version` prints `claude-i 0.2.0.dev0` (or equivalent pre-release marker) and exits 0.
- AC-3: The six modules exist under `src/claude_i/`: `__init__.py`, `cli.py`, `hook.py`, `runner.py`, `deps.py`, `reaper.py`, `settings.py`. Each module contains at minimum a stub (docstring + public function/class skeleton) with no `ImportError` when imported.
- AC-4: `pytest tests/` exits 0 (even with only a smoke `test_import.py` that imports all six modules).
- AC-5: `ruff check src/ tests/` exits 0 (no lint errors).
- AC-6: `mypy src/claude_i/` exits 0 with `strict = true` in `pyproject.toml` (stubs are typed).
- AC-7: GitHub Actions workflow `.github/workflows/ci.yml` runs on every push and pull request to `main`: lint (`ruff`), type-check (`mypy`), and `pytest` on `ubuntu-latest` with Python 3.11 and 3.12. The workflow is green on the bootstrap commit.
- AC-8: `seed/claude-i` is **preserved verbatim** — `git diff seed/claude-i` produces no output after this story merges.
- AC-9: The refactored modules reproduce the functional behavior of `seed/claude-i` (when wired together via `cli.py`), even if the full hardening is incomplete. The functional gap is acceptable; missing behavior is covered by STORY-001.1 and STORY-001.2. No regression in existing behavior is introduced.
- AC-10: `pyproject.toml` declares `requires-python = ">=3.11"`, `hatchling` as the build backend, and a `[project.scripts]` entry pointing `claude-i` at `claude_i.cli:main`.

## Tasks / Subtasks

- [ ] 1.1 — Create `pyproject.toml` with Hatchling backend
  - [ ] Set `name = "claude-i"`, `version = "0.2.0.dev0"`, `requires-python = ">=3.11"`
  - [ ] Add `[project.scripts] claude-i = "claude_i.cli:main"`
  - [ ] Declare runtime dependencies: `none` (all deps are stdlib + external binaries)
  - [ ] Add `[tool.hatch.build.targets.wheel] packages = ["src/claude_i"]`
  - [ ] Add `[tool.ruff]`, `[tool.mypy]` with `strict = true`, `[tool.pytest.ini_options]` sections

- [ ] 1.2 — Create `src/claude_i/__init__.py`
  - [ ] Expose `__version__ = "0.2.0.dev0"`
  - [ ] Keep it minimal — no star imports

- [ ] 1.3 — Create `src/claude_i/settings.py` stub
  - [ ] Define `SETTINGS: Path = Path.home() / ".claude" / "settings.json"`
  - [ ] Migrate the `HOOK_CMD` constant from `seed/claude-i` here (source of truth for all stories)
  - [ ] Add typed helper stubs: `load_settings() -> dict[str, Any]`, `write_settings(cfg: dict[str, Any]) -> None`

- [ ] 1.4 — Create `src/claude_i/hook.py` stub
  - [ ] Migrate `hook_installed()`, `install_hook()`, `ensure_hook()` from seed (lines 26-65)
  - [ ] Typed signatures, docstrings; implementation can delegate to `settings.py`
  - [ ] No behavioral change from seed in this story — hardening happens in STORY-001.1

- [ ] 1.5 — Create `src/claude_i/deps.py` stub
  - [ ] Define `check_deps() -> None` stub (raises `SystemExit` with hint on missing binary)
  - [ ] Define `assert_not_windows() -> None` stub
  - [ ] Enumerate expected external binaries: `["tmux", "claude"]`

- [ ] 1.6 — Create `src/claude_i/runner.py` stub
  - [ ] Migrate `tmux()`, `tail_pane()`, `run()` from seed (lines 68-160)
  - [ ] Typed signatures; `run()` signature: `run(prompt: str, extra_args: list[str], verbose: bool, ready_wait: float, timeout: int) -> str`
  - [ ] No behavioral change in this story

- [ ] 1.7 — Create `src/claude_i/reaper.py` stub
  - [ ] Define `reap_orphans() -> int` stub (returns count of killed sessions)
  - [ ] Define `register_cleanup(session: str) -> None` stub (atexit/signal registration placeholder)
  - [ ] Full implementation deferred to STORY-001.2

- [ ] 1.8 — Create `src/claude_i/cli.py`
  - [ ] Migrate `main()` from seed (lines 163-180)
  - [ ] Add `--version` flag using `importlib.metadata.version("claude-i")`
  - [ ] Wire `cli.py` → `hook.ensure_hook()` → `runner.run()` → `print(result)`
  - [ ] Subcommand stubs (`doctor`, `uninstall`, `reap`) as `NotImplementedError` placeholders — full impl in STORY-001.5

- [ ] 1.9 — Create `tests/test_import.py`
  - [ ] `import claude_i` succeeds (AC-4 smoke test)
  - [ ] `from claude_i import cli, hook, runner, deps, reaper, settings` — all import without error
  - [ ] Assert `claude_i.__version__` is a non-empty string

- [ ] 1.10 — Create `.github/workflows/ci.yml`
  - [ ] Trigger: `push` and `pull_request` to `main`
  - [ ] Matrix: `python-version: ["3.11", "3.12"]`, `os: [ubuntu-latest]`
  - [ ] Steps: `pip install -e ".[dev]"` → `ruff check` → `mypy` → `pytest`
  - [ ] Add `[project.optional-dependencies] dev = ["pytest", "ruff", "mypy"]` to `pyproject.toml`

- [ ] 1.11 — Verify `seed/claude-i` is unchanged
  - [ ] `git diff HEAD~1..HEAD -- seed/claude-i` produces no output
  - [ ] Add a CI step: `git diff --exit-code seed/` to detect accidental seed mutation

## Dev Notes

- **Module boundary rationale (from @architect):** `settings.py` owns all `~/.claude/settings.json` I/O; `hook.py` owns hook logic using `settings.py`; `runner.py` owns the tmux lifecycle; `deps.py` owns binary presence checks; `reaper.py` owns cleanup and signal handling; `cli.py` is the thin argparse entry point wiring the others together.
- **`HOOK_CMD` constant:** currently lives in `seed/claude-i` line 17-22. Move it to `settings.py` as the canonical location. All other modules import from there. Do NOT duplicate it.
- **Hatchling vs setuptools:** use Hatchling — it reads from `pyproject.toml` natively and is the PyPA-recommended backend for new projects.
- **`requires-python`:** pin `>=3.11` (walrus operator, `match`, `tomllib` stdlib, `Path.read_text()` without `encoding` warnings). The seed uses f-strings and `list[str]` annotations directly — these are 3.9+ but 3.11 is the practical minimum for `tomllib` and stable `argparse.REMAINDER` behavior.
- **`importlib.metadata`:** use `importlib.metadata.version("claude-i")` in `cli.py` for `--version`; this reads from the installed package metadata and stays in sync with `pyproject.toml` automatically.
- **Seed preservation CI step:** add to `ci.yml` under a `check-seed-integrity` job: `git diff --exit-code seed/` — this prevents accidental seed mutation in future PRs and satisfies the Epic's DoD requirement.
- **Expected file paths after this story:**
  - `pyproject.toml`
  - `src/claude_i/__init__.py`
  - `src/claude_i/cli.py`
  - `src/claude_i/hook.py`
  - `src/claude_i/runner.py`
  - `src/claude_i/deps.py`
  - `src/claude_i/reaper.py`
  - `src/claude_i/settings.py`
  - `tests/__init__.py`
  - `tests/test_import.py`
  - `.github/workflows/ci.yml`

## Testing

- **pytest smoke:** `tests/test_import.py` — import all modules, assert `__version__` non-empty.
- **CLI smoke (manual):** `pip install -e . && claude-i --version` — should print `claude-i 0.2.0.dev0` without error.
- **Lint:** `ruff check src/ tests/` — must exit 0 before marking AC-5 complete.
- **Type check:** `mypy src/claude_i/` — must exit 0 before marking AC-6 complete.
- **CI green:** confirm GitHub Actions passes on the PR before merge.
- **Seed integrity (manual):** `git diff seed/claude-i` — must produce no output.

## File List

(empty — populated by @dev during execution)

## Dev Agent Record

(empty — populated by @dev)
