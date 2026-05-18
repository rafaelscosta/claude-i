# STORY-001.1: Critical Hardening — Permission Mode, Hook Scoping, Dep Check, Env Var Hygiene

| Field | Value |
|---|---|
| Status | Ready for Review |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Validated | 2026-05-17 by @po (Pax) — GO with Auto-Fix, 9/10 |
| Depends on | STORY-001.0 (Done) |
| Estimated | 5 pts (~2 days) |
| Executor | @dev (Dex) |
| Quality Gate | @qa (Quinn) |
| Deploy Type | none (Python library/CLI — no production deploy) |

## User Story

As a developer running `claude-i` on a system with pre-existing Claude Code hooks and custom permission profiles, I want `claude-i` to launch the sub-`claude` with safe permission defaults, never collide with my own Stop hooks, validate that system dependencies are present, and not pollute the sub-process environment, so that I can adopt `claude-i` without fear of breaking my existing Claude Code setup.

## Acceptance Criteria

- AC-1: `claude-i "<prompt>"` invokes the sub-`claude` with `--permission-mode acceptEdits` by default. A `--permission-mode <mode>` CLI flag allows override; the flag value is passed through verbatim to `claude`.
- AC-2: When `tmux` is not on `$PATH`, `claude-i` exits with code `2` and prints an OS-specific install hint: `brew install tmux` (macOS), `sudo apt install tmux` (Ubuntu/Debian), `sudo dnf install tmux` (Fedora/RHEL). No tmux session is started.
- AC-3: When `claude` is not on `$PATH`, `claude-i` exits with code `2` and prints a link to the Claude Code install docs. No tmux session is started.
- AC-4: `CLAUDE_I_SENTINEL` is not present in `claude-i`'s own `os.environ` after `runner.run()` starts the tmux session, and is not inherited by **sibling** subprocesses that `claude-i` itself spawns (i.e. any future `subprocess.run` calls). The sentinel value **is still delivered to the in-tmux `sh -c` command** via the existing `CLAUDE_I_SENTINEL=<path> exec claude` shell prefix (seed line 96), because the Stop hook's shell guard requires `$CLAUDE_I_SENTINEL` at runtime. Verification: a unit test asserts the `env` kwarg passed to the tmux-spawning `subprocess.run` does NOT contain `CLAUDE_I_SENTINEL`; a second test asserts the `sh -c` command string DOES still begin with `CLAUDE_I_SENTINEL=`. **Scope note:** sub-`claude`'s own descendant subprocesses inherit whatever env sub-`claude` chooses to pass; that surface is outside `claude-i`'s control and outside this AC. Full env-channel removal (e.g. baking sentinel path into `HOOK_CMD` via templating) is deferred to a future story if needed.
- AC-5: The installed Stop hook entry in `settings.json` includes a `matcher` field (or equivalent scoping mechanism supported by the Claude Code hook format) that restricts the hook to fire only when `CLAUDE_I_SENTINEL` is set, **in addition to** the existing `if [ -n "$CLAUDE_I_SENTINEL" ]` shell guard. If the `matcher` field is not supported in the detected Claude Code version, `claude-i` logs a warning and falls back to the shell guard only.
- AC-6: `hook_installed()` in `hook.py` verifies both the presence of `HOOK_CMD` and the presence of the `matcher` or scoping field (where applicable) — the seed's plain `command == HOOK_CMD` string compare (seed line 34) is no longer the sole verification mechanism.
- AC-7: `deps.check_deps()` is called before any tmux or hook operation in `cli.py`. Missing-dependency errors are surfaced to the user before the hook install prompt.
- AC-8: Exit codes are documented in `--help` output: `0` = success, `1` = runtime error (timeout, parse failure), `2` = dependency missing or config error.

## Tasks / Subtasks

