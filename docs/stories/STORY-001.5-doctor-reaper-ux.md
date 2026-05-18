# STORY-001.5: Doctor, Reaper, UX — Subcommands, JSON Output, Readiness Polling, G10-G17 Tests

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Depends on | STORY-001.1, STORY-001.2 |
| Estimated | 5 pts (~2 days) |

## User Story

As an operator running `claude-i` in scripts and pipelines, I want self-diagnostic (`doctor`), reversal (`uninstall`), and orphan cleanup (`reap`) subcommands, machine-readable JSON output, readiness polling instead of fixed sleep, and automatic stale sentinel cleanup, so that `claude-i` is operationally transparent and embeddable in automation without guesswork.

## Acceptance Criteria

- AC-1: `claude-i doctor` performs all of the following checks and prints a structured pass/fail report to stdout: (a) `tmux` on PATH, (b) `claude` on PATH, (c) Stop hook installed and correct (verified by reading `settings.json`, not just presence), (d) `settings.json` is valid JSON, (e) no stale sentinel files in `/tmp` matching `claude-i-*.done`. On any failure, `claude-i doctor` exits non-zero (code `1`). On all pass, exits `0`.
- AC-2: `claude-i doctor --json` outputs the same report as a JSON object `{"checks": [{"name": "...", "status": "pass"|"fail", "detail": "..."}], "overall": "pass"|"fail"}` and exits with the same codes as AC-1.
- AC-3: `claude-i uninstall` removes the `claude-i` Stop hook entry from `settings.json` (using the same `flock` acquired in STORY-001.2), preserves all other hook entries, and prints what was removed. If no hook is found, prints a no-op message and exits `0`. If `settings.json` is invalid JSON, exits `1` with an error.
- AC-4: `claude-i reap` finds all tmux sessions matching the pattern `claude-i-*` (via `tmux list-sessions -F "#S"`), kills them, and reports the count killed. If no matching sessions exist, exits `0` with "no orphaned sessions found". Exits `1` if `tmux` is not on PATH.
- AC-5: `--output-format json` on the main `claude-i "<prompt>"` invocation outputs `{"text": "...", "cost_usd": <float|null>, "tokens_in": <int|null>, "tokens_out": <int|null>, "duration_ms": <int>}` to stdout. Fields are `null` if the upstream `claude` session does not expose them. `duration_ms` is always populated (wall time from prompt send to Stop hook fire).
- AC-6: The fixed `time.sleep(ready_wait)` in `runner.run()` (seed line 111) is replaced with a readiness poller that probes the tmux pane content at 250ms intervals until a claude-prompt indicator is detected (e.g., pane contains `>` or a pattern indicating the claude TUI is ready), with a maximum wait of `--ready-wait` seconds (default 10s). If the pane never becomes ready within the timeout, `claude-i` exits `1` with a "TUI did not become ready" message.
- AC-7: On every run of the main `claude-i "<prompt>"` command, sentinel files under `/tmp` matching `claude-i-*.done` older than 24 hours are deleted (best-effort, errors silently ignored).
- AC-8: Tests cover G14 (`SubagentStop` hook event handling) and G15 (stale sentinel accumulation and cleanup).

## Tasks / Subtasks

- [ ] 6.1 — Implement `claude-i doctor` subcommand in `cli.py`
  - [ ] Add `subparsers.add_parser("doctor")` with `--json` flag
  - [ ] Implement `cmd_doctor(args)` function that runs 5 checks (AC-1 list)
  - [ ] Check (a): `deps._which("tmux")` — pass/fail
  - [ ] Check (b): `deps._which("claude")` — pass/fail
  - [ ] Check (c): `hook.hook_installed()` — pass/fail; detail: which part failed (missing vs wrong format)
  - [ ] Check (d): `settings.load_settings()` — pass/fail; catch `json.JSONDecodeError`
  - [ ] Check (e): count files matching `Path("/tmp").glob("claude-i-*.done")` older than 24h — pass if 0, fail with count otherwise
  - [ ] Plain text output: one line per check with `[PASS]` / `[FAIL]` prefix
  - [ ] `--json` output: serialize the checks list and overall status
  - [ ] Exit code: `0` if all pass, `1` if any fail
  - [ ] Unit test: `test_cli.py::test_doctor_all_pass`, `test_cli.py::test_doctor_fails_on_missing_tmux`, `test_cli.py::test_doctor_json_output`

