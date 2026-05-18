# STORY-001.5 Quality Gate

| Field | Value |
|---|---|
| Story | STORY-001.5 — Doctor, Reaper, UX: Subcommands, JSON Output, Readiness Polling, G10-G17 Tests |
| Epic | EPIC-001 |
| Gate | **PASS** (re-gate; was CONCERNS 80/100) |
| Quality Score | **95 / 100** |
| Reviewer | Quinn (Test Architect) |
| Review Date | 2026-05-18 (re-gate) |
| Reviewed Commits | initial: `56b2019`, `ed5ca7d`, `3b6edd1`, `c3abdd0`, `edeadc2`, `8e025b0`, `733be58`; re-gate: `36f6ad9` (Q-1/Q-2/Q-3 tests), `e130d8f` (Q-4/Q-5 doc fixes) |
| Risk Profile | deep — final story of EPIC-001, public subcommand surface, signature-breaking refactor (`runner.run()` tuple migration), no CodeRabbit (skipped per mission scope), 8 ACs |
| Expires | 2026-06-01 |

## Re-gate Verdict (2026-05-18, post-Path-A)

**PASS — 95/100.** All 5 issues from initial CONCERNS verdict resolved.

| Issue | Resolution | Evidence |
|---|---|---|
| Q-1 (MEDIUM, G14) | `tests/test_hook.py::test_subagent_stop_deferred` lands (commit `36f6ad9`). Test pins NOTES.md § 'STORY-001.5 — G14 SubagentStop Deferred' header + `SubagentStop` keyword + `DEFERRED` label. If anyone removes the deferral record, this test fires and re-opens the gap. **AC-8 G14 obligation closed via deferral marker.** | ✅ RESOLVED |
| Q-2 (MEDIUM, remove_hook) | `test_hook.py::test_remove_hook_removes_only_claude_i_entry` (line 306) + `test_hook.py::test_remove_hook_noop_when_not_installed` (line 367) both land in `36f6ad9`. | ✅ RESOLVED |
| Q-3 (MEDIUM, cmd_reap) | `test_cli.py::test_reap_subcommand_calls_reap_orphans` (line 537) + `test_cli.py::test_reap_subcommand_zero_count_exits_0` (line 574) both land in `36f6ad9`. | ✅ RESOLVED |
| Q-4 (LOW, AC-3/AC-4 exit codes) | AC-3 and AC-4 now reference `CONFIG_ERROR` (`2`) explicitly with rationale citing STORY-001.2 G8 hardening and STORY-001.1 AC-3 alignment. Story text matches impl. | ✅ RESOLVED |
| Q-5 (LOW, checkbox accuracy) | Task 6.7 test row now points at the delivered `test_subagent_stop_deferred` marker in `test_hook.py` (not the missing `test_runner.py::test_subagent_stop_payload_handled_gracefully`). File List reflects actual delivery. | ✅ RESOLVED |

### Re-run gates (fresh venv, 2026-05-18)

| Gate | Result |
|---|---|
| `python3 -m venv` + `pip install -e ".[dev]"` (Python 3.14) | exit 0 |
| `pytest tests/` | **89 passed** in 0.26s (was 84; +5 net follow-ups) |
| `ruff check .` | All checks passed |
| `mypy --strict src/` | Success: no issues in 8 source files |
| `claude-i --version` | `claude-i 0.2.0` (G4 contract intact) |
| `git diff 3a2be40 HEAD -- seed/claude-i` | empty (seed verbatim from STORY-001.0) |
| `git diff ce6c50a..HEAD -- src/claude_i/reaper.py` | empty (C-1 IDS resolution holds; G6 atexit reaper untouched) |
| G4 sentinel sanitization (runner.py:370 prefix + line 391 `_sanitized_env()`) | INTACT |
| G7 flock parity (`remove_hook` uses same `_settings_flock` as `install_hook`) | INTACT |
| G8 exit codes (named constants throughout `cmd_doctor`/`cmd_uninstall`/`cmd_reap`) | INTACT |