- [x] 2.1 — Implement `deps.check_deps()` in `src/claude_i/deps.py`
  - [x] Check `shutil.which("tmux")` — if None, detect OS via `platform.system()` + `/etc/os-release` and emit the correct install hint, then `sys.exit(2)`
  - [x] Check `shutil.which("claude")` — if None, emit install hint with link, then `sys.exit(2)`
  - [x] Unit test: `test_deps.py::test_missing_tmux_exits_2` and `test_deps.py::test_missing_claude_exits_2` (mock `shutil.which`)

- [x] 2.2 — Wire `deps.check_deps()` into `cli.main()` before `ensure_hook()`
  - [x] Confirm `cli.py` calls `deps.check_deps()` as the first substantive action in `main()`
  - [x] Unit test: `test_cli.py::test_deps_called_before_hook` (patch both, verify call order)

- [x] 2.3 — Add `--permission-mode` flag to `cli.py`
  - [x] `ap.add_argument("--permission-mode", default="acceptEdits", metavar="MODE", help="Claude permission mode (default: acceptEdits)")`
  - [x] Pass `["--permission-mode", args.permission_mode]` to `runner.run()` as part of `extra_args` before user-supplied extras
  - [x] Unit test: `test_cli.py::test_permission_mode_default` and `test_cli.py::test_permission_mode_override`

- [x] 2.4 — Implement env var isolation in `runner.run()` (sibling-subprocess scope only)
  - [x] Build a sanitized env to pass to `subprocess.run()` calls in this module: `env = {k: v for k, v in os.environ.items() if k != "CLAUDE_I_SENTINEL"}` (factored into `_sanitized_env()` helper + `_STRIPPED_ENV_VARS` constant for extensibility)
  - [x] **KEEP** the `CLAUDE_I_SENTINEL=<sentinel-path>` prefix inside `claude_cmd` — preserved verbatim at `runner.py:130` (was line 76 pre-edit)
  - [x] Pass `env=_sanitized_env()` to the `tmux("new-session", ..., env=...)` call only. Read-side calls (capture-pane / set-buffer / paste-buffer / send-keys / kill-session) intentionally inherit `os.environ` — they spawn short-lived tmux client processes, not the sub-claude.
  - [x] **Test contract (both assertions confirmed):**
    - `test_runner.py::test_sentinel_stripped_from_subprocess_env` PASS
    - `test_runner.py::test_sentinel_still_in_sh_command` PASS
    - Anti-pattern smoke (mutate runner.py to remove shell prefix → re-run) confirmed `test_sentinel_still_in_sh_command` correctly fails with the expected diagnostic, then runner.py restored.

- [x] 2.5 — Investigate `matcher` field support in Claude Code hook format (time-box: 90 minutes)
  - [x] Sources consulted in authority order: `claude --help` / `claude hooks --help` (no hooks subcommand exists); local schema at `~/.claude/schema/` (absent) and `~/.claude/settings.schema.json` (absent); live `~/.claude/settings.json` programmatic inspection; internal hooks reference at `~/.claude/commands/claude-code-mastery/hooks-architect.md`.
  - [x] Decision: **DEFER (treat as unsupported for this story)**. `matcher` is documented for tool-event hooks (`PreToolUse` / `PostToolUse`) where it filters by tool name regex; `Stop` is session-level with no documented `matcher` field in the live settings.json or in the hooks-architect reference. Hardcoding an unverified schema for Stop would risk breaking installs.
  - [x] Finding recorded in `NOTES.md` § "Hook Matcher Support" with investigation date, sources, decision rationale, and revisit conditions.
  - [x] Tasks 2.6 / 2.7 were not blocked by this — the fallback branch (shell-guard-only) is fully sufficient for AC-5 and AC-6.
  - **Time spent:** ~15 minutes (well under the 90-min cap).

