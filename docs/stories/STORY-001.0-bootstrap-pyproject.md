# STORY-001.0: Bootstrap — Package Skeleton, pyproject, CI, pytest, Seed Refactor

| Field | Value |
|---|---|
| Status | Done |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Validated | 2026-05-17 by @po (Pax) — GO Condicional, 9/10 |
| Implemented | 2026-05-17 by @dev (Dex) |
| Depends on | none |
| Estimated | 5 pts (~2 days) |
| Executor | @dev (Dex) |
| Quality Gate | @qa (Quinn) |

## User Story

As a developer cloning `claude-i` for the first time, I want a properly structured Python package with a working `pip install -e .`, a `pytest` scaffold, and CI lint/test on every push, so that I can contribute with confidence and @dev has a stable foundation for all subsequent hardening stories.

## Acceptance Criteria

- AC-1: `pip install -e .` on a clean clone of `main` (Python 3.11+, no virtualenv pre-existing) exits 0 and places `claude-i` on `$PATH` within the activated environment.
- AC-2: `claude-i --version` prints a line containing `0.2.0.dev0` (e.g. `claude-i 0.2.0.dev0`) and exits 0. The version string is sourced from `importlib.metadata.version("claude-i")` and the `claude-i ` prefix is added by argparse (`action="version"` + `version="%(prog)s {ver}"`).
- AC-3: The six modules exist under `src/claude_i/`: `__init__.py`, `cli.py`, `hook.py`, `runner.py`, `deps.py`, `reaper.py`, `settings.py`. Each module contains at minimum a stub (docstring + public function/class skeleton) with no `ImportError` when imported.
- AC-4: `pytest tests/` exits 0 (even with only a smoke `test_import.py` that imports all six modules).
- AC-5: `ruff check src/ tests/` exits 0 (no lint errors).
- AC-6: `mypy src/claude_i/` exits 0 with `strict = true` in `pyproject.toml` (stubs are typed).
- AC-7: GitHub Actions workflow `.github/workflows/ci.yml` runs on every push and pull request to `main`: lint (`ruff`), type-check (`mypy`), and `pytest` on `ubuntu-latest` with Python 3.11 and 3.12. The workflow is green on the bootstrap commit.
- AC-8: `seed/claude-i` is **preserved verbatim** — `git diff seed/claude-i` produces no output after this story merges.
- AC-9: The refactored modules reproduce the functional behavior of `seed/claude-i` (when wired together via `cli.py`), even if the full hardening is incomplete. Verification is **manual smoke + downstream integration tests in STORY-001.1**, not an automated assertion in this story. The functional gap is acceptable; missing behavior is covered by STORY-001.1 and STORY-001.2. No regression in existing behavior is introduced.
- AC-10: `pyproject.toml` declares `requires-python = ">=3.11"`, `hatchling` as the build backend, and a `[project.scripts]` entry pointing `claude-i` at `claude_i.cli:main`.

## Tasks / Subtasks

- [x] 1.1 — Create `pyproject.toml` with Hatchling backend
  - [x] Set `name = "claude-i"`, `version = "0.2.0.dev0"`, `requires-python = ">=3.11"`
  - [x] Add `[project.scripts] claude-i = "claude_i.cli:main"`
  - [x] Declare runtime dependencies: `none` (all deps are stdlib + external binaries)
  - [x] Add `[tool.hatch.build.targets.wheel] packages = ["src/claude_i"]`
  - [x] Add `[tool.ruff]`, `[tool.mypy]` with `strict = true`, `[tool.pytest.ini_options]` sections

- [x] 1.2 — Create `src/claude_i/__init__.py`
  - [x] Expose `__version__ = "0.2.0.dev0"`
  - [x] Keep it minimal — no star imports

- [x] 1.3 — Create `src/claude_i/settings.py` stub
  - [x] Define `SETTINGS: Path = Path.home() / ".claude" / "settings.json"`
  - [x] Migrate the `HOOK_CMD` constant from `seed/claude-i` here (source of truth for all stories)
  - [x] Add typed helper stubs: `load_settings() -> dict[str, Any]`, `write_settings(cfg: dict[str, Any]) -> None`

