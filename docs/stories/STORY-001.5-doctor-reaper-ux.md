# STORY-001.5: Doctor, Reaper, UX — Subcommands, JSON Output, Readiness Polling, G10-G17 Tests

| Field | Value |
|---|---|
| Status | Ready |
| Epic | EPIC-001 |
| Owner | @dev (Dex) |
| Executor | @dev |
| Quality Gate | @qa |
| Accountable | rafaelscosta |
| deploy_type | none |
| Created | 2026-05-17 |
| Depends on | STORY-001.1, STORY-001.2 |
| Estimated | 5 pts (~2 days) |

## User Story

As an operator running `claude-i` in scripts and pipelines, I want self-diagnostic (`doctor`), reversal (`uninstall`), and orphan cleanup (`reap`) subcommands, machine-readable JSON output, readiness polling instead of fixed sleep, and automatic stale sentinel cleanup, so that `claude-i` is operationally transparent and embeddable in automation without guesswork.

## Acceptance Criteria

- AC-1: `claude-i doctor` performs all of the following checks and prints a structured pass/fail report to stdout: (a) `tmux` on PATH, (b) `claude` on PATH, (c) Stop hook installed and correct (verified by reading `settings.json`, not just presence), (d) `settings.json` is valid JSON, (e) no stale sentinel files in `/tmp` matching `claude-i-*.done` **older than 24 hours** (sentinels younger than 24h are excluded — they are likely owned by an in-flight `claude-i` invocation; the 24h window matches AC-7 cleanup semantics — resolves @po C-4). On any failure, `claude-i doctor` exits non-zero (code `1`). On all pass, exits `0`.
- AC-2: `claude-i doctor --json` outputs the same report as a JSON object `{"checks": [{"name": "...", "status": "pass"|"fail", "detail": "..."}], "overall": "pass"|"fail"}` and exits with the same codes as AC-1.
- AC-3: `claude-i uninstall` removes the `claude-i` Stop hook entry from `settings.json` (using the same `flock` acquired in STORY-001.2), preserves all other hook entries, and prints what was removed. If no hook is found, prints a no-op message and exits `0`. If `settings.json` is invalid JSON, exits `1` with an error.
- AC-4: `claude-i reap` finds **orphaned** `claude-i-<pid>` tmux sessions (where the owning PID is no longer alive, via existing `reaper._pid_alive()` from STORY-001.2) and kills them. Sessions with live owners are LEFT INTACT (a concurrent `claude-i` run must not be killed). Reports count killed. Exits `0` with "no orphaned sessions found" when none. Exits `1` if `tmux` is not on PATH. — Resolves @po validation C-2 (orphan-only semantic, matches existing `reap_orphans()` implementation in `src/claude_i/reaper.py:95-143`).
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

- [ ] 6.3 — Wire existing `reap_orphans()` to new `claude-i reap` subcommand — ADAPT, not CREATE (resolves @po C-1 IDS violation)
  - [ ] Verify existing impl: `grep -n "def reap_orphans" src/claude_i/reaper.py` should show ONE definition at line ~95. Tests at `tests/test_reaper.py:109-159` cover orphan detection via `_pid_alive()`.
  - [ ] Add `subparsers.add_parser("reap")` in `cli.py`
  - [ ] Implement `cmd_reap(args)` — call existing `reaper.reap_orphans()`, print report (`Reaped N orphan session(s)` or `no orphaned sessions found`), exit 0 (even if count=0)
  - [ ] If `tmux` not on PATH: catch FileNotFoundError, print message, exit 1 (per AC-4)
  - [ ] Unit test: `test_cli.py::test_reap_subcommand_calls_reap_orphans` (mock reap_orphans, verify called), `test_cli.py::test_reap_subcommand_zero_count_exits_0`
  - [ ] DO NOT re-implement `reap_orphans()` — that exists in `reaper.py:95-143` already from STORY-001.2. Editing it would be a regression to G6's atexit semantics.