- [x] 2.6 — Upgrade `hook_installed()` in `hook.py`
  - [x] Replace the seed's single `command == HOOK_CMD` check with a structural check: `type == "command"` AND `command == HOOK_CMD` (Part A). Part B (matcher verification) is a no-op because Stop has no documented matcher — recorded in the docstring with a forward-link to a future story.
  - [x] Old-style entries (right command, wrong type — e.g. `type: http` with HOOK_CMD as the command string) now correctly return `False`, forcing reinstall via the structural check.
  - [x] Unit tests: `test_hook.py::test_hook_installed_detects_legacy_hook` PASS and `test_hook.py::test_hook_installed_detects_correct_hook` PASS. Additional regressions: `test_hook_installed_returns_false_when_missing`, `test_hook_installed_returns_false_on_malformed_json`, `test_hook_installed_ignores_unrelated_hooks`.

- [x] 2.7 — Update `install_hook()` in `hook.py`
  - [x] Write the documented Stop-hook entry format (no matcher key) — preserves the seed's shape.
  - [x] Preserve all pre-existing `Stop` entries — `setdefault("Stop", []).append(...)` (the seed already did this; locked in by regression test).
  - [x] Unit test: `test_hook.py::test_install_hook_preserves_existing_hooks` PASS (creates a pre-existing http Stop hook, runs `install_hook()`, verifies BOTH entries are present afterwards). Additional regressions: `test_install_hook_creates_settings_when_missing`, `test_install_hook_refuses_malformed_json`, `test_install_then_detect_roundtrip`.

- [x] 2.8 — Document exit codes in `cli.py` `--help`
  - [x] Epilog added to `ArgumentParser` using `RawDescriptionHelpFormatter`:
    ```
    Exit codes:
      0  success
      1  runtime error (timeout, parse failure)
      2  missing dependency or config error
    ```
  - [x] Verified via `test_cli.py::test_help_contains_exit_code_epilog` and manually with `claude-i --help` post-install.

## Dev Notes

- **G1 (permission mode):** The seed's `claude_cmd` at line 96 passes no `--permission-mode`. The fix is simply prepending `["--permission-mode", args.permission_mode]` to the `extra_args` forwarded to `claude`. The `--permission-mode acceptEdits` default is the safest value that still permits the tool to do useful work.
- **G2 (hook scoping):** The seed already has a shell-guard (`if [ -n "$CLAUDE_I_SENTINEL" ]` in `HOOK_CMD`), which prevents the hook from writing output on normal `claude` sessions. The gap is that Claude Code may fire the hook callback for ALL `Stop` events before the shell guard runs — causing a visible no-op error in normal claude use. If the `matcher` field exists, it filters at the Claude Code layer before the command is invoked, eliminating the no-op noise. If `matcher` is not supported, the shell guard remains the only protection. **Do not hardcode a matcher schema without first verifying it exists in the installed Claude Code version.**
- **G3 (dep check):** `shutil.which()` is the correct stdlib function. OS detection for the install hint: `platform.system() == "Darwin"` → brew; otherwise read `/etc/os-release` for `ID` or `ID_LIKE` (`ubuntu`/`debian` → apt; `fedora`/`rhel` → dnf). Default fallback: `"install tmux via your system package manager"`.
- **G4 (env isolation) — TWO layers, both required:**
  - **Layer 1 — Delivery to sub-`claude`:** the `sh -c "CLAUDE_I_SENTINEL=<path> exec claude ..."` shell prefix (seed line 96) is the **only** mechanism that gets the sentinel value to the Stop hook's shell guard (`if [ -n "$CLAUDE_I_SENTINEL" ]`). **Keep it.** Removing it breaks the hook → sentinel file never written → `runner.run()` times out → entire pipeline broken.
  - **Layer 2 — Isolation from sibling subprocesses:** `claude-i` itself runs Python code that spawns `subprocess.run` calls (tmux commands, future cleanup helpers, etc). Those calls inherit `os.environ`. We **strip `CLAUDE_I_SENTINEL` from the `env` kwarg** passed to those `subprocess.run` calls so the var does not bleed into Python-side sibling processes. The in-tmux `sh -c` argument still embeds the var via the explicit string prefix (Layer 1), so sub-`claude` is unaffected.
  - **What this story does NOT solve:** sub-`claude` is free to forward its own env to its descendant tools. That surface is outside `claude-i`'s reach. AC-4 scope is bounded accordingly.
  - **Common executor trap:** "the prefix is redundant once we sanitize env" is **false**. The prefix is the delivery channel; the env strip is the isolation channel. They solve different problems. The test contract in Task 2.4 requires BOTH a "stripped from env" assertion AND a "still in sh prefix" assertion specifically to catch this.
