# STORY-001.8 Validation (@po Pax)

**Date:** 2026-05-19
**Validator:** @po (Pax)
**Story:** STORY-001.8 — Bug 6: tmux paste-buffer / Enter Race
**Verdict:** **NEEDS_REVISION** (4 items, none HIGH-severity blockers; all can be fixed in-line)

## Phase 0 — Epic Context (D10 incremental review)

Reviewed all 7 prior closed stories (STORY-001.0 through STORY-001.7). Key cross-cutting contracts that STORY-001.8 must NOT break:

| Contract | Source | Conflict with 001.8? |
|---|---|---|
| G4 two-layer sentinel sanitization | STORY-001.1 | No — fix is downstream of session spawn |
| G5 `tempfile.mkstemp` atomic | STORY-001.2 | No — pre-prompt-delivery |
| G6 reaper / SIGTERM cleanup | STORY-001.2 | No — orthogonal |
| G7 `fcntl.flock` on settings | STORY-001.2 | No — runner does not touch settings |
| G8 four-branch RuntimeError contract | STORY-001.2 | No — exit codes unchanged |
| G13 UTF-8 encoding via `tmux()` | STORY-001.2 | **Reaffirmed** by AC-4 |
| Seed integrity (byte-identical) | STORY-001.0 | Confirmed in File List |
| Atomic-rename HOOK_CMD | STORY-001.6 | No — independent layer |
| `_wait_for_payload` 2s grace | STORY-001.6 | No — fires AFTER Bug 6 fix point |
| `_TRANSCRIPT_RETRY_SECONDS` | STORY-001.7 | No — fires AFTER Bug 6 fix point |
| Payload-first extraction | STORY-001.7 | No — fires AFTER Bug 6 fix point |
| `--retries N` flag | STORY-001.7 | **Synergistic** — Bug 6 fixes the per-attempt path; retries cover Bug 5 burst hang |

**Cross-story consistency:** No conflicts. STORY-001.8 modifies a narrowly-scoped 3-line block in `runner.run()` (the prompt-delivery section) and is orthogonal to every contract above.

## Phase 1 — 10-point Validation

| # | Check | Verdict | Detail |
|---|---|---|---|
| 1 | AC clarity & testability | PASS | All 9 ACs have concrete pass/fail criteria. |
| 2 | Task decomposition (1 → many ACs) | PASS | 6 tasks, each cited to specific ACs. |
| 3 | IDS principle (REUSE > ADAPT > CREATE) | PASS | ADAPT `runner.run` (3-line block); REUSE `tmux()` wrapper; REUSE existing test fixtures. No new modules. |
| 4 | File List accuracy | **REVISION** (P-1) | Missing: `tail_pane`/verbose path is touched (zero diff but should be explicitly noted to dispel reviewer doubt). |
| 5 | Testing plan coverage | **REVISION** (P-2) | AC-7 prompt is too short (~32 chars) — would pass even WITHOUT the Bug 6 fix. Test does not actually validate the fix it claims to. |
| 6 | Dev Notes / risk register | PASS | Corner cases (newlines, tabs, escape sequences, threshold) explicitly addressed. |
| 7 | Dependency chain explicit | PASS | Depends on STORY-001.7 (Done); v0.2.2 released. |
| 8 | DoD achievable in estimate | PASS | 2 pts / 2h realistic — fix is 3 lines + 5 tests + version bump. |
| 9 | Acceptance Test plan complete | **REVISION** (P-3) | Slash skill (`/idea`) scenario not explicitly tested. Bug 2b in the empirical bench showed `/idea` failed; the Bug 6 fix should resolve it. Missing test = missing regression guard. |
| 10 | Documentation surface | **REVISION** (P-4) | Task 9.6 (Homebrew bump) is mentioned but with no explicit dependency ordering. Bumping the formula BEFORE v0.2.3 is tagged + released would point at a non-existent SHA256. Task ordering must be sequenced. |

## Findings (must address before implementation)

### P-1 (LOW) — File List should explicitly state `tail_pane` unchanged

**Where:** `## File List` → `Unchanged (verified)`
**Add:** `tail_pane()` in `runner.py:tail_pane` is also unchanged. It calls `tmux capture-pane` which is on the READ side (separate from the prompt-delivery WRITE side). The verbose mode that uses `tail_pane` continues to work identically after this story.
**Why it matters:** A reviewer reading the story alone could wonder whether changing the prompt-delivery mechanism affects verbose tail. An explicit "unchanged" entry kills that doubt and saves review back-and-forth.

### P-2 (MEDIUM) — AC-7 / Task 9.3 prompt does NOT validate the fix