- [x] 1.4 — Create `src/claude_i/hook.py` stub
  - [x] Migrate `hook_installed()`, `install_hook()`, `ensure_hook()` from seed (lines 26-65)
  - [x] Typed signatures, docstrings; implementation can delegate to `settings.py`
  - [x] No behavioral change from seed in this story — hardening happens in STORY-001.1

- [x] 1.5 — Create `src/claude_i/deps.py` stub
  - [x] Define `check_deps() -> None` stub (raises `SystemExit` with hint on missing binary)
  - [x] Define `assert_not_windows() -> None` stub
  - [x] Enumerate expected external binaries: `["tmux", "claude"]`

- [x] 1.6 — Create `src/claude_i/runner.py` stub
  - [x] Migrate `tmux()`, `tail_pane()`, `run()` from seed (lines 68-160)
  - [x] Typed signatures; `run()` signature: `run(prompt: str, extra_args: list[str], verbose: bool, ready_wait: float, timeout: int) -> str`
  - [x] No behavioral change in this story

- [x] 1.7 — Create `src/claude_i/reaper.py` stub
  - [x] Define `reap_orphans() -> int` stub (returns count of killed sessions)
  - [x] Define `register_cleanup(session: str) -> None` stub (atexit/signal registration placeholder)
  - [x] Full implementation deferred to STORY-001.2

- [x] 1.8 — Create `src/claude_i/cli.py`
  - [x] Migrate `main()` from seed (lines 163-180)
  - [x] Add `--version` flag using argparse `action="version"`, with version string sourced from `importlib.metadata.version("claude-i")`. Format: `"%(prog)s {ver}"` so output is `claude-i 0.2.0.dev0`.
  - [x] **CRITICAL — `--version` must short-circuit before `ensure_hook()`**: argparse's `action="version"` handles this natively (prints and exits before `parse_args()` returns). Do NOT call `ensure_hook()` until after `parse_args()` has fully returned. This prevents CI hangs (CI cannot answer the `y/N` prompt in `ensure_hook()`).
  - [x] Wire (post-`parse_args`): `hook.ensure_hook()` → `runner.run()` → `print(result)`
  - [x] Subcommand stubs (`doctor`, `uninstall`, `reap`) as `NotImplementedError` placeholders — full impl in STORY-001.5

- [x] 1.9 — Create `tests/test_import.py`
  - [x] `import claude_i` succeeds (AC-4 smoke test)
  - [x] `from claude_i import cli, hook, runner, deps, reaper, settings` — all import without error
  - [x] Assert `claude_i.__version__` is a non-empty string

- [x] 1.10 — Create `.github/workflows/ci.yml`
  - [x] Trigger: `push` and `pull_request` to `main`
  - [x] Matrix: `python-version: ["3.11", "3.12"]`, `os: [ubuntu-latest]`
  - [x] Steps: `pip install -e ".[dev]"` → `ruff check` → `mypy` → `pytest`
  - [x] Add `[project.optional-dependencies] dev = ["pytest", "ruff", "mypy"]` to `pyproject.toml`

- [x] 1.11 — Verify `seed/claude-i` is unchanged
  - [x] `git diff HEAD~1..HEAD -- seed/claude-i` produces no output (verified post-commit; pre-commit verified via `git diff seed/claude-i` → no output)
  - [x] Add a CI step: `git diff --exit-code seed/` to detect accidental seed mutation (job `check-seed-integrity` in `.github/workflows/ci.yml`)

## Dev Notes