- [ ] 6.2 — Implement `claude-i uninstall` subcommand in `cli.py` and `hook.py`
  - [ ] Add `subparsers.add_parser("uninstall")`
  - [ ] Implement `hook.remove_hook() -> int` (returns count of removed entries)
  - [ ] `remove_hook()`: load `settings.json` with flock → filter out all entries where `command == HOOK_CMD` → write back → return removed count
  - [ ] `cmd_uninstall(args)`: call `remove_hook()`, print result, exit 0
  - [ ] Unit test: `test_hook.py::test_remove_hook_removes_only_claude_i_entry`, `test_hook.py::test_remove_hook_noop_when_not_installed`

- [ ] 6.3 — Implement `claude-i reap` subcommand in `cli.py` and `reaper.py`
  - [ ] Add `subparsers.add_parser("reap")`
  - [ ] Implement `reaper.reap_orphans() -> int` (full implementation, was stub in STORY-001.0)
  - [ ] `reap_orphans()`: call `tmux list-sessions -F "#S"` → filter lines starting with `claude-i-` → kill each with `tmux kill-session -t <name>` → return count
  - [ ] `cmd_reap(args)`: call `reap_orphans()`, print report, exit 0 (even if count=0)
  - [ ] Unit test: `test_reaper.py::test_reap_orphans_kills_matching_sessions`, `test_reaper.py::test_reap_orphans_returns_zero_when_none`

- [ ] 6.4 — Implement `--output-format json` for main prompt command
  - [ ] Add `ap.add_argument("--output-format", choices=["text", "json"], default="text")` to main parser
  - [ ] Add `start_time = time.monotonic()` before the Stop hook wait loop
  - [ ] Add `duration_ms = int((time.monotonic() - start_time) * 1000)` after hook fires
  - [ ] Attempt to extract `cost_usd`, `tokens_in`, `tokens_out` from the hook payload (field names TBD — check the hook event payload shape at runtime); default to `null` if absent
  - [ ] In `cli.main()`: if `--output-format json`, `print(json.dumps({...}))` instead of `print(result)`
  - [ ] Unit test: `test_cli.py::test_output_format_json_structure`, `test_cli.py::test_output_format_json_null_fields_when_absent`

- [ ] 6.5 — Replace fixed sleep with readiness poller in `runner.run()`
  - [ ] Remove `time.sleep(ready_wait)` (seed line 111)
  - [ ] Implement `_wait_for_tui_ready(session: str, timeout: float, interval: float = 0.25) -> None`:
    - Poll `tmux capture-pane -pt <session>` every `interval` seconds
    - Detect readiness: pane content contains a known indicator (investigate live: try `">"` as the claude interactive prompt marker; if unreliable, fall back to detecting non-empty pane content after initial lines settle)
    - If ready: return
    - If `timeout` exceeded: raise `TimeoutError("TUI did not become ready")`
  - [ ] Update `runner.run()` to call `_wait_for_tui_ready(session, ready_wait)` instead of `time.sleep`
  - [ ] Add `--ready-wait` default change: 10.0 (up from 4.0 in seed — poller is more reliable but we need headroom)
  - [ ] Document the probe heuristic in a comment: "Probe detects claude TUI readiness by watching for prompt pattern; adjust regex in settings.py if upstream TUI changes"
  - [ ] Unit test: `test_runner.py::test_readiness_poller_returns_on_prompt_detected`, `test_runner.py::test_readiness_poller_raises_on_timeout`