**Where:** AC-7 + Task 9.3 second bullet
**Current:** `claude-i --retries 1 "@analyst help me with a question"` (~32 chars)
**Problem:** Empirical test bench (2026-05-19) showed that 32-char prompts already work on v0.2.2 — including `@analyst help me with a question` succeeded in 11s without ANY Bug 6 fix. This test would pass on v0.2.2 too, so it does NOT validate AC-7's intent ("the fix unblocks AIOX agent invocation").
**Fix:** Change the prompt to something ≥ 60 chars that exercises the same agent capability. Suggested: `"Como @analyst Atlas, suggest one specific risk for the claude-i project's current dependency on Anthropic's Claude Code CLI."` (~125 chars). Adjust AC-7 text accordingly.

### P-3 (MEDIUM) — Add slash-skill regression test

**Where:** AC-6 / AC-7 + Task 9.3
**Problem:** The empirical bench showed `/idea` (Test 2b) failing even with `--timeout 300`. This is a direct Bug 6 symptom (Enter never submits after `/` triggers a menu OR the prompt is too long for paste-buffer). The story does not have an explicit test that the Bug 6 fix resolves this scenario.
**Fix:** Add a third sub-bullet under Task 9.3:
> `tests/test_integration_e2e.py::test_e2e_slash_skill_invocation` — `claude-i --retries 1 "/idea anota: claude-i v0.2.3 reliability test 2026-05-19"` (~70 chars) → exit 0 + non-empty stdout. Failing this test means slash commands are still broken; passing locks the contract.

Add a corresponding **AC-7b**:
> **AC-7b (slash command invocation works):** A new integration test `test_e2e_slash_skill_invocation` runs `claude-i --retries 1 "/idea anota: <text>"` (~70 chars) and asserts exit 0 + non-empty stdout.

### P-4 (HIGH-process-ordering) — Task 9.6 must sequence AFTER release tag

**Where:** Task 9.6 (Homebrew formula bump)
**Problem:** The formula needs the v0.2.3 sdist SHA256, which only exists AFTER:
1. Bump commit pushed
2. Tag `v0.2.3` created and pushed
3. GitHub Release v0.2.3 created with sdist attached
4. SHA256 of the released sdist computed

If Task 9.6 runs before step 3, it would commit a placeholder/wrong SHA256, breaking the formula until manually patched.
**Fix:** Either (a) move Task 9.6 to a new explicit "Release Ceremony" subsection AFTER Task 9.5, with the dependency chain spelled out; or (b) split Task 9.6 into 9.6a (compute v0.2.3 sdist sha256, prepare formula diff) and 9.6b (commit formula after release tag is live). I recommend (a) for clarity.

Suggested new Task 9.6 wording:

> - [ ] 9.6 — Release ceremony (Homebrew formula bumps AFTER release)
>   - [ ] 9.6.1 — Commit + push all source changes (Tasks 9.1–9.5) to `main`
>   - [ ] 9.6.2 — Tag `v0.2.3` and push tag
>   - [ ] 9.6.3 — Build sdist + wheel locally, attach to GitHub Release `v0.2.3` via `gh release create`
>   - [ ] 9.6.4 — Compute SHA256 of the released sdist (`shasum -a 256 dist/*.tar.gz`)
>   - [ ] 9.6.5 — Update `~/Projects/AIOX/homebrew-claude-i/Formula/claude-i.rb` (url + sha256 + test assertion) and push
>   - [ ] 9.6.6 — `brew upgrade rafaelscosta/claude-i/claude-i` smoke test → `claude-i --version` → `claude-i 0.2.3`

## Issues NOT raised (intentional)

- **No HIGH-severity blockers.** The 4 findings are all narrow doc/test refinements; none touch the implementation approach (`send-keys -l`) which is empirically validated.
- **No IDS violation.** The fix is ADAPT-of-3-lines; no new module / no shadow logic.
- **No security regression surface.** `send-keys -l <prompt>` is fed into the SAME tmux subprocess that already received the prompt via paste-buffer. Trust boundary unchanged.

## Recommendation

**Apply P-1 / P-2 / P-3 / P-4 inline to the story doc**, then mark Status: **In Progress** and hand off to @dev. Expected effort to apply revisions: ~10 minutes (text-only edits). No new code needed for the revisions themselves.

After revisions land, @dev starts Task 9.1 immediately. Implementation effort estimate of 2 pts / ~2h holds.

---

*Validation file: `docs/stories/STORY-001.8-validation.md` | Story: `docs/stories/STORY-001.8-tmux-paste-race.md` | 2026-05-19*
