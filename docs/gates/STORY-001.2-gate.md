# STORY-001.2 Quality Gate

| Field | Value |
|---|---|
| Story | STORY-001.2 — Important Hardening: mkstemp, Reaper/atexit, flock, Exit Codes, Windows Guard, Encoding |
| Epic | EPIC-001 |
| Gate | **PASS** |
| Quality Score | **95 / 100** |
| Reviewer | Quinn (Test Architect) |
| Review Date | 2026-05-18 |
| Reviewed Commits | `72869d7`, `e2205bb`, `51af081`, `1df43e5`, `8e469b9`, `14205d4`, `00c375a`, `3a80b73` (8 ahead of `origin/main`) |
| Risk Profile | standard |
| Expires | 2026-06-01 |

## Status Reason

All 7 ACs verified satisfied. 68/68 pytest pass in a fresh venv (Python 3.14.3), ruff clean (S306 actively catches mktemp regression — verified), mypy strict clean across 8 source files, seed verbatim (empty diff vs 001.1 close), `--version` regression intact, exit-code epilog rendered with all 4 codes. **G4 two-layer contract intact** — both `CLAUDE_I_SENTINEL=` shell prefix at `runner.py:166` and `env=_sanitized_env()` kwarg at `runner.py:187` present; the G4 test pair (`test_sentinel_stripped_from_subprocess_env` + `test_sentinel_still_in_sh_command`) passes. `assert_not_windows()` has exactly **one** definition in `deps.py:128` (stub replaced, not duplicated). All 4 AC-7 parse-failure branches landed (3 RuntimeError at lines 246/251/265 + 1 explicit `return ""` at 271). 8 atomic commits, each scoped to a single gap (G5/G6/G7/G8/G9/G13) + 1 test consolidation + 1 docs commit, each bisectable.

## Independent Quality Gates (re-run by @qa)

| Gate | Result | Notes |
|---|---|---|
| `python3 -m venv` + `pip install -e ".[dev]"` (fresh) | exit 0 | Python 3.14.3 |
| `pytest tests/` | **68 passed** in 0.10s | Matches @dev's count |
| `ruff check src/ tests/` | All checks passed | — |
| `mypy --strict src/claude_i/` | Success: no issues in 8 source files | — |
| `git diff seed/claude-i` (vs 001.1 close) | empty | Seed integrity preserved |
| `claude-i --version` | `claude-i 0.2.0.dev0` | No callbacks fired |
| `claude-i --help` | Exit-code epilog: 0/1/2/3 all enumerated | — |
| `ruff S306` regression smoke | `Found 1 error` on `tempfile.mktemp()` | Guard active |

## AC Validation

| AC | Status | Evidence |
|---|---|---|
| AC-1 (mkstemp, no mktemp in src) | PASS | `grep` shows `mkstemp` at `runner.py:157`, zero `mktemp` call sites; `S306` ruff rule active and verified to catch regression |
| AC-2 (atexit + SIGTERM reaper, SIGKILL doc) | PASS | `reaper.register_cleanup()` wires `atexit` + `SIGTERM` handler; `--help` notes SIGKILL best-effort |
| AC-3 (fcntl.flock on settings.json, 5s timeout, exit 1) | PASS | `_acquire_lock_with_retry()` at `hook.py:101–144` with deadline-based retry + `sys.exit(RUNTIME_ERROR)` on timeout; wraps only `install_hook()` write path, leaves `hook_installed()` read-only untouched (G2 deferral preserved) |
| AC-4 (exit 1 runtime, exit 0 success / opt-in empty, `--allow-empty`) | PASS | `cli.py` adds `--allow-empty`; RuntimeError → exit 1; empty without flag → exit 1; empty with flag → exit 0 |
| AC-5 (native Windows → exit 3 + WSL2 URL) | PASS | `assert_not_windows()` at `deps.py:128` with strict `sys.platform == "win32"` check; verbatim message; `sys.exit(PLATFORM_ERROR)`; called first in `check_deps()` |
| AC-6 (UTF-8 encoding, warn-and-continue) | PASS | Best-effort `prompt.encode("utf-8")` round-trip check; `encoding="utf-8"` propagated to subprocess calls |
| AC-7 (4 distinguishable runner.run() branches) | PASS | Branch 1 `return ""` at line 271; Branch 2 `RuntimeError("no assistant message")` at 265; Branch 3 `RuntimeError("hook fired but no payload written")` at 246; Branch 4 `RuntimeError("transcript missing")` at 251; all 4 dedicated tests present and passing |