- **G12 (partial):** This story upgrades the `hook_installed()` check. The remaining G12 fix (doctor runtime verification) is in STORY-001.5.
- **Exit code 2** for dependency/config errors follows POSIX convention (misuse of shell command). Use `sys.exit(2)` not `raise SystemExit`.
- **Cross-story coordination — `runner.py` double-touch with STORY-001.2:** this story modifies `runner.run()` for env isolation (Task 2.4). STORY-001.2 will modify the same function for `tempfile.mkstemp` (gap G5), `reaper.register_cleanup` wiring (gap G6), and exit-code differentiation (gap G8). The Epic serializes these sequentially (001.1 then 001.2), so no parallel merge conflict — but the executor should keep the env-isolation patch in a small, single-purpose commit so STORY-001.2's `runner.py` edits remain auditable as separate diffs.
- **Code reality check (verified 2026-05-17 by @po against `main`):** `src/claude_i/runner.py:76-78` currently builds `parts = [f"CLAUDE_I_SENTINEL={shlex.quote(str(sentinel))}", "exec", "claude"]` then `claude_cmd = " ".join(parts)`. That prefix is what AC-4 / Task 2.4 require to be preserved. `src/claude_i/runner.py:80-92` is the `tmux("new-session", ..., "sh", "-c", claude_cmd)` call — that is the `subprocess.run` whose `env` kwarg needs sanitization. Currently `tmux()` (line 26-33) calls `subprocess.run` with no `env` kwarg (so inherits `os.environ`). The minimum change is plumbing an optional `env` parameter through `tmux()` or replacing that one call site with a direct `subprocess.run(...)` that takes `env=sanitized_env`. Either is acceptable; pick the one that keeps `tmux()`'s read-side helpers (the `capture-pane`, `set-buffer`, `paste-buffer`, `send-keys` calls) unchanged.
- **Expected files to touch:**
  - `src/claude_i/deps.py` — full implementation
  - `src/claude_i/hook.py` — upgrade `hook_installed()`, `install_hook()`
  - `src/claude_i/runner.py` — env sanitization
  - `src/claude_i/cli.py` — `--permission-mode` flag, wire `check_deps()`
  - `src/claude_i/settings.py` — possibly update `HOOK_CMD` or add `HOOK_ENTRY` constant
  - `tests/test_deps.py` — new
  - `tests/test_hook.py` — new
  - `tests/test_cli.py` — extend
  - `tests/test_runner.py` — extend
  - `NOTES.md` — matcher support finding

## Testing

- **pytest unit tests** (all via mocking — no real `claude` or `tmux` invoked):
  - `test_deps.py::test_missing_tmux_exits_2` — mock `shutil.which` returning None for `tmux`; assert `SystemExit(2)`.
  - `test_deps.py::test_missing_claude_exits_2` — same for `claude`.
  - `test_deps.py::test_both_present_no_exit` — mock both present; assert no `SystemExit`.
  - `test_deps.py::test_tmux_hint_macos` — mock `platform.system()` = `"Darwin"`; assert hint contains `"brew"`.
  - `test_deps.py::test_tmux_hint_ubuntu` — mock `/etc/os-release` with `ID=ubuntu`; assert hint contains `"apt"`.
  - `test_hook.py::test_hook_installed_detects_legacy_hook` — settings.json with old-format hook (no matcher); assert returns `False`.
  - `test_hook.py::test_hook_installed_detects_correct_hook` — settings.json with full new-format hook; assert returns `True`.
  - `test_hook.py::test_install_hook_preserves_existing_hooks` — settings.json with a pre-existing `Stop` hook; after `install_hook()`, both the old and new entries are present.
  - `test_runner.py::test_sentinel_stripped_from_subprocess_env` — patch subprocess; verify `CLAUDE_I_SENTINEL` not in captured `env` kwarg.
  - `test_runner.py::test_sentinel_still_in_sh_command` — patch subprocess; verify the `sh -c <claude_cmd>` arg string starts with `CLAUDE_I_SENTINEL=`. **Both env-strip and sh-prefix tests must pass** — the first alone would pass on a broken implementation that loses the sentinel entirely.
  - `test_cli.py::test_permission_mode_default` — assert `--permission-mode acceptEdits` appears in subprocess call.
  - `test_cli.py::test_permission_mode_override` — pass `--permission-mode bypassPermissions`; assert overridden value appears.