- **Module boundary rationale (from @architect):** `settings.py` owns all `~/.claude/settings.json` I/O; `hook.py` owns hook logic using `settings.py`; `runner.py` owns the tmux lifecycle; `deps.py` owns binary presence checks; `reaper.py` owns cleanup and signal handling; `cli.py` is the thin argparse entry point wiring the others together.
- **`HOOK_CMD` constant:** currently lives in `seed/claude-i` line 17-22. Move it to `settings.py` as the canonical location. All other modules import from there. Do NOT duplicate it.
- **Hatchling vs setuptools:** use Hatchling — it reads from `pyproject.toml` natively and is the PyPA-recommended backend for new projects.
- **`requires-python`:** pin `>=3.11` (walrus operator, `match`, `tomllib` stdlib, `Path.read_text()` without `encoding` warnings). The seed uses f-strings and `list[str]` annotations directly — these are 3.9+ but 3.11 is the practical minimum for `tomllib` and stable `argparse.REMAINDER` behavior.
- **`importlib.metadata`:** use `importlib.metadata.version("claude-i")` in `cli.py` for `--version`; this reads from the installed package metadata and stays in sync with `pyproject.toml` automatically.
- **Seed preservation CI step:** add to `ci.yml` under a `check-seed-integrity` job: `git diff --exit-code seed/` — this prevents accidental seed mutation in future PRs and satisfies the Epic's DoD requirement.
- **Forward-compat — stubs will be rewritten downstream.** Keep stubs minimal and non-prescriptive. Specifically:
  - `hook.py` — STORY-001.1 adds `matcher`/sentinel-keyed hook scoping (G2). Don't over-design the hook block shape now.
  - `runner.py` — STORY-001.5 replaces `--ready-wait` with readiness polling (G17). The `ready_wait: float` parameter in `run()` is **transitional**; downstream story may rename/remove. Keep the signature as specified, but do not build features around the param staying.
  - `reaper.py` — STORY-001.2 implements `atexit`+signal cleanup (G6). Stubs here are placeholders only.
- **`ensure_hook()` interactive prompt in non-TTY contexts:** the seed's `ensure_hook()` calls `input()` which would hang in CI. STORY-001.0 keeps the same behavior (no scope creep), but Task 1.8 ensures `--version` exits BEFORE `ensure_hook()` is called. CI runs only `--version` / `pytest`, never the full prompt path — that's the safety contract for this bootstrap.
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

### Created
- `pyproject.toml` — Hatchling build backend, Python 3.11+, `claude-i` entry point, ruff/mypy(strict)/pytest config, `[dev]` extras.
- `src/claude_i/__init__.py` — package docstring + `__version__ = "0.2.0.dev0"`.
- `src/claude_i/settings.py` — canonical `HOOK_CMD` and `SETTINGS` path, typed `load_settings()` / `write_settings()` helpers.
- `src/claude_i/hook.py` — verbatim behavioral port of `hook_installed()` / `install_hook()` / `ensure_hook()` (seed lines 26-65), delegates I/O to `settings.py`.
- `src/claude_i/deps.py` — `check_deps()` + `assert_not_windows()` stubs, `EXPECTED_BINARIES = ("tmux", "claude")`.
- `src/claude_i/runner.py` — verbatim behavioral port of `tmux()` / `tail_pane()` / `run()` (seed lines 68-160). `tempfile.mktemp` preserved with comment pointing to STORY-001.2 (gap G5).
- `src/claude_i/reaper.py` — `reap_orphans()` / `register_cleanup()` stubs; full implementation deferred to STORY-001.2 (gap G6).
- `src/claude_i/cli.py` — argparse entry point with `--version` (`action="version"`, `%(prog)s {ver}` format) wired BEFORE `ensure_hook()` to prevent CI hangs; `doctor` / `uninstall` / `reap` subcommand placeholders raise `NotImplementedError` (STORY-001.5).
- `tests/__init__.py` — empty package marker.
- `tests/test_import.py` — 4 smoke tests: package imports, all submodules import, `HOOK_CMD` SoT, `EXPECTED_BINARIES` enumerated.
- `.github/workflows/ci.yml` — `lint-typecheck-test` job (Python 3.11/3.12 on ubuntu-latest, `ruff` + `mypy` + `pytest` + `--version` assertion) and `check-seed-integrity` job (`git diff` against the first commit that introduced `seed/claude-i`).

### Modified
- `docs/stories/STORY-001.0-bootstrap-pyproject.md` — task checkboxes flipped to `[x]`, File List + Dev Agent Record populated, status flipped to `In Review`.

### Untouched (per AC-8)
- `seed/claude-i` — byte-identical to initial commit, verified via `git diff seed/claude-i` (no output).

## Dev Agent Record

### Implementation Mode
- **Mode:** YOLO (per `*develop` skill, cross-repo execution from sinkra-hub session).
- **Branch:** `feat/story-001.0-bootstrap-pyproject` (created from `main` at SHA `59a7f72`).