### Acceptance Criteria Verification (post-Path-A)

All 8 ACs now fully met: AC-1 ✓, AC-2 ✓, AC-3 ✓ (text aligned with impl), AC-4 ✓ (text aligned with impl), AC-5 ✓, AC-6 ✓, AC-7 ✓, **AC-8 ✓** (G15 covered + G14 deferral marker test pins NOTES.md record).

### Quality Score Calculation (re-gate)

- 0 FAILs, 1 minor CONCERNS remaining (Reliability NFR — G14 functional handling is deferred per documented investigation, only the deferral marker is tested; this is a known epic-level deferral, same pattern as G2 in STORY-001.1).
- Score: `100 - (5 × 1) = 95`.
- Two LOW items from initial review (Q-4, Q-5) both resolved (not deducted; LOW = note only).

### Recommended Next

- @devops `*push` final 001.5 commits (`36f6ad9`, `e130d8f`) → main
- @po `*close-story STORY-001.5` (mark Done, PASS gate accepted)
- @po `*close-epic EPIC-001` ceremony: v0.2.0 tag → `gh workflow run publish.yml` → Task 5.9 Homebrew Formula URL flip → operator brew smoke → Epic DoD verification

### Status (re-gate)

**[✓ Approved — Ready for Done]**

---

## Original CONCERNS verdict (preserved for audit trail)

## Status Reason

Implementation is solid and the three @po NO-GO findings (C-1 IDS, C-2 orphan-only, C-3 signature migration) are genuinely resolved end-to-end. 84/84 pytest PASS, ruff clean, mypy `--strict` clean (8 sources), `seed/claude-i` byte-identical, `--version` = `claude-i 0.2.0`. Core contracts from prior stories are intact (G4 sentinel sanitization, G6 atexit reaper, G7 flock on both install AND remove, G8 exit codes, G9 Windows guard).

Gate is **CONCERNS** (not PASS) for two clusters:

1. **AC-8 partially unmet.** AC-8 requires tests cover G14 AND G15. G15 is well-covered (2 tests in `test_runner.py`). G14 has **zero tests** — neither a graceful-handling test nor a deferral-marker test. The File List entry claims `tests/test_* — G14 test marker (deferred per Task 6.7)` but no such marker exists in any test file. Task 6.7 listed `test_runner.py::test_subagent_stop_payload_handled_gracefully` as required output; this test does not exist.
2. **Three checked task obligations have no corresponding tests** despite checkboxes `[x]`:
   - Task 6.2: `test_hook.py::test_remove_hook_removes_only_claude_i_entry` + `test_hook.py::test_remove_hook_noop_when_not_installed` — **not present** (test_hook.py: 13 tests baseline → 13 tests now; zero additions).
   - Task 6.3: `test_cli.py::test_reap_subcommand_calls_reap_orphans` + `test_cli.py::test_reap_subcommand_zero_count_exits_0` — **not present** (cmd_reap CLI wiring untested; the underlying `reap_orphans()` IS tested from 001.2, but the new subcommand glue is not).
   - Task 6.7 / G14: `test_subagent_stop_payload_handled_gracefully` — **not present** (per cluster 1).

The story claims "+16 new tests" — true in total count (16 net adds), but the distribution misses 4–5 tests promised by the Task list. Gate semantics: checked-but-unwritten tests are a process violation, not a functional defect. Functionality works; coverage claim diverges from delivery.

## @po NO-GO Resolutions