## NFR Validation

| NFR | Status | Notes |
|---|---|---|
| Security | PASS | TOCTOU race closed (mkstemp), advisory lock on settings, sentinel sanitization preserved from 001.1 |
| Performance | PASS | Lock acquisition 100ms retry / 5s deadline; no hot-path regressions |
| Reliability | PASS | atexit + SIGTERM reaper covers normal exit, KeyboardInterrupt, SIGTERM; finally cleanup retained (belt-and-braces); silent cleanup avoids masking real errors |
| Maintainability | PASS | Named `ExitCode` constants replace bare integer literals across 5 modules; cross-module imports clean (no circulars); docstrings enumerate all 4 AC-7 branches |

## Top Issues

None blocking. Two minor observations recorded as `future` recommendations.

## Recommendations

### Immediate
None.

### Future
1. **action:** Append G14 (SubagentStop discovery) + G17 (readiness polling) carryovers to `NOTES.md` for operator visibility (currently only documented in story Dev Agent Record). 001.1 convention puts deferrals in NOTES.md; story-level is acceptable but NOTES.md is more discoverable post-merge.
   **refs:** `NOTES.md`
   **suggested_owner:** dev
2. **action:** Migrate `reaper.py:74` bare `sys.exit(1)` in `_sigterm_handler` to `sys.exit(RUNTIME_ERROR)` for consistency with the named-constant convention adopted in G8. Functionally identical (1 == RUNTIME_ERROR); cosmetic improvement only.
   **refs:** `src/claude_i/reaper.py:74`
   **suggested_owner:** dev

## Quality Score Calculation

```
quality_score = 100 - (20 × 0 FAILs) - (5 × 0 CONCERNS) - 5 future-debt discount
            = 95
```

The 5-point discount reflects two `future` recommendations (NOTES.md carryover documentation, reaper.py bare integer cosmetic) — neither blocks PASS but both represent residual polish.

## Risk Profile

**standard** — no auto-escalation triggers fired:
- Touched files: no auth/payment/security paths
- Tests: 38 new tests added (68 total vs 30 at 001.1 close)
- Diff: well-scoped per gap; largest single commit (G8) is 406 lines across 8 files but each change is localized
- Previous gate (001.1): PASS 94/100
- AC count: 7 (within threshold)
- Reference impact: not measured (code intel unavailable in this repo)

## CodeRabbit Self-Healing

Skipped per operator instruction in mission ("Skip CodeRabbit. Re-run gates independently in fresh venv."). Gates re-run independently verified all green.

## Deploy Readiness

Skipped — `Deploy Type: none` (Python library/CLI, no production deploy).

## Compliance Check

- Coding Standards: ✓ Python 3 type hints, docstrings present on all new functions, `from __future__ import annotations` used consistently
- Project Structure: ✓ exit_codes.py placed in package (not in cli.py per @architect rationale documented in module docstring — avoids circular import via cli)
- Testing Strategy: ✓ unit tests with mocks, no real tmux/claude invocation, deterministic
- All ACs Met: ✓ 7/7

## Files Modified During Review

None — review was read-only.

## Gate Decision Application (Deterministic Order)

1. CodeRabbit self-healing exhausted? → No (skipped per operator)
2. Risk thresholds exceeded? → No
3. Test coverage gaps (P0)? → No — all 7 ACs traced to passing tests
4. Issue severity high/medium? → No
5. NFR statuses? → All PASS

**Final Gate: PASS**

## Recommended Next

@devops `*push` (8 commits ready) → @po `*close-story` (move STORY-001.2 to Done, update epic tracker).
