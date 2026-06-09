# STORY-001.10: Late Stop-Hook Artifact Cleanup

| Field | Value |
|---|---|
| Status | Done |
| Epic | EPIC-001 maintenance |
| Owner | @dev (Dex) |
| Executor | @dev |
| Quality Gate | @qa |
| Accountable | rafaelscosta |
| deploy_type | none |
| Created | 2026-06-09 |
| Estimated | 1 pt |

## User Story

As the maintainer of `claude-i`, I want timeout/retry paths to clean Stop-hook artifacts even when the hook touches the sentinel late, so extensive E2E runs do not leave fresh `claude-i-*.done` files accumulating in the system tempdir.

## Context

During extensive real E2E validation on 2026-06-09, `claude-i doctor --json` passed and no `claude-i-*` tmux sessions remained, but the tempdir contained many fresh `claude-i-*.done` files. Payload samples showed title-generation Stop events such as `SKIP`, `Chat: ...`, and `Docs: ...`.

The likely race is:

- the Stop hook writes `<sentinel>.json`;
- `runner.run()` times out or filters a title fire while the hook is between `mv` and `touch`;
- the first `finally` cleanup removes the payload;
- the hook touches `<sentinel>.done` just after cleanup, leaving a fresh orphan.

## Acceptance Criteria

- **AC-1:** `runner.run()` continues to remove the current run's sentinel, payload, and temporary payload files.
- **AC-2:** Timeout/retry and title-filtered paths perform a short post-`kill-session` cleanup sweep to catch late Stop-hook touches.
- **AC-3:** Ordinary no-title success paths do not add the post-cleanup wait.
- **AC-4:** Cleanup remains best-effort and never masks the real run result.
- **AC-5:** Unit regression coverage simulates late payload/sentinel creation after the first cleanup.
- **AC-6:** Local validation passes: targeted runner test, full unit suite, ruff, mypy, build/twine, install smoke, doctor, and relevant E2E checks.

## Tasks / Subtasks

- [x] 11.1 Diagnose fresh sentinel accumulation after real E2E.
- [x] 11.2 Add focused cleanup helper for per-run artifacts.
- [x] 11.3 Wire post-kill sweep for title-filtered and exception paths.
- [x] 11.4 Add regression test for late Stop-hook artifact cleanup.
- [x] 11.5 Re-run validation and close the gate.

## File List

**Modified:**

- `src/claude_i/runner.py`
- `tests/test_runner.py`
- `docs/stories/STORY-001.10-late-stop-hook-cleanup.md`
- `docs/gates/STORY-001.10-gate.md`

## Dev Notes

- This fix does not change the Stop hook command. The existing payload-then-touch order remains correct.
- The cleanup sweep is intentionally scoped to the current run's unique sentinel family and includes `<payload>.tmp`.
- The post-cleanup wait is only enabled for title-filtered Stop events and exception/timeout unwinds.

## Dev Agent Record

### Implementation Summary

- Added per-run artifact cleanup for sentinel, payload, and payload temp files.
- Added short post-Stop cleanup for timeout/title-filtered paths.
- Added `atexit` cleanup so title-generation Stop events that land after `runner.run()` returns but before process exit are removed.
- Isolated mocked runner tests so they no longer create real system tempdir sentinels when `Path.unlink` is monkeypatched to no-op.

### Validation

- Targeted regression: `1 passed`.
- `tests/test_runner.py`: `38 passed`, `remaining_after_runner_tests=0`.
- Full default suite: `120 passed, 5 skipped`.
- Real E2E spot checks:
  - `test_e2e_single_shot_smoke`: `1 passed`, `remaining_after_single_shot=0`.
  - `test_e2e_long_prompts`: `1 passed`, `remaining_after_long_prompts=0`.
- GitHub smoke workflow `27233563936`: shellcheck, dry-run, macOS, Ubuntu, and Fedora all passed.