| Finding | Required Resolution | Verification | Status |
|---|---|---|---|
| **C-1** — IDS violation: redefining `reap_orphans` | Wire existing `reaper.reap_orphans()` to new `cmd_reap` (ADAPT > CREATE) | `git log -- src/claude_i/reaper.py` last touched `e2205bb` (STORY-001.2). `git diff ce6c50a HEAD -- src/claude_i/reaper.py` = empty. `cli.py:494` calls `reaper.reap_orphans()` directly with no shadow logic. | ✅ RESOLVED |
| **C-2** — AC-4 orphan-only semantic | AC-4 reworded to "kills all *orphaned* tmux sessions" with live owners protected | `reap_orphans()` filters via `_pid_alive` (unchanged from 001.2); `cmd_reap` is a thin wrapper that adds only the tmux-on-PATH precheck. Live sessions remain intact. | ✅ RESOLVED |
| **C-3** — `runner.run()` signature break unmentioned | Add Task 6.4a; migrate to `tuple[str, RunMetadata]`; update all callsites atomically | Commit `56b2019` lands the migration in one atomic refactor commit. `RunMetadata: TypedDict` defined in `runner.py:54`. 13 `runner.run(...)` callsites total (1 production + 12 test); all destructure correctly. Primary caller `cli.py:565` does `response, metadata = runner.run(...)`. All 84 tests PASS post-migration. | ✅ RESOLVED |

## Independent Quality Gates (re-run by @qa, fresh venv)

| Gate | Result | Notes |
|---|---|---|
| Fresh `python3 -m venv` + `pip install -e ".[dev]"` | exit 0 | Python 3.14, clean install on `/tmp/claude-i-qa-venv-001-5` |
| `pytest tests/` | **84 passed** in 0.27s | +16 net vs 001.4 baseline (68); distribution: test_cli +10, test_runner +6, test_hook +0 |
| `ruff check .` | All checks passed | — |
| `mypy --strict src/` | Success: no issues in 8 source files | — |
| `claude-i --version` | `claude-i 0.2.0` | G4 contract intact |
| `claude-i --help` | Lists doctor / uninstall / reap subcommands + `--output-format` + `--ready-wait` + `--allow-empty` + `--permission-mode` | AC compliance: Task 6.8 ✓ |
| `claude-i doctor` | Runs 5 checks; FAILs on missing hook in fresh venv (expected) | AC-1 ✓ structure; exit code semantics correct |
| `claude-i doctor --json` | Valid JSON `{"checks": [...], "overall": "..."}` | AC-2 ✓ |
| `claude-i reap` (no tmux sessions present) | `no orphaned sessions found`, exit 0 | AC-4 ✓ |
| `seed/claude-i` integrity | Last touched `3a2be40` (STORY-001.0); zero diff from epic start | Verbatim seed preserved (AC from 001.0) |
| Reaper.py preserved | `git diff ce6c50a..HEAD -- src/claude_i/reaper.py` = empty | C-1 resolution verified at the file level |
| Hook.py flock parity | `remove_hook()` uses same `_settings_flock` helper as `install_hook()` (hook.py:205-269) | G7 contract symmetric |
| Runner sentinel sanitization | `CLAUDE_I_SENTINEL=` shell prefix (runner.py:370) + `env=_sanitized_env()` (runner.py:391) | G4 contract intact |

## Acceptance Criteria Verification