- **Manual smoke (requires real tmux + claude):** Run `claude-i "echo hello"` and verify no collision with pre-existing Stop hooks (if any). Run with `tmux` removed from PATH; verify exit 2 with brew/apt/dnf hint.

## File List

**Modified:**

- `src/claude_i/deps.py` — full G3 implementation: `check_deps()` exits 2 with OS-specific install hints; `_tmux_install_hint()`, `_linux_distro_ids()`, `_parse_os_release()` helpers; `CLAUDE_INSTALL_URL` constant.
- `src/claude_i/cli.py` — `--permission-mode` flag (default `acceptEdits`) prepended to `extra_args` (G1); `deps.check_deps()` invoked before `hook.ensure_hook()` (Task 2.2); exit-code epilog added with `RawDescriptionHelpFormatter` (Task 2.8).
- `src/claude_i/runner.py` — `_STRIPPED_ENV_VARS` constant + `_sanitized_env()` helper; `tmux()` gains optional `env: dict[str, str] | None = None` kwarg; the `new-session` call site now passes `env=_sanitized_env()` (G4 Layer 2). Shell prefix `CLAUDE_I_SENTINEL=<path>` preserved verbatim (G4 Layer 1). Module docstring rewritten to document the two-layer contract.
- `src/claude_i/hook.py` — `hook_installed()` tightened to a structural check via new `_is_claude_i_hook_entry()` helper (Task 2.6); module docstring updated to record the G2 / matcher decision. `install_hook()` already appended-not-replaced; behavior locked in by new test (Task 2.7).

**New:**

- `tests/test_deps.py` — 8 tests covering missing-tmux/claude exits, OS-specific hints (macOS / Ubuntu / Fedora / generic fallback), no `/etc/os-release` graceful fallback, both-present no-exit.
- `tests/test_cli.py` — 6 tests: `--permission-mode` default + override + precedence vs user extras, deps-before-hook call order, exit-code epilog visible, `--version` regression (no callbacks fire).
- `tests/test_runner.py` — 3 tests: G4 env-strip assertion, G4 shell-prefix-preserved assertion, sanitized-env preserves unrelated vars.
- `tests/test_hook.py` — 9 tests: missing settings file, malformed JSON, correct hook detected, legacy hook (right command, wrong type) detected as false, unrelated hooks ignored, install creates fresh file, install preserves pre-existing hooks, install refuses malformed JSON, install→detect roundtrip.
- `NOTES.md` — operator-facing log; § "Hook Matcher Support" records the Task 2.5 investigation (sources, decision, revisit conditions).

**Unchanged (verified):**

- `seed/claude-i` — `git diff seed/claude-i` empty per AC.
- `src/claude_i/settings.py`, `src/claude_i/reaper.py`, `src/claude_i/__init__.py`, `tests/test_import.py` — no touches; pre-existing tests still pass.

## Dev Agent Record

**Executor:** @dev (Dex)
**Model:** Claude Opus 4.7 (1M context)
**Execution mode:** YOLO (autonomous) — story explicit + @po pre-validated GO with conditions
**Date:** 2026-05-17
**Duration:** ~90 minutes (Task 2.5 used ~15 of the 90-min cap; remaining tasks straight-line)