- [ ] 6.4a — Migrate `runner.run()` signature `-> str` → `-> tuple[str, RunMetadata]` (PREREQUISITE for 6.4) — resolves @po C-3
  - [ ] Define `RunMetadata` as a `TypedDict` (or dataclass) in `runner.py` with fields: `duration_ms: int`, `cost_usd: float | None`, `tokens_in: int | None`, `tokens_out: int | None`
  - [ ] Update `runner.run()` to return `(text, metadata)` instead of bare `text`
  - [ ] Update ALL callers — search and update: `grep -rn "runner.run(" src/ tests/` (expect ~5 files based on 16 callsite estimate from @po, mostly in tests)
  - [ ] `cli.py:main()` is the primary caller — destructure `result, metadata = runner.run(...)`
  - [ ] Test files use `result = runner.run(...)` directly — change to `result, _ = runner.run(...)` where metadata isn't asserted
  - [ ] Keep `runner.run()` docstring updated — 4-branch contract from 001.2 + new metadata return type
  - [ ] All 68 existing tests must still pass (regression check is mandatory)

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

## Validation Findings (2026-05-18 — @po Pax)

### Blocking Conditions (NO-GO until resolved)

**C-1 — IDS violation on Task 6.3 (`reap_orphans` already exists).** `src/claude_i/reaper.py:95-143` already implements `reap_orphans()` end-to-end (landed in STORY-001.2 per 001.2 closure note: "landed here in 001.2 so the atexit infrastructure has a sibling reaper for ad-hoc cleanup"). 4 dedicated tests exist at `tests/test_reaper.py:109-159` (`test_reap_orphans_returns_zero_when_no_tmux`, `test_reap_orphans_skips_non_claude_i_sessions`, `test_reap_orphans_kills_dead_pid_sessions`, `test_reap_orphans_skips_live_pid_sessions`). Task 6.3 reads "full implementation, was stub in STORY-001.0" — that text is stale. **Action:** rewrite Task 6.3 as "wire existing `reaper.reap_orphans()` to a new `cmd_reap(args)` CLI subcommand" (ADAPT, not CREATE per IDS Principles). Do NOT redefine `reap_orphans()`.

**C-2 — AC-4 semantic conflict with existing implementation.** AC-4 says `claude-i reap` "finds all tmux sessions matching the pattern `claude-i-*` ... kills them". The existing `reap_orphans()` at `reaper.py:95-143` kills ONLY orphans (PID gone per `_pid_alive`) — live `claude-i-*` sessions are skipped. Mission brief uses the phrase "force kill **orphan** claude-i-* tmux sessions". Three readings now coexist: (a) orphan-only (current code + mission brief), (b) all `claude-i-*` (AC-4 literal), (c) operator-confirmable. **Action:** decision required from @pm/operator before executor starts. Recommend (a) orphan-only — matches the current safer implementation and the mission wording; update AC-4 to read "kills all *orphaned* tmux sessions matching `claude-i-*` (sessions whose owning PID is no longer alive)". Live sessions of concurrent in-flight `claude-i` invocations must NOT be reaped.

**C-3 — `runner.run()` signature breaking change unmentioned.** AC-5 requires `--output-format json` to emit `cost_usd`, `tokens_in`, `tokens_out`, `duration_ms`. Currently `runner.run()` returns `str`. To expose metadata, `runner.run()` must return `(str, dict)` tuple — a breaking change touching `cli.py:165` + 15 test callsites (`tests/test_cli.py:25,146,166`, `tests/test_runner.py:100,200,247,318,333,348,372,394,442,464`). Dev Notes do not call this out. **Action:** Tasks 6.4 + 6.5 + 6.6 (anywhere `runner.run()` is touched) must add an explicit task: "Migrate `runner.run()` signature from `-> str` to `-> tuple[str, RunMetadata]` where `RunMetadata` is a typed dict carrying `duration_ms` (always populated) + nullable `cost_usd`/`tokens_in`/`tokens_out`. Update all callsites in `cli.py` and tests in one atomic commit before AC-5 work begins. No backward-compat shim — claude-i is single-consumer."

### Conditions (GO Condicional — executor must address)

**C-4 — AC-1(e) vs Task 6.1(e) internal inconsistency.** AC-1(e) says doctor must check "no stale sentinel files in `/tmp` matching `claude-i-*.done`" (no age qualifier). Task 6.1(e) says "older than 24h — pass if 0, fail with count otherwise". **Action:** align — use the 24h qualifier in BOTH (matches AC-7 cleanup window and avoids false-fail when a `claude-i` run is in flight). Recommend doctor reports a WARN (not FAIL) for sentinels younger than 24h to disambiguate "stale" from "in-flight". @dev to clarify in AC-1(e) before implementation.