- [ ] 6.6 — Implement stale sentinel cleanup in `runner.run()`
  - [ ] Add `_cleanup_stale_sentinels()` helper in `runner.py`:
    - Glob `/tmp/claude-i-*.done`
    - For each file older than 24h (`time.time() - os.path.getmtime(p) > 86400`): `p.unlink(missing_ok=True)` — catch all exceptions silently
  - [ ] Call `_cleanup_stale_sentinels()` at the start of `runner.run()` before any new session creation
  - [ ] Unit test: `test_runner.py::test_stale_sentinels_cleaned_on_run` (G15 coverage)

- [ ] 6.7 — Handle `SubagentStop` hook event (G14)
  - [ ] Investigate: does Claude Code fire a `SubagentStop` event distinct from `Stop`? Check hook payload `event` or `type` field
  - [ ] If `SubagentStop` events are distinct and could cause the sentinel to be written prematurely (before the final assistant turn): add event-type check in `HOOK_CMD` or post-process the payload to verify the event type
  - [ ] If indistinguishable from `Stop`: document the finding and add a test that simulates a `SubagentStop` payload shape to verify `runner.run()` handles it gracefully (does not crash, may return partial result)
  - [ ] Unit test: `test_runner.py::test_subagent_stop_payload_handled_gracefully` (G14 coverage)

- [ ] 6.8 — Update `--help` to reflect all subcommands and new flags
  - [ ] Ensure `claude-i --help` lists all subcommands: `doctor`, `uninstall`, `reap`
  - [ ] Document `--output-format`, `--allow-empty`, `--permission-mode`, `--ready-wait` with clear descriptions
  - [ ] Verify `claude-i doctor --help` and `claude-i reap --help` produce sensible output

## Dev Notes

- **G10 (streaming):** True streaming output (partial assistant text as it generates) is not addressable with the current tmux/Stop-hook architecture — the hook fires only after Claude finishes. The `--verbose` flag (tail_pane) provides a visual proxy. G10 is noted as closed-with-caveat: the UX improvement from readiness polling (AC-6) and the `--verbose` live-tail covers the "frozen" feeling. If full streaming is desired in a future Epic, it requires a different architecture (e.g., `claude --output-format stream-json`).
- **G11 (metadata):** The hook payload written to `$CLAUDE_I_SENTINEL.json` contains whatever Claude Code sends to the Stop hook. Check the actual payload shape at runtime (run `claude-i --verbose` on a known prompt and inspect the `.json` file before it is deleted). Common fields: `transcript_path`, `session_id`. Cost/token fields may require `--output-format json` flag on the `claude` invocation itself — add it as part of `extra_args` when `--output-format json` is requested.
- **G12 (final):** `doctor` check (c) is the runtime hook verification completing the G12 fix started in STORY-001.1. The 001.1 story upgraded `hook_installed()` at install time; `doctor` verifies it at runtime (settings.json may have been modified externally).
- **G14 (SubagentStop):** This gap covers the case where Claude Code invokes a subagent (tool use) and fires a `SubagentStop` event. If `CLAUDE_I_SENTINEL` is set during a subagent invocation, the hook might fire early, writing an incomplete payload. The sentinel-based architecture is vulnerable to this. Mitigation: check the event type in the hook payload (`hook_input.get("event")` or similar) and only proceed if it is `Stop` (not `SubagentStop`). If that field is absent (older Claude Code versions), fall back to best-effort behavior.
- **G17 (readiness polling) probe heuristic:** The claude interactive TUI renders a prompt `>` after initialization. However, this is an implementation detail of `claude` and subject to change (DEP-3). The probe should be conservative: also accept "pane has more than 2 non-empty lines" as a readiness signal. Store the regex in `settings.py` as `TUI_READY_PATTERN: str = r"[>❯]"` so it can be overridden without code change.
- **`--output-format json` on `claude` itself:** If the `claude` binary supports `--output-format json`, adding it to `extra_args` may produce structured metadata directly. Investigate; if supported, prefer that over parsing the Stop hook payload for cost/token fields.
- **Subcommand dispatch in `cli.py`:** Use `subparsers` with `set_defaults(func=cmd_*)` pattern:
  ```python
  sub = ap.add_subparsers()
  p_doctor = sub.add_parser("doctor"); p_doctor.set_defaults(func=cmd_doctor)
  p_uninstall = sub.add_parser("uninstall"); p_uninstall.set_defaults(func=cmd_uninstall)
  p_reap = sub.add_parser("reap"); p_reap.set_defaults(func=cmd_reap)
  args = ap.parse_args()
  if hasattr(args, "func"): sys.exit(args.func(args))
  ```