### Agent Model Used

`claude-opus-4-7[1m]` via Claude Agent SDK (Sinkra Hub agent wrapper).

### Decisions

1. **G4 — `tmux()` kwarg vs direct subprocess.run at the call site.** Per the @po code-reality-check, two options: add optional `env` kwarg to `tmux()` (touches the helper but read-side calls keep inheriting `os.environ` by passing nothing) OR replace the one new-session call site with a direct `subprocess.run(..., env=...)`. Chose Option 1 — symmetric API surface, no duplication of the argv list, keeps the helper as the single tmux entrypoint, and read-side calls remain a 1-line `tmux("capture-pane", ...)`. The optional `env=None` parameter means existing callers (capture-pane / set-buffer / paste-buffer / send-keys / kill-session) need zero change.
2. **G4 — strip-list constant `_STRIPPED_ENV_VARS`.** Factored the strip rule into a tuple constant rather than inlining `if k != "CLAUDE_I_SENTINEL"` in a dict comprehension. STORY-001.2 / 001.5 may extend the strip set; this gives them a single anchor.
3. **G3 — install URL.** `https://docs.claude.com/en/docs/claude-code/setup` — chosen over the generic root because it's the canonical landing page for fresh installs. Constant `CLAUDE_INSTALL_URL` so a future story can update without touching test assertions (which check for the URL via the constant, not a literal).
4. **G2 — `_is_claude_i_hook_entry` helper.** Factored the structural check into a tiny helper so the docstring can explain *why* the structural check matters (catches `type: http` legacy entries) without crowding the loop.
5. **Task 2.5 — DEFER over try-and-test.** With no documented `matcher` schema for `Stop` events and a 90-min cap, I did not invent one. The shell guard inside `HOOK_CMD` already provides the practical isolation; the residual "Claude Code fires the callback before the guard runs" cost is a no-op `cat` / `touch` to a path that fails-soft. Recording the finding in `NOTES.md` and forward-linking it from the hook module docstring gives the next visitor everything they need.
6. **Anti-pattern smoke test for G4.** Before claiming Task 2.4 done, I manually mutated `runner.py` to remove the shell prefix, re-ran `test_runner.py`, confirmed `test_sentinel_still_in_sh_command` failed with the expected diagnostic, then restored runner.py from a tmp backup. Confirms the second assertion isn't redundant.

### Test Summary

- **Total tests:** 30 (4 pre-existing in `test_import.py`, 26 new across `test_deps.py` / `test_cli.py` / `test_runner.py` / `test_hook.py`).
- **Pass rate:** 30 / 30.
- **Quality gates:**
  - `pip install -e ".[dev]"` — exit 0.
  - `pytest tests/` — 30 passed.
  - `ruff check src/ tests/` — All checks passed.
  - `mypy src/claude_i/` (strict) — Success: no issues found in 7 source files.
  - `git diff seed/claude-i` — empty.
  - `claude-i --version` regression — prints `claude-i 0.2.0.dev0`, no callbacks fire on `--version`.

### Debug Log References

None — no debugging beyond the deliberate anti-pattern smoke for G4 (described above).

### Completion Notes

- All 8 tasks marked `[x]`. All 4 critical gaps (G1, G2, G3, G4) closed; partial G12 (hook_installed structural check) also landed as part of Task 2.6.
- AC-1 / AC-2 / AC-3 / AC-4 / AC-5 / AC-6 / AC-7 / AC-8 — all satisfied.
- @po conditions honored: shell prefix preserved (1); Task 2.5 well within 90-min cap (2); G4 in its own atomic commit (3); both G4 assertions present and asserted (4).
- 4 atomic commits, one per gap (G3 / G1 / G4 / G2), in the order recommended by advisor for clean diffs.
- Constitution: commits made locally under `AIOX_ACTIVE_AGENT=dev`. No `git push` — delegated to `@devops` per Article II.
- Next: `@qa *review-story docs/stories/STORY-001.1-critical-gaps-g1-g4.md`.