| AC | Description | Status | Evidence |
|---|---|---|---|
| **AC-1** | `doctor` runs 5 checks, exits 0/1 | ✅ PASS | `cmd_doctor` (cli.py:408) iterates 5 check functions; 7 tests in `test_cli.py:329-501` cover all-pass, missing-tmux, missing-hook, malformed-settings, stale-sentinel, and age-filter |
| **AC-2** | `doctor --json` outputs `{"checks": [...], "overall": "..."}` | ✅ PASS | `test_doctor_json_output` (test_cli.py:466) asserts schema |
| **AC-3** | `uninstall` removes claude-i hook, preserves others, exits 0 on no-op, **1 on malformed JSON** | ⚠ PASS-with-drift | Implementation correct (`hook.remove_hook()` uses same flock, filters via `_is_claude_i_hook_entry`, returns count). HOWEVER: AC literal "exits 1" contradicts impl `CONFIG_ERROR` (=2). The 2-exit-code is consistent with STORY-001.2 G8 hardening (malformed config = 2, not 1) and matches `install_hook` symmetry. **Defensible drift**, story text out of sync with project convention. **No tests for `cmd_uninstall` or `remove_hook`** (see CONCERNS) |
| **AC-4** | `reap` kills orphans only, live owners protected, exits 1 if tmux missing | ⚠ PASS-with-drift | Functionality correct (delegates to `reap_orphans` which already orphan-filters per C-2). Tmux-missing path returns `CONFIG_ERROR` (=2), AC literal says "1". Same drift cluster as AC-3. **No tests for `cmd_reap` wiring**. |
| **AC-5** | `--output-format json` shape | ✅ PASS | `test_output_format_json_structure` + `test_output_format_json_null_fields_when_absent` (test_cli.py:241,276); `duration_ms` always populated via `time.monotonic()` |
| **AC-6** | Readiness poller replaces fixed sleep; 250ms interval; `--ready-wait` cap | ✅ PASS | `_wait_for_tui_ready` (runner.py:192); 4 tests cover prompt-detected, timeout, zero-timeout shortcut, unicode prompt. `--ready-wait` default raised to 10.0 (was 4.0). `TUI_READY_PATTERN` overridable via `settings.py` |
| **AC-7** | Stale sentinel cleanup on every run (>24h, best-effort silent) | ✅ PASS | `_cleanup_stale_sentinels` (runner.py:151) called at top of `run()` (runner.py:353); 2 tests in `test_runner.py:573,607` cover happy path + silent error swallowing |
| **AC-8** | Tests cover **G14 AND G15** | ⚠ FAIL | G15 ✓ (test_runner.py:573,607). G14 ✗ — zero tests, zero deferral markers. File List claims a marker that doesn't exist. |

**Summary: 7/8 ACs fully met, AC-8 partially unmet (50% — G15 only).**

## G-Gap Coverage Audit (Epic-Close Readiness)

| Gap | Source Story | Resolution | Evidence in 001.5 |
|---|---|---|---|
| G4 | 001.1 | sentinel sanitization | `runner.py:74,243,370,391` — INTACT |
| G6 | 001.2 | atexit reaper | `reaper.py:95-143` — UNCHANGED |
| G7 | 001.2 | flock on settings.json | `hook.py:163,205` — both install + remove use `_settings_flock` |
| G8 | 001.2 | exit codes | `exit_codes.py` unchanged; cmd_doctor/uninstall/reap use named constants |
| G9 | 001.4 | Windows guard | `deps.py` unchanged |
| G10 | 001.5 | streaming output | DEFERRED with rationale in story Dev Notes — accepted: architecture incompatible, `--verbose` is proxy |
| G11 | 001.5 | metadata via `--output-format json` | IMPLEMENTED (AC-5) |
| G12 | 001.5 | runtime hook verification | IMPLEMENTED via doctor check (c) (AC-1c) |
| G13 | n/a | — | (no such gap in epic registry) |
| **G14** | 001.5 | SubagentStop handling | **DEFERRED in NOTES.md** but AC-8 promised a test that does not exist |
| **G15** | 001.5 | stale sentinel accumulation | IMPLEMENTED + tested (AC-7 + AC-8 G15 portion) |
| G16 | 001.5 | doctor/uninstall/reap subcommands | IMPLEMENTED (AC-1/AC-3/AC-4) |
| G17 | 001.5 | readiness polling | IMPLEMENTED + tested (AC-6) |
| G18 | n/a | — | (epic-level DoD) |

**G14 deferral assessment:** NOTES.md `STORY-001.5 — G14 SubagentStop Deferred` (lines 125-158) is well-structured — sources consulted, empirical test on claude-code 2.1.143, no distinct event observed in transcript payload, revisit triggers documented. The deferral itself is **acceptable** (same pattern as G2 in 001.1). The gap is that AC-8 verbatim says "Tests cover G14" — a deferral-marker test (e.g., `test_subagent_stop_deferred` xfail or pytest.skip with reason) would have closed AC-8 without implementation.