### Verification (local, pre-commit)

All six quality gates green on Python 3.11.12 in fresh `/tmp/claude-i-venv-001` venv:

| Gate | Command | Result |
|---|---|---|
| AC-1 install | `pip install -e ".[dev]"` | exit 0, wheel built (`claude_i-0.2.0.dev0-py3-none-any.whl`) |
| AC-2 version | `claude-i --version` | `claude-i 0.2.0.dev0`, exit 0 |
| AC-4 tests | `pytest tests/` | `4 passed in 0.01s`, exit 0 |
| AC-5 lint | `ruff check src/ tests/` | `All checks passed!`, exit 0 |
| AC-6 typecheck | `mypy src/claude_i/` | `Success: no issues found in 7 source files`, exit 0 |
| AC-8 seed | `git diff seed/claude-i` | no output, exit 0 |

### Notes & Forward-Compat Decisions

- **`tempfile.mktemp` retention:** verbatim seed behavior preserved in `runner.run()` with an inline comment pointing forward to STORY-001.2 (gap G5). Replacing it now would breach AC-9 ("no behavioral change in this story").
- **`ready_wait: float` parameter:** kept per spec as a transitional parameter. STORY-001.5 (gap G17) replaces it with readiness polling.
- **`importlib.metadata` fallback:** `cli._version_string()` falls back to `claude_i.__version__` when the package is not installed (defensive, in case of direct `python -m claude_i.cli` runs from a checkout). Argparse always prefixes with `%(prog)s ` so the final output is exactly `claude-i 0.2.0.dev0`.
- **Hook block shape:** `install_hook()` writes `{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": HOOK_CMD}]}]}}` — verbatim seed shape. STORY-001.1 will add `matcher` / sentinel-keyed scoping (gap G2); the current shape is intentionally minimal so the downstream patch is auditable.
- **CI seed-integrity check:** the job compares `HEAD` against the first commit that introduced `seed/claude-i` (resolved via `git log --diff-filter=A`). This is more rigorous than `HEAD~1..HEAD` because it catches drift across multiple commits, not just the most recent one.
- **`ruff` rule selection:** `E/W/F/I/B/UP/RUF` enabled. `BLE001` and `S306` are NOT in the selected set, so I removed the corresponding `# noqa` directives and replaced them with explanatory comments. If STORY-001.2 enables `S`-rules (security) for the `tempfile.mktemp` line, the comment is right there as a flag.
- **Constitution adherence:** local commit only (Article on Agent Authority). Push delegated to `@devops` per cross-repo execution context.

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-17 | @pm (Morgan) | Initial draft from EPIC-001 |
| 2026-05-17 | @sm (River) | Story drafted with 11 tasks, 10 ACs |
| 2026-05-17 | @po (Pax) | Validated 9/10 [GO Condicional]. Context: Epic 001, Wave 0 (bootstrap, no prior stories). 0 prior stories analyzed (Epic is greenfield). D10: 0 divergences (nothing to diverge from). Auto-fixes applied: (1) AC-2 tightened — explicit format contract + argparse `%(prog)s {ver}` recipe; (2) AC-9 — clarified manual smoke + downstream integration testing path; (3) Task 1.8 — added CRITICAL note that `--version` must short-circuit before `ensure_hook()` to prevent CI hangs; (4) Dev Notes — added forward-compat warnings for `hook.py`/`runner.py`/`reaper.py` stubs that downstream stories will rewrite. Status transitioned Draft → Ready. Conditions for @dev: (a) preserve the manual-only verification of AC-9; (b) keep `ready_wait` parameter shape per spec but treat as transitional; (c) verify `--version` exits before `ensure_hook()` is called (use argparse `action="version"`). |
| 2026-05-17 | @dev (Dex) | Implemented all 11 tasks. All six local quality gates green (install, --version, pytest 4/4, ruff, mypy strict, seed unchanged). Branch `feat/story-001.0-bootstrap-pyproject`. PO conditions addressed: (a) AC-9 verified manually (no automated assertion added); (b) `ready_wait` kept transitional per spec; (c) `--version` uses `action="version"` so it short-circuits before `parse_args()` returns — `ensure_hook()` is unreachable on a `--version` invocation. Status Ready → In Review. Pending: @devops push, @qa gate. |
| 2026-05-17 | @qa (Quinn) | Quality gate **PASS 96/100**. All 10 ACs verified (AC-7 deferred to post-push CI). 0 CRITICAL/HIGH/MEDIUM issues; 2 LOW cosmetic items recorded as backlog. CodeRabbit skipped (cross-repo, compensating control: manual gate re-run on fresh venv). Gate file: `docs/gates/STORY-001.0-gate.md`. Status: Ready for Done. |
| 2026-05-17 | @devops (Gage) | Pushed `feat/story-001.0-bootstrap-pyproject` → fast-forward merge to `main`. CI run #26010042733 GREEN on Python 3.11 + 3.12 + `check-seed-integrity` job. AC-7 externally confirmed. Working tree clean post-merge. |
| 2026-05-17 | @po (Pax) | Closed: status In Review → **Done**. Pre-closure gates: CHK-8 N/A (`deploy_type: none`; CI green run #26010042733 serves as external validation); CHK-9 N/A (claude-i is greenfield, no AIOX registry surface); CHK-10 N/A (no `services/`, `squads/`, or `.claude/skills/` files created — pure Python package scaffold). All Phase 1 verification items confirmed: PASS gate, 11/11 tasks checked, 10/10 ACs verified, File List + Dev Agent Record + QA Results populated. Epic 001 progress: 1/6 stories Done (16.7%). |

## QA Results

### Review Date: 2026-05-17

### Reviewed By: Quinn (Test Architect, @qa)

### CodeRabbit Self-Healing
- Iterations: 0/3
- Outcome: SKIPPED — cross-repo execution; CodeRabbit CLI integration is sinkra-hub-bound (WSL path). Acceptable exception per skill protocol Section 5.
- Compensating control: @qa independently re-ran all six local quality gates in a fresh `/tmp/claude-i-qa-venv` (Python 3.11.12). All passed.
- MEDIUM issues logged as tech debt: 0

### Reference Impact (Code Intelligence)
Skipped — `isCodeIntelAvailable()` not applicable in claude-i repo (no `.aiox-core` infrastructure; greenfield bootstrap).

### Risk Profile
- Depth: **standard**
- Escalation triggers fired: **none**
  - No auth/payment/security files
  - Tests added (4 smoke tests, all passing)
  - Diff 848 lines but distributed across stub modules (<100 lines each)
  - No prior FAIL gate
  - 10 ACs (boundary) — but every AC is a simple existence / exit-code assertion
  - No high-consumer files (greenfield)

### Code Quality Assessment

Excellent. Module boundaries match Dev Notes exactly. `settings.py` is the canonical owner of `HOOK_CMD` and all `~/.claude/settings.json` I/O. `hook.py` delegates via `settings.load_settings()` / `write_settings()`. `runner.py` owns tmux lifecycle. `deps.py` and `reaper.py` are correctly stubbed with forward-compat anchors. `cli.py` is a thin argparse wiring layer.

Defensive improvements over verbatim seed (NOT behavior changes, required by mypy strict):
- `settings.load_settings()` adds `isinstance(parsed, dict)` guard against malformed top-level JSON
- `cli._version_string()` falls back to `__version__` for non-installed checkout
- `hook.install_hook()` adds `assert isinstance(...)` to satisfy mypy strict on `setdefault` returns

Test `test_hook_cmd_is_single_source_of_truth` enforces `hook.HOOK_CMD is settings.HOOK_CMD` (identity, not equality) — excellent future-proofing against accidental shadowing.

Forward-compat anchors preserved as inline comments (G2/G5/G6/G7/G15/G16/G17) at the exact module boundaries downstream stories will target.

### Refactoring Performed

None. Code quality is already at the level @qa would refactor toward.

### Deploy Readiness

Skipped — `deploy_type` is absent / none. Pure library/CLI scaffold.

### Compliance Check

- Coding Standards: [✓] `from __future__ import annotations` everywhere; PEP 8 via ruff; full type hints
- Project Structure: [✓] `src/` layout per Hatchling; tests under `tests/`
- Testing Strategy: [✓] Smoke level appropriate for bootstrap; behavioral coverage deferred to STORY-001.1+
- All ACs Met: [✓] 10/10 verified (AC-7 CI-green-on-bootstrap-commit pending @devops push)

### Improvements Checklist

- [ ] (LOW, future) Remove redundant `tests/.gitkeep` — `tests/__init__.py` already serves as package marker
- [ ] (LOW, future) `runner.tail_pane` broad-except — verbatim seed (AC-9 contract); tighten opportunistically in STORY-001.2

### Security Review

- `permissions: contents: read` on CI workflow — least-privilege.
- `tempfile.mktemp` (deprecated, insecure) is intentionally retained per AC-9 with explicit forward-compat marker for STORY-001.2 gap G5. Documented in `runner.py:66-68`, not hidden.

### Performance Considerations

N/A for bootstrap. Smoke tests run in 0.01s. CI uses `cache: pip` for faster job startup.

### Files Modified During Review

None.

### Gate Status

Gate: **PASS** → `docs/gates/STORY-001.0-gate.md`
Quality score: **96/100**
ACs verified: 10/10 (AC-7 CI-on-bootstrap-commit pending @devops push)
PO conditions: 4/4 met

### Recommended Status

[✓ Ready for Done] — pending: @devops `*push` → CI green confirms AC-7 → @po `*close-story`.
(Story owner decides final status.)

## Closure

| Field | Value |
|---|---|
| Closed by | @po (Pax) |
| Closed on | 2026-05-17 |
| Final status | **Done** |
| QA gate | **PASS 96/100** (see `docs/gates/STORY-001.0-gate.md`) |
| CI confirmation | GREEN — run #26010042733 (Python 3.11 + 3.12 + `check-seed-integrity` job) |
| Pre-closure gates | CHK-8: N/A (`deploy_type: none`; CI run is the external validation) · CHK-9: N/A (no AIOX registry surface in claude-i) · CHK-10: N/A (no service/squad/skill files created — pure Python package scaffold) |
| Phase 1 verification | PASS gate ✓ · 11/11 tasks checked ✓ · 10/10 ACs verified ✓ · File List populated ✓ · Dev Agent Record populated ✓ · QA Results populated ✓ · Status was `In Review` ✓ |

### Notable forward-compat carryover (for downstream stories)

The bootstrap intentionally preserves seed behavior verbatim. Each module carries inline anchors marking where downstream stories will land:

| Gap | Anchor location | Closes in |
|---|---|---|
| G2 — `matcher` / sentinel-keyed hook scoping | `src/claude_i/hook.py:5-7`, `:38-55` | STORY-001.1 |
| G5 — `tempfile.mkstemp` (replace `mktemp`) | `src/claude_i/runner.py:5-7`, `:66-68` | STORY-001.2 |
| G6 — `atexit` + signal cleanup | `src/claude_i/reaper.py:3-5`, `:11-27` | STORY-001.2 |
| G7 — `fcntl.flock` around settings.json mutations | `src/claude_i/settings.py:7-9`, `:50-57` | STORY-001.2 |
| G15 — stale sentinel cleanup | `src/claude_i/cli.py:99-114` (subcommand placeholders) | STORY-001.2 / STORY-001.5 |
| G17 — readiness polling (replaces `--ready-wait`) | `src/claude_i/runner.py:8-10`, `src/claude_i/cli.py` arg shape | STORY-001.5 |

### Velocity probe

STORY-001.0 was the Epic's velocity baseline. Effort 5 pts / ~2 days estimated; delivered same-day from validation through close-out via the @sm → @po → @dev → @qa → @devops → @po cycle. Estimate calibration for downstream stories (28 pts total, 5 stories remaining) stands.

### Next recommended story

**STORY-001.1** — Critical hardening (G1-G4 + partial G12): permission-mode default, hook scoping, dep check, env var hygiene. STORY-001.0 was its only prerequisite — now satisfied. Recommended command: `/validate-story-draft docs/stories/STORY-001.1-critical-hardening.md` once @sm has the draft ready, then `/develop-story` to execute.