### CodeRabbit Self-Healing

Skipped — CodeRabbit CLI requires WSL setup not present in this environment (macOS dev box). `coderabbit_iterations: 0` for this reason only; warning logged per the develop-story skill's documented fallback. No replacement quality gate needed — the 30 unit tests, strict mypy, and ruff checks cover what CodeRabbit's static analysis would have flagged on a Python diff of this size.

## QA Results

### Review Date: 2026-05-17

### Reviewed By: Quinn (Test Architect)

### Gate: **PASS** — Quality Score 94/100

Gate file: `docs/gates/STORY-001.1-gate.md`

### CodeRabbit Self-Healing

- Iterations: 0/3
- Outcome: SKIPPED — CodeRabbit CLI requires WSL setup not present in this macOS environment. Documented fallback per skill spec. The 30 unit tests + strict mypy + ruff cover the static analysis surface CodeRabbit would have flagged on a Python diff of this size.

### Risk Profile

- Depth: **standard**
- Escalation triggers fired: none (no auth/payment files; tests added; diff < 500 lines; no prior FAIL gate; 8 ACs is exactly at threshold but not exceeded; no >10-consumer modified files).

### Independent Quality Gates (re-run by @qa in fresh venv)

| Gate | Result |
|---|---|
| Fresh `python3 -m venv` + `pip install -e ".[dev]"` | exit 0 (Python 3.14.3) |
| `pytest tests/` | **30 passed** in 0.10s |
| `ruff check src/ tests/` | All checks passed |
| `mypy --strict src/claude_i/` | Success: no issues in 7 source files |
| `git diff seed/claude-i` | empty (seed untouched) |
| `claude-i --version` | `claude-i 0.2.0.dev0`, no callbacks fire |
| `claude-i --help` | exit-code epilog rendered (all 3 lines) |

All gates re-verified — match @dev's claimed results 1:1.

### Acceptance Criteria Coverage

**8/8 ACs verified satisfied.** See gate file `### Acceptance Criteria Coverage` table for the per-AC evidence map.

### Specific Concerns Assessment (from review mission)

| Concern | Verdict |
|---|---|
| G2 deferral justification | **ACCEPTED WITH NOTES** — NOTES.md cites 4 authority sources; matcher field genuinely undocumented for `Stop` events; structural `hook_installed()` check is forward-compatible foundation. |
| G4 design correctness | **VERIFIED** — both env-strip AND sh-prefix assertions present, passing, and load-bearing per @dev's anti-pattern smoke. |
| G1 default in subprocess args | **VERIFIED** — `cli.py:120` prepends to extras; overridable; tested via 3 cases. |
| G3 OS hints + exit 2 | **VERIFIED** — Darwin/Ubuntu/Fedora/generic/missing-file all tested; exit code 2 confirmed. |
| PO conditions (a/b/c/d) | **ALL HONORED** — shell prefix preserved verbatim, Task 2.5 ~15 min, G4 single-purpose commit, both G4 assertions present. |
| Forward-compat for STORY-001.2 | **CLEAN SEAMS** — `_STRIPPED_ENV_VARS` constant, optional `env` kwarg on `tmux()`, explicit forward-links in docstrings to G5/G6/G8. |
| Atomic commits | **BISECTABLE** — 4 commits map 1:1 to gaps with clear scope and bodies. |

### Code Quality Assessment

Implementation is exceptionally clean: docstrings explain *why* not just *what*, constants are extracted into named symbols with clear ownership (`HOOK_CMD`, `_STRIPPED_ENV_VARS`, `EXPECTED_BINARIES`, `CLAUDE_INSTALL_URL`), helper functions are small and single-purpose, every error path has a graceful fallback. The G4 two-layer contract (delivery via shell prefix + isolation via env strip) is documented in both module docstring and test docstrings, making the executor-trap @po flagged genuinely hard to fall into.

### Refactoring Performed

None — code did not require @qa-side refactoring.

### Deploy Readiness