## Top Issues

| ID | Severity | Description | File | Suggested Owner |
|---|---|---|---|---|
| Q-1 | **MEDIUM** | AC-8 partially unmet: no G14 test (neither functional nor deferral marker). Story File List claims a marker that does not exist. | `tests/test_runner.py` or `tests/test_hook.py` | dev |
| Q-2 | **MEDIUM** | Task 6.2 promised 2 `test_hook.py` tests (`test_remove_hook_*`) — neither exists. `remove_hook()` is untested at the unit level. | `tests/test_hook.py` | dev |
| Q-3 | **MEDIUM** | Task 6.3 promised 2 `test_cli.py` tests (`test_reap_subcommand_*`) — neither exists. `cmd_reap` CLI wiring is untested (the underlying `reap_orphans` IS tested from 001.2, but the new glue isn't). | `tests/test_cli.py` | dev |
| Q-4 | **LOW** | AC-3 says "exits 1" on malformed JSON; impl returns 2 (CONFIG_ERROR). AC-4 says "exits 1" if tmux missing; impl returns 2. Both are defensible per STORY-001.2 G8 hardening (malformed config = 2), but the story AC text never got the memo. Recommend a 1-line AC clarification at epic close, or accept the drift in QA Results. | `docs/stories/STORY-001.5-doctor-reaper-ux.md` (AC-3, AC-4) | po |
| Q-5 | **LOW** | Story Tasks/Subtasks 6.2, 6.3, 6.7 have `[x]` on test sub-bullets that were not delivered. Checkbox accuracy drift. | `docs/stories/STORY-001.5-doctor-reaper-ux.md` | dev |

**Severity rule applied:** MEDIUM → Gate CONCERNS (not FAIL). Per skill rules, FAIL requires either security/data-loss P0 test missing or any HIGH severity. G14 graceful handling is operational quality, not security/data-loss.

## NFR Validation

| NFR | Status | Notes |
|---|---|---|
| Security | PASS | `_sanitized_env()` strips CLAUDE_I_SENTINEL from child env (runner.py:240); flock on settings.json mutations (hook.py:102); no privilege escalation surface |
| Performance | PASS | Readiness poller 250ms interval (configurable); doctor stale check globs `/tmp` (cheap); JSON output is constant overhead |
| Reliability | CONCERNS | G14 SubagentStop edge case has no test; cmd_uninstall has no test; cmd_reap glue has no test. Functionality verified by hand but not by automation |
| Maintainability | PASS | All new code typed (`RunMetadata: TypedDict`); docstrings cite story IDs + gap numbers; subcommand dispatch is single-responsibility; checkbox-vs-delivery drift is the only smell |

## Refactoring Performed

None. Implementation is well-structured; no in-place refactoring needed.

## Files Modified During Review

None. QA Results section will be appended to the story; no source file touched.

## Recommendations

### Immediate (before epic close)

1. **@dev**: Add 4 small tests to close the AC-8 / Task 6.2 / Task 6.3 / Task 6.7 gaps:
   - `tests/test_hook.py::test_remove_hook_removes_only_claude_i_entry` — settings.json with claude-i hook + user hook → after `remove_hook()`, user hook preserved, claude-i absent, returns 1.
   - `tests/test_hook.py::test_remove_hook_noop_when_not_installed` — empty settings.json → `remove_hook()` returns 0, no raise.
   - `tests/test_cli.py::test_reap_subcommand_zero_count_exits_0` — monkeypatch `reaper.reap_orphans` → 0, monkeypatch `shutil.which("tmux")` → "/usr/bin/tmux", call `cmd_reap`, assert exit 0 + "no orphaned sessions" in stdout.
   - `tests/test_runner.py::test_subagent_stop_payload_handled_gracefully` (or `test_subagent_stop_deferred` with `pytest.skip(reason="G14 — see NOTES.md")`) — closes AC-8 G14 obligation.

   Estimated effort: **~30 minutes**. Re-gate to PASS after these land.

2. **@po**: One-line AC clarification (or QA Results note) — exit codes 1 vs 2 for AC-3 (malformed JSON) and AC-4 (missing tmux). Story text says 1, impl says 2 (CONFIG_ERROR per G8 hardening). Convention wins; story should align.

3. **@dev**: Uncheck the 3 affected task sub-bullets (Tasks 6.2, 6.3, 6.7 test rows) until the tests land, OR strike the rows with a note. Checkbox accuracy matters for future audits.

### Future (epic-close ceremony, post-001.5 close)

Per @po validation findings (Epic-Close Decision section in story):

1. @devops `*push` final 001.5 commits → main
2. @devops tag `v0.2.0` + `git push --tags`
3. @devops `gh workflow run publish.yml` → approve `publish` environment gate
4. @devops Task 5.9 (carried from 001.4): regenerate formula URL + SHA256 against canonical PyPI artifact, push to `homebrew-claude-i`
5. Operator (Rafael) — clean macOS `brew tap` + `brew install` + `claude-i --version` smoke
6. @po `*close-epic EPIC-001` — verify all 8 G-gaps closed-or-deferred, mark Epic Done

**These are NOT part of STORY-001.5 scope.** The story Dev Notes correctly hold them as epic-level DoD items.

## Quality Score Calculation

- 0 FAILs (no HIGH-severity issues, no security/data-loss P0 missing tests, no CodeRabbit exhaustion).
- 4 CONCERNS items (Q-1 G14 test missing, Q-2 remove_hook tests missing, Q-3 cmd_reap tests missing, Reliability NFR=CONCERNS).
- Score: `100 - (5 × 4) = 80`. Two LOW items (Q-4, Q-5) noted but not deducted (LOW = note only).

## Epic-Close Readiness

**Blockers before v0.2.0 tag ceremony:** NONE that prevent the tag itself. The CONCERNS items are **test coverage debt**, not functional defects. The implementation works end-to-end.

**Recommended sequencing:**

| Path | Description |
|---|---|
| **A (recommended)** | @dev addresses Q-1/Q-2/Q-3 (30 min, 4 tests) → re-gate to PASS → @po closes story → @devops runs epic-close ceremony. Clean ledger, no test debt carried into v0.2.0. |
| **B (acceptable)** | @po accepts CONCERNS as written, documents the 3 missing test groups as a 001.5-followup item in EPIC-001 close notes, ships v0.2.0. Test debt carried but visible. |

**Either path unblocks the v0.2.0 tag.** No security or data-loss risk surface.

## Recommended Status

**[✗ Changes Required — See unchecked items above]**

Story owner (@po) decides between Path A (add the 4 missing tests, re-gate to PASS) and Path B (accept CONCERNS, ship with test debt logged in epic-close notes). Either way, **EPIC-001 v0.2.0 release ceremony is unblocked** — the gap is process accuracy (checkbox vs delivery) and test coverage debt, not functional or security risk.

## Handoff

| If | Next Agent | Next Command |
|---|---|---|
| Path A chosen | @dev | Add 4 tests; commit; request re-review via `*review-story 001.5` |
| Path B chosen | @po | `*close-story STORY-001.5` with CONCERNS gate accepted; note test debt in EPIC-001 close ledger |
| After story Done (either path) | @devops | `*push` → tag `v0.2.0` → `gh workflow run publish.yml` (epic-close ceremony per @po decision) |

---

*Gate file: `docs/gates/STORY-001.5-gate.md` | Story: `docs/stories/STORY-001.5-doctor-reaper-ux.md` | Reviewer: Quinn (Test Architect) | 2026-05-18*