**C-5 — G14 (`SubagentStop`) lacks time-box guard.** Task 6.7 reads as full implementation but the @sm flag (echoed in mission brief D10 risk 2) calls it "investigative". STORY-001.1 G2 used the 90-min-cap + NOTES.md-defer pattern with forward-compatible structural foundation (`_is_claude_i_hook_entry()`). **Action:** restructure Task 6.7 as "Investigate `SubagentStop` event distinctness for max 90 min. IF distinct event field is discoverable in hook payload → implement check. ELSE → document finding in `NOTES.md` § 'SubagentStop Discovery' with sources consulted, add a graceful-handling test (Task 6.7 unit test stub), defer to a future story." Same pattern as G2 deferral.

### Auto-Fixed

- Owner=TBD → @dev (Dex)
- Executor missing → @dev
- Quality Gate missing → @qa
- Accountable missing (non-Human executor → mandatory) → rafaelscosta (operator/sole CODEOWNER on `rafaelscosta/claude-i`)
- `deploy_type` missing → `none` (PyPI publish + Homebrew tap publish are Epic-level DoD items, not story tasks — see Epic-Close Decision below)

### Epic-Close Decision (Mission brief Q5)

**Recommendation: Epic close is a SEPARATE ceremony, NOT part of STORY-001.5.** The Epic-Level DoD (`docs/epics/EPIC-001-packaging-and-hardening.md` lines 167-179) lists `v0.2.0` tag, PyPI publish, Formula URL flip (Task 5.9), manual brew install verification, and EPIC-001 close as **Epic-level** items, not story ACs. They depend on 001.5 landing on `main` first (so the tag captures a clean final SHA). Treating them as part of 001.5 would either (a) require the tag to predate the gate/closure (operationally awkward) or (b) couple 001.5's QA gate to PyPI-side state outside @dev/@qa authority.

**Suggested executor split for the epic-close ceremony (post-001.5-close, no story file):**
1. @devops `*push` final 001.5 commits + tag `v0.2.0` + `git push --tags`
2. @devops `gh workflow run publish.yml` + approve `publish` environment gate
3. @devops Task 5.9 — Formula URL flip to canonical `files.pythonhosted.org` + SHA256 regeneration + tap repo push
4. Operator (Rafael) — clean macOS `brew tap` + `brew install` + `claude-i --version` verification
5. @po `*close-epic EPIC-001` — verify Epic DoD checklist 100% green, mark Epic Done

**Rationale for split:** Story scope stays G10/G11/G12/G14/G15/G16/G17 + the 7 ACs as currently drafted. Epic close is a 5-step ceremony spread across 2-3 agents + 1 operator action. Bundling them into 001.5 would conflate "code change" with "release action" and force @qa to gate on operator-only steps.

### Recommended Executor + QG (Mission brief request)

- **Executor:** `@dev` (Dex) for all 8 tasks (subcommand wiring, JSON output, readiness poller, stale cleanup, G14 investigation, G15 tests, --help refresh). All work is Python in `src/claude_i/` + tests in `tests/`. No DB/infra/UI/design work in scope. `@db-sage`, `@architect`, `@devops` are NOT needed for 001.5 implementation.
- **Quality Gate:** `@qa` (Quinn) — same pattern as 001.0-001.4 (5/5 PASS, scores 92-96). Independent re-run in fresh venv + ruff + mypy strict + pytest.
- **Epic close (separate ceremony):** `@devops` (Gage) for steps 1-3, operator for step 4, `@po` for step 5.

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-17 | @sm (River) | Initial draft |
| 2026-05-18 | @po (Pax) | Validated 6/10 [NO-GO pending C-1/C-2/C-3 resolution]. Context: Epic 001, 5 prior stories Done (96/94/95/94/92). D10: 3 divergences found (Task 6.3 IDS / AC-4 semantic / runner.run signature), 5 auto-fixes applied (owner+executor+QG+accountable+deploy_type). Conditions: C-4 AC-1(e) age qualifier, C-5 G14 time-box pattern. Epic-close decision: separate ceremony recommended (5-step split post-001.5-close). |