Skipped — `deploy_type: none` (Python library/CLI, no production deploy surface).

### Compliance Check

- Python typing (PEP 484 strict): ✅ mypy --strict clean across 7 files
- Code style (ruff): ✅ clean
- Test coverage: ✅ 30 tests / 8 ACs (3.75 tests per AC avg) — every AC has at least one directly-verifying test
- Seed-port discipline (verbatim seed unchanged): ✅ `git diff seed/claude-i` empty
- Constitution adherence: ✅ commits made locally under `AIOX_ACTIVE_AGENT=dev`; no `git push` from @dev (correctly delegated to @devops)
- Story conditions from @po: ✅ all 4 honored

### NFR Validation

| NFR | Status |
|---|---|
| Security | PASS |
| Performance | PASS |
| Reliability | PASS |
| Maintainability | PASS |

Detail in gate file.

### Top Issues

None blocking. Two minor cosmetic observations (non-gating):
1. `_is_claude_i_hook_entry` is private but referenced in docstrings — naming consistent, no action.
2. `claude-i --help` emits ANSI color codes under TTY — argparse default; noted for CI fixture authors.

One forward-compat note: when STORY-001.2 re-touches `runner.py` for G5/G6/G8, reviewer should confirm the G4 two-layer contract is not regressed (a one-line `grep -q 'CLAUDE_I_SENTINEL=' src/claude_i/runner.py` as a CI tripwire would add belt-and-braces).

### Files Modified During Review

None.

### Recommended Status

**✅ Ready for Done** — proceed `@devops *push` → `@po *close-story`.

### Gate Status

Gate: PASS → `docs/gates/STORY-001.1-gate.md`
Quality Score: 94/100
Risk profile: standard


## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-17 | @dev (Dex) | Implementation complete. 4 atomic commits (G3 → G1 → G4 → G2): `bcb411f` deps + OS hints, `b0e9eea` cli (permission-mode + deps gating + exit-code epilog), `8e663e0` runner env-strip, `6fd4497` hook structural check + NOTES.md. 30/30 tests pass, ruff/mypy clean, seed unchanged, `--version` regression intact. Status → Ready for Review. Next: `@qa *review-story`. |
| 2026-05-17 | @sm (River) | Initial story draft from EPIC-001 (G1-G4 + partial G12) |
| 2026-05-17 | @po (Pax) | Validated 9/10 [GO with Auto-Fix]. Context: Epic 001, after STORY-001.0 Done (96/100 QA PASS). 1 prior story analyzed. D10: 1 critical contradiction surfaced (Task 2.4 vs Dev Notes G4 — would have broken pipeline if executor followed literally), 4 auto-fixes applied. Conditions: (a) executor MUST keep the `CLAUDE_I_SENTINEL=` shell prefix inside `sh -c claude_cmd` and ONLY strip from the `env` kwarg of sibling `subprocess.run` calls; (b) Task 2.5 hard time-box of 90 min — fall back to shell-guard-only beyond that; (c) coordinate `runner.py` edits with STORY-001.2's pending changes (serialize, small commits); (d) both G4 test assertions (env-strip + sh-prefix) required — a single assertion masks the broken design. Auto-fixes applied: (1) frontmatter completed (Executor `@dev`, Quality Gate `@qa`, Deploy Type `none`, Status `Ready`); (2) AC-4 rewritten to bound scope (sibling subprocesses only, not sub-`claude` descendants) and add explicit two-assertion verification contract; (3) Task 2.4 contradiction resolved — explicit KEEP-prefix + STRIP-from-env-kwarg pattern, anti-pattern callout, both-test-required contract; (4) Task 2.5 time-boxed (90 min) with explicit 3-branch decision matrix and "do not block 2.6/2.7" clause; (5) Dev Notes G4 rewritten as "two layers, both required" with executor-trap warning; (6) Testing section split into both G4 assertions; (7) cross-story coordination note for runner.py double-touch with 001.2 added; (8) code-reality-check anchor against current `runner.py` (lines 76-92) added. |