- **Expected files to touch:**
  - `src/claude_i/cli.py` — subcommand dispatch, `--output-format`, `--allow-empty` wiring
  - `src/claude_i/hook.py` — `remove_hook()`
  - `src/claude_i/runner.py` — readiness poller, stale sentinel cleanup, duration timing, G14 payload check
  - `src/claude_i/reaper.py` — `reap_orphans()` full implementation
  - `src/claude_i/settings.py` — `TUI_READY_PATTERN` constant
  - `tests/test_cli.py` — doctor, uninstall, reap, JSON output tests
  - `tests/test_hook.py` — `remove_hook()` tests
  - `tests/test_reaper.py` — `reap_orphans()` tests
  - `tests/test_runner.py` — poller, stale cleanup, G14, G15 tests

## Testing

- **pytest unit tests** (all mocked):
  - `test_cli.py::test_doctor_all_pass` — all checks mocked to return pass; assert exit 0 and `[PASS]` in output.
  - `test_cli.py::test_doctor_fails_on_missing_tmux` — mock `which("tmux")` = None; assert exit 1 and `[FAIL]` for tmux check.
  - `test_cli.py::test_doctor_json_output` — `--json` flag; assert output is valid JSON with `checks` and `overall` keys.
  - `test_hook.py::test_remove_hook_removes_only_claude_i_entry` — settings.json with claude-i hook + user hook; after `remove_hook()`, user hook preserved and claude-i hook absent.
  - `test_hook.py::test_remove_hook_noop_when_not_installed` — no hook in settings.json; `remove_hook()` returns 0 and does not raise.
  - `test_reaper.py::test_reap_orphans_kills_matching_sessions` — mock `tmux list-sessions` output; verify `kill-session` called for each match.
  - `test_reaper.py::test_reap_orphans_returns_zero_when_none` — empty session list; returns 0.
  - `test_cli.py::test_output_format_json_structure` — mock `runner.run()` to return `("hello", {...metadata})` tuple; assert JSON output has all keys.
  - `test_runner.py::test_readiness_poller_returns_on_prompt_detected` — mock pane content that eventually contains `>`; assert `_wait_for_tui_ready` returns.
  - `test_runner.py::test_readiness_poller_raises_on_timeout` — mock pane always empty; assert `TimeoutError` after timeout.
  - `test_runner.py::test_stale_sentinels_cleaned_on_run` — create a sentinel file with mtime 25h ago; call `_cleanup_stale_sentinels()`; assert file deleted. (G15)
  - `test_runner.py::test_subagent_stop_payload_handled_gracefully` — pass a hook payload with event type `SubagentStop`; assert `runner` does not crash and returns a predictable value. (G14)
- **Manual smoke (`doctor`):** After full install (`pipx install claude-i`), run `claude-i doctor`. All 5 checks should pass (green) on a correctly configured machine.
- **Manual smoke (`uninstall`):** Run `claude-i uninstall`; verify the hook is removed from `settings.json`. Run `claude-i doctor`; check (c) should fail.
- **Manual smoke (`reap`):** Start a `claude-i` session and SIGKILL it; run `claude-i reap`; verify the orphaned tmux session is killed.

## File List

(empty — populated by @dev during execution)

## Dev Agent Record

(empty — populated by @dev)
