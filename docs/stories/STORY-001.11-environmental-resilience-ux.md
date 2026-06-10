# STORY-001.11: Environmental Resilience UX for Bug 5

| Field | Value |
|---|---|
| Status | Done |
| Epic | EPIC-001 maintenance |
| Owner | @dev (Dex) |
| Executor | @dev |
| Quality Gate | @qa |
| Accountable | rafaelscosta |
| deploy_type | none |
| Created | 2026-06-10 |
| Estimated | 1 pt |

## User Story

As an operator running `claude-i` in scripts or high-burst workflows, I want Stop-hook signal timeouts to be classified with clear retry guidance, so I can distinguish documented environmental Bug 5 from a `claude-i` payload/parser regression.

## Context

Bug 5 is already documented as an upstream/environmental Claude Code session hang under burst load. `claude-i` cannot force the sub-`claude` process to produce a Stop hook event, but it can make the failure actionable.

Before this story, a final timeout printed the raw runner error. Operators had to remember the README/NOTES guidance manually.

## Acceptance Criteria

- **AC-1:** Final `No Stop hook signal` failures name documented Bug 5.
- **AC-2:** Single-shot callers are told to use `--retries 3` for automation.
- **AC-3:** Exhausted retry callers are told all attempts were exhausted and pointed to `--retries 5` plus pacing for high-burst workflows.
- **AC-4:** Error handling keeps the same exit code (`1`) and does not change retry semantics.
- **AC-5:** Non-Bug-5 `RuntimeError` / `TimeoutError` messages continue to surface without Bug 5 guidance.
- **AC-6:** README and NOTES match the new operator-facing behavior.

## Tasks / Subtasks

- [x] 12.1 Add Bug 5 final-error formatter.
- [x] 12.2 Keep retry loop semantics unchanged.
- [x] 12.3 Add CLI tests for no-retry and exhausted-retry guidance.
- [x] 12.4 Update README/NOTES operator guidance.
- [x] 12.5 Run validation and close gate.

## File List

**Modified:**

- `src/claude_i/cli.py`
- `tests/test_cli.py`
- `README.md`
- `NOTES.md`
- `docs/stories/STORY-001.11-environmental-resilience-ux.md`
- `docs/gates/STORY-001.11-gate.md`

## Dev Notes

- This story deliberately does not change default retry behavior.
- This story does not attempt to mask an upstream hang as success.
- Future enhancement, if needed: add a richer `doctor --verbose` host-pressure report.

## Dev Agent Record

### Implementation Summary

- Added `_format_final_run_error()` and `_looks_like_stop_signal_timeout()` in `cli.py`.
- Final `No Stop hook signal` failures now include Bug 5 classification, retry level guidance, and `claude-i doctor` guidance.
- Added tests for single-shot guidance and exhausted retry guidance.

### Validation

See `docs/gates/STORY-001.11-gate.md`.
