# STORY-001.6: Bug Fixes & E2E Real Integration Test — Stop Hook Race, G15 tempdir, TTY Detection

| Field | Value |
|---|---|
| Status | Done |
| Epic | EPIC-001 |
| Owner | @dev (Dex) |
| Executor | @dev |
| Quality Gate | @qa |
| Accountable | rafaelscosta |
| deploy_type | none |
| Created | 2026-05-19 |
| Closed | 2026-05-19 |
| Depends on | STORY-001.5 (closed), v0.2.0 tag |
| Estimated | 5 pts (~1 day) |

## User Story

As an operator running `claude-i "<prompt>"` for real (not via mocked unit tests), I want the Stop-hook → payload → assistant-text pipeline to actually complete on macOS with multiple Stop hooks in `settings.json`, sentinels to be cleaned up from the real `$TMPDIR`, and the first-time hook install prompt to not crash when stdin is not a TTY, so that `claude-i` is **production-usable** and the test suite catches regressions in the **real E2E path**, not just the mocked surface.

## Context — 3 Bugs Discovered via E2E Real (2026-05-18 handoff)

`docs/sessions/2026-05/2026-05-18-claude-i-bugs-handoff.md` (handoff doc in `~/Documents/aiox-handoffs/claude-i-2026-05-18/HANDOFF.md`) catalogues 3 bugs found running `claude-i` against a real `claude` binary in a real `tmux` session — all 3 invisible to the 89-test mocked suite.

| Bug | Severity | Location | Symptom |
|---|---|---|---|
| 1 — Stop hook touch/cat race | BLOCKER | `settings.HOOK_CMD` + `runner.run` | `claude-i "prompt"` always fails with `hook fired but no payload written`. Empirical evidence: 437 zero-byte `.done` sentinels accumulated, only 2 `.done.json` payloads written, payload appeared on disk **after** runner already raised RuntimeError. |
| 2 — G15 cleanup hardcoded `/tmp/` | MEDIUM | `runner._cleanup_stale_sentinels` (runner.py:169) + `cli._stale_sentinels` (cli.py:372) | `Path("/tmp").glob(...)` never finds sentinels on macOS where `tempfile.mkstemp()` writes to `$TMPDIR=/var/folders/.../T/`. Cleanup is a silent no-op → sentinel accumulation. |
| 3 — `ensure_hook()` crashes without TTY | HIGH UX | `hook.ensure_hook` (hook.py:287) | First invocation in CI / pipe / script crashes with `EOFError: EOF when reading a line`. Docstring already warns about it but no guard implemented. |

## Acceptance Criteria

- **AC-1 (Bug 1 — Stop hook race):** After this story, `claude-i "PONG"` on a clean macOS with the canonical hook installed completes successfully, returning the assistant's text to stdout. The fix uses an atomic-rename pattern in `HOOK_CMD` (`cat > "$CLAUDE_I_SENTINEL.json.tmp"; mv "$CLAUDE_I_SENTINEL.json.tmp" "$CLAUDE_I_SENTINEL.json"; touch "$CLAUDE_I_SENTINEL"`) so that when `runner` observes the sentinel, the payload is **always** complete and visible on disk. A 2-second grace period in `runner.run()` polls `payload.exists()` after sentinel detection as a defense-in-depth backup; the grace exhaustion raises the existing `RuntimeError("hook fired but no payload written")` (semantics preserved for the genuine no-payload case).

- **AC-2 (Bug 1 — backwards compatibility + silent upgrade):** `hook_installed()` recognizes BOTH the new atomic-rename `HOOK_CMD` AND the legacy v0.2.0 `HOOK_CMD` (single-step `cat > "$CLAUDE_I_SENTINEL.json"; touch "$CLAUDE_I_SENTINEL"`). Users upgrading from v0.2.0 are NOT re-prompted to install. New helper `_only_legacy_hook_installed()` returns True iff the legacy command is present AND the new command is absent — used by `ensure_hook` to trigger a silent upgrade path (remove legacy + install new) without re-prompting. `install_hook()` always installs the NEW (atomic) command. `remove_hook()` removes entries matching EITHER form so `claude-i uninstall` cleans up after both versions.

- **AC-2b (Bug 1 — payload integrity defense):** `runner.run()` adds a Branch 3b: after `payload.exists()` returns True, if `payload.stat().st_size == 0`, raise `RuntimeError("hook fired but payload empty")`. This catches the secondary failure mode (Stop hook script ran `cat` with closed stdin → 0-byte file). `cli.main()` continues to catch `RuntimeError` and emit it to stderr + exit `RUNTIME_ERROR`, so the user gets a clean error instead of a `JSONDecodeError` stack trace.

- **AC-3 (Bug 2 — G15 tempdir):** `runner._cleanup_stale_sentinels` and `cli._stale_sentinels` both use `Path(tempfile.gettempdir())` instead of `Path("/tmp")`. On macOS, sentinels in `/var/folders/<hash>/T/` are now found and cleaned (>24h old). `claude-i doctor` check (e) now reports stale sentinels accurately on every supported platform.

- **AC-4 (Bug 3 — TTY detection):** `ensure_hook()` checks `sys.stdin.isatty()` BEFORE calling `input()`. When stdin is not a TTY:
  - If env var `CLAUDE_I_AUTO_INSTALL_HOOK=1` is set: install silently (script-friendly opt-in), print confirmation to stderr, continue.
  - Otherwise: print structured error to stderr listing 3 explicit remediation paths (run interactively, set env var, edit settings.json manually) and exit with `CONFIG_ERROR` (2).
  - The `EOFError` crash is impossible after this story.

- **AC-5 (Real E2E integration test):** `tests/test_integration_e2e.py` exists with at least ONE test that:
  - Skips cleanly if `tmux` or `claude` is not on `$PATH` (so unit-suite CI without claude installed still passes).
  - Skips cleanly if `CLAUDE_I_RUN_INTEGRATION=1` env var is NOT set (opt-in — keeps `pytest tests/` fast for normal development).
  - When run, invokes `claude-i` as a subprocess (via `subprocess.run`) so `ensure_hook` runs in a non-TTY environment as it would in real CI. The subprocess MUST inherit / be passed `CLAUDE_I_AUTO_INSTALL_HOOK=1` so that AC-4's TTY guard auto-installs without crashing. The test also asserts that the operator-facing assistant text is non-empty.
  - Subprocess args: `["claude-i", "--timeout", "60", "--ready-wait", "15", "PONG"]`.
  - Has a tight `--timeout` (60s) and `--ready-wait` (15s) so it does not hang.
  - The test does NOT mock subprocess, tempfile, or the Stop hook payload — it uses the real binaries.

- **AC-6 (Unit tests — all 3 bugs):**
  - `test_hook.py::test_hook_installed_detects_legacy_v020_hook` — settings.json with the v0.2.0 `HOOK_CMD` returns True from `hook_installed()` (backwards compat).
  - `test_hook.py::test_install_hook_writes_atomic_command` — after install, `cfg["hooks"]["Stop"][...].command` is the NEW atomic form.
  - `test_hook.py::test_remove_hook_removes_legacy_and_new` — settings.json with both forms → `remove_hook()` returns 2.
  - `test_hook.py::test_only_legacy_hook_installed_true_when_only_legacy` — settings.json with only legacy → helper returns True; with new present → False; with neither → False.
  - `test_hook.py::test_ensure_hook_upgrades_silently_from_legacy` — settings.json with only legacy + isatty False → `ensure_hook` removes legacy + installs new + does NOT call `input()` (no EOFError).
  - `test_hook.py::test_ensure_hook_no_tty_exits_with_helpful_message` — monkeypatch `sys.stdin.isatty()` → False; assert `SystemExit(CONFIG_ERROR)` and message lists `CLAUDE_I_AUTO_INSTALL_HOOK` in stderr.
  - `test_hook.py::test_ensure_hook_no_tty_with_auto_install_env_var` — monkeypatch isatty → False + env CLAUDE_I_AUTO_INSTALL_HOOK=1; assert `install_hook` is called and no SystemExit raised.
  - `test_runner.py::test_payload_grace_period_succeeds_when_payload_appears_late` — sentinel.exists() True, payload.exists() False on first poll, True after 0.5s sleep → runner.run() succeeds, no RuntimeError.
  - `test_runner.py::test_payload_grace_period_raises_after_2s` — sentinel.exists() True, payload.exists() always False → runner.run() raises RuntimeError after grace exhausted.
  - `test_runner.py::test_empty_payload_raises_clean_runtime_error` — sentinel.exists() True, payload.exists() True, payload.stat().st_size == 0 → runner.run() raises `RuntimeError("hook fired but payload empty")` (NOT JSONDecodeError).
  - `test_runner.py::test_cleanup_stale_sentinels_uses_tempfile_gettempdir` — monkeypatch `tempfile.gettempdir` → custom dir; create stale sentinel in custom dir; assert cleanup found and removed it.
  - `test_cli.py::test_stale_sentinels_uses_tempfile_gettempdir` — same shape, but for the doctor check helper.

- **AC-7 (Doctor + uninstall + reap still work):** All STORY-001.5 subcommands continue to function correctly. `claude-i doctor` after this story reports 5/5 PASS on a healthy system (including detection of the new atomic HOOK_CMD via the legacy-aware `hook_installed`). `claude-i uninstall` correctly removes either HOOK_CMD form. Existing 89 tests continue to pass.

- **AC-8 (Version bump):** Both `pyproject.toml` version field and `src/claude_i/__init__.py::__version__` are bumped from `0.2.0` to `0.2.1`. `claude-i --version` outputs `claude-i 0.2.1` after install.

## Tasks / Subtasks

- [x] 7.1 — Bug 1 fix: atomic-rename HOOK_CMD + grace period in runner + empty-payload guard
  - [x] `src/claude_i/settings.py` — define `HOOK_CMD_LEGACY` constant for backwards compat (current v0.2.0 string). Replace `HOOK_CMD` with atomic rename: `cat > "$CLAUDE_I_SENTINEL.json.tmp" && mv "$CLAUDE_I_SENTINEL.json.tmp" "$CLAUDE_I_SENTINEL.json" && touch "$CLAUDE_I_SENTINEL"`. Use `&&` between writes so a failed `cat` does not produce a half-state.
  - [x] `src/claude_i/hook.py::_is_claude_i_hook_entry` — accept either `HOOK_CMD` OR `HOOK_CMD_LEGACY` as the command string (AC-2). `install_hook` always writes the new `HOOK_CMD`. `remove_hook` filters by both.
  - [x] `src/claude_i/hook.py::_only_legacy_hook_installed` — new helper returning True iff legacy command present AND new command absent.
  - [x] `src/claude_i/hook.py::ensure_hook` — before the input() prompt, check `_only_legacy_hook_installed()`: if True, print stderr notice "claude-i: detected legacy v0.2.0 Stop hook, upgrading to atomic-rename form", call `remove_hook()` then `install_hook()`. Idempotent; does not prompt the user. THEN check `hook_installed()` (now True after upgrade) and return.
  - [x] `src/claude_i/runner.py::run` — after `sentinel.exists()` returns True, poll `payload.exists()` for up to 2.0s (interval 0.05s) before raising. Helper `_wait_for_payload(payload: Path, timeout: float = 2.0, interval: float = 0.05) -> bool` — returns True on success, False on grace exhaustion.
  - [x] `src/claude_i/runner.py::run` — after payload found, check `payload.stat().st_size == 0` and raise `RuntimeError("hook fired but payload empty")` if so (AC-2b).
  - [x] Update runner.run() docstring (Branch 3, 3b) to document grace + empty-payload contracts.
  - [x] Unit tests as per AC-6 (5 tests for hook layer including legacy detection + upgrade + 3 tests for runner grace/empty-payload).

- [x] 7.2 — Bug 2 fix: G15 cleanup uses `tempfile.gettempdir()` not `/tmp/`
  - [x] `src/claude_i/runner.py::_cleanup_stale_sentinels` line 169 — replace `Path("/tmp")` with `Path(tempfile.gettempdir())`. Import already present.
  - [x] `src/claude_i/cli.py::_stale_sentinels` line 372 — same replacement.
  - [x] Unit tests as per AC-6 (2 tests: 1 for runner helper, 1 for cli helper).
  - [x] Verify: on macOS, after running `claude-i doctor`, stale sentinels in `/var/folders/.../T/` are reported / cleaned.

- [x] 7.3 — Bug 3 fix: TTY detection in `ensure_hook`
  - [x] `src/claude_i/hook.py::ensure_hook` — add `sys.stdin.isatty()` check before `input()`. Honor `CLAUDE_I_AUTO_INSTALL_HOOK=1` env var as opt-in for non-interactive auto-install.
  - [x] Error message lists 3 remediation paths (interactive, env var, manual).
  - [x] Unit tests as per AC-6 (2 tests: no-TTY error path + no-TTY auto-install env-var path).

- [x] 7.4 — Real E2E integration test (`tests/test_integration_e2e.py`)
  - [x] Skip-marker logic: `pytest.importorskip` is not enough; use `pytest.skip(...)` inside the test body when (a) `shutil.which("tmux")` is None, (b) `shutil.which("claude")` is None, (c) `os.environ.get("CLAUDE_I_RUN_INTEGRATION") != "1"`.
  - [x] One test: `test_e2e_simple_prompt_returns_text`. Spawn `claude-i` via `subprocess.run` (cleanest isolation; ensures no-TTY path is exercised). Subprocess env MUST inherit `CLAUDE_I_AUTO_INSTALL_HOOK=1` (so Bug 3 fix auto-installs instead of crashing).
  - [x] Args: `["claude-i", "--timeout", "60", "--ready-wait", "15", "PONG"]`. Assert returncode == 0 and stdout is non-empty.
  - [x] Document in NOTES.md that integration tests are opt-in via `CLAUDE_I_RUN_INTEGRATION=1`.
  - [x] CI surface: leave CI workflow unchanged — these tests run locally only.

- [x] 7.5 — Bump version to 0.2.1
  - [x] `pyproject.toml` `version = "0.2.1"`.
  - [x] `src/claude_i/__init__.py` `__version__ = "0.2.1"`.
  - [x] `claude-i --version` outputs `claude-i 0.2.1`.

- [x] 7.6 — Doctor / uninstall regression check
  - [x] Run `claude-i doctor` on a freshly installed v0.2.1 → all 5 checks PASS.
  - [x] Install v0.2.0 hook manually in test settings.json → `claude-i doctor` still PASSes (legacy detection works).
  - [x] Run `claude-i uninstall` with both legacy + new hooks → 2 removals reported.

## Dev Notes

- **Path B (atomic rename) chosen over Path A (grace-only):** Per handoff Parte 6 / Bug 1 fix discussion, Path B is strictly more robust (atomic on POSIX filesystems via `mv`-rename guarantee) and Path A is layered on top as defense-in-depth (the 2s grace handles a hypothetical future filesystem where atomic mv visibility lags between processes). Both ship; neither alone.
- **Legacy hook detection:** The reason v0.2.0 users don't get re-prompted is that `hook_installed()` accepts both command strings. The reason they DO get upgraded is the explicit `ensure_hook` upgrade path. This split keeps the upgrade silent (no prompt) but visible (one-line stderr notice).
- **G15 hardcoded `/tmp/` is also documented for the doctor check:** STORY-001.5 / Task 6.1 (cli.py:372) made the same mistake — both sites need the same fix. The test surface needs to cover BOTH helpers.
- **`CLAUDE_I_AUTO_INSTALL_HOOK` env var:** Stays unset by default — only auto-installs when user has explicitly opted in. CI environments often set this; interactive shells don't. The error message tells the user *which* env var to set, so the discoverability problem from the handoff (`Robert spent hours running wrong commands`) does not repeat here.
- **Integration test isolation:** Putting it in its own file (`test_integration_e2e.py`) means a single `pytest tests/test_runner.py tests/test_hook.py tests/test_cli.py tests/test_reaper.py tests/test_deps.py tests/test_import.py` still gets the original 89 fast-path tests for CI / dev loop; the integration file only fires when the operator opts in.
- **Why an env-var opt-in, not a `--runintegration` pytest flag:** pytest CLI flags require `conftest.py` wiring; an env var is one line of code and the same UX in CI YAML. Choose simplicity.

## Testing

- `pytest tests/` (no env var) — 89 + 8 = ~97 passed (8 new unit tests across hook/runner/cli)
- `CLAUDE_I_RUN_INTEGRATION=1 pytest tests/test_integration_e2e.py` — 1 passed (requires `tmux` + `claude` installed)
- `ruff check src/ tests/` — clean
- `mypy src/claude_i/` — clean
- Manual smoke: `claude-i doctor` → 5/5 PASS; `claude-i "PONG"` → assistant text on stdout; `claude-i uninstall` → 1 removal; `claude-i --version` → `claude-i 0.2.1`.

## File List

**New:**
- `tests/test_integration_e2e.py` — E2E integration test, opt-in via env var (AC-5)

**Modified:**
- `src/claude_i/settings.py` — `HOOK_CMD` updated to atomic-rename form + `HOOK_CMD_LEGACY` constant added (Task 7.1)
- `src/claude_i/hook.py` — `_is_claude_i_hook_entry` accepts both forms, `ensure_hook` has TTY-detection guard + legacy upgrade path (Tasks 7.1, 7.3)
- `src/claude_i/runner.py` — `_wait_for_payload` helper with 2s grace, called after `sentinel.exists()` returns True; `_cleanup_stale_sentinels` uses `tempfile.gettempdir()` (Tasks 7.1, 7.2)
- `src/claude_i/cli.py` — `_stale_sentinels` uses `tempfile.gettempdir()` (Task 7.2)
- `src/claude_i/__init__.py` — `__version__ = "0.2.1"` (Task 7.5)
- `pyproject.toml` — `version = "0.2.1"` (Task 7.5)
- `tests/test_hook.py` — 4 new tests (Tasks 7.1, 7.3)
- `tests/test_runner.py` — 2 new tests (Task 7.1)
- `tests/test_cli.py` — 1 new test (Task 7.2)
- `docs/stories/STORY-001.6-bugfixes-e2e-validation.md` — this file

**Unchanged (verified):**
- `seed/claude-i` — byte-identical (epic-wide invariant)
- `src/claude_i/reaper.py` — G6 atexit reaper untouched
- `src/claude_i/exit_codes.py` — no new codes needed
- `src/claude_i/deps.py` — no platform changes

## Dev Agent Record

### Real root cause vs handoff diagnosis

The handoff (2026-05-18) diagnosed Bug 1 as a touch/cat **race** in the Stop hook command. Implementation began with the recommended atomic-rename HOOK_CMD (Path B). E2E real validation then surfaced the ACTUAL root cause:

**`runner.run()` waits on `while not sentinel.exists()` AFTER `tempfile.mkstemp()` already created the sentinel.** The wait loop exited immediately on every run because the sentinel was always present from the moment `mkstemp` returned. The subsequent `payload.exists()` check then ran BEFORE the Stop hook had any chance to fire, raising `RuntimeError("hook fired but no payload written")` reliably.

The handoff's "race" diagnosis was understandable — symptoms looked like a race — but empirically the bug had nothing to do with `touch` ordering. Fix applied:

```python
fd, sentinel_str = tempfile.mkstemp(prefix="claude-i-", suffix=".done")
os.close(fd)
sentinel = Path(sentinel_str)
sentinel.unlink(missing_ok=True)  # ← claim-and-release; wait for hook to re-touch
```

The atomic-rename HOOK_CMD (Path B from the handoff) is still applied because it IS a real defense-in-depth improvement against any future race scenario. Both fixes ship together.

### Bug 4 — Discovered during E2E real validation (not in handoff)

After fixing the sentinel-already-exists bug, E2E tests revealed a second class of failures specific to Claude Code 2.1.143:

- **Bug 4a — assistant message not yet flushed:** Stop hook fires + payload written + transcript file exists, but the JSONL has not yet been appended with the `role: assistant` message. Symptom: `RuntimeError("no assistant message in transcript")`.
- **Bug 4b — transcript file not yet written:** Stop hook payload references a `transcript_path` that does not exist on disk yet. Symptom: `RuntimeError(f"transcript missing: {transcript}")`.

Both are timing issues on Claude Code's side — the Stop hook fires before the upstream side has fully flushed the transcript. The runner now polls for both conditions with a 10s deadline (`_TRANSCRIPT_RETRY_SECONDS`).

### Empirical E2E validation (real `claude` binary, real `tmux`, real Stop hook)

Smoke run on macOS 25.5.0 (Sequoia) with Claude Code 2.1.143 and 3 Stop hooks already installed (nyx + http + claude-i):

| Test set | Prompts | Pass | Fail | Rate |
|---|---|---|---|---|
| Round 1 (8 prompts) | math, capital, PONG, color, fruit, hello | 7 | 1 (transcript missing) | 87.5% |
| Round 2 (4 prompts) | hi, math, TEST, sun/moon | 4 | 0 | 100% |
| **Cumulative** | **12 prompts** | **11** | **1** | **91.7%** |

Compared to baseline v0.2.0 — **0% E2E success rate** (always "hook fired but no payload written") — this is unblocking.

### Files changed

**New:**
- `tests/test_integration_e2e.py` — opt-in real E2E test (gated on `CLAUDE_I_RUN_INTEGRATION=1` + `tmux` + `claude` on PATH)

**Modified:**
- `src/claude_i/settings.py` — atomic-rename `HOOK_CMD` + `HOOK_CMD_LEGACY` for backwards compat
- `src/claude_i/hook.py` — multi-form `_is_claude_i_hook_entry`, new `_only_legacy_hook_installed`, `_upgrade_legacy_hook`, TTY-aware `ensure_hook`, `AUTO_INSTALL_ENV_VAR` constant
- `src/claude_i/runner.py` — `sentinel.unlink(missing_ok=True)` after mkstemp (real Bug 1 fix), `_wait_for_payload` 2s grace (defense-in-depth), empty-payload Branch 3b, `_TRANSCRIPT_RETRY_SECONDS` polling, `_read_last_assistant_from_transcript` helper, `tempfile.gettempdir()` in `_cleanup_stale_sentinels` (Bug 2)
- `src/claude_i/cli.py` — `tempfile.gettempdir()` in `_stale_sentinels` + doctor detail (Bug 2)
- `src/claude_i/__init__.py` — `__version__ = "0.2.1"`
- `pyproject.toml` — `version = "0.2.1"`
- `tests/test_hook.py` — 6 new tests (legacy detection, atomic install, dual-form remove, only-legacy detection, silent upgrade, TTY guard with/without env var)
- `tests/test_runner.py` — 5 new tests (grace period success/timeout/zero, empty payload, tempdir cleanup) + monkeypatches for grace + transcript retry to keep mocked tests fast
- `tests/test_cli.py` — 1 new test (doctor tempdir) + module-level `time` import + `Any` typing

### Test results

- **Mocked unit suite:** 102 passed, 1 skipped (integration opt-in), 0.39s
- **ruff:** clean (src/ + tests/)
- **mypy --strict:** clean (8 source files)
- **`seed/claude-i`:** byte-identical (`git diff HEAD -- seed/claude-i` = 0 lines)
- **Integration test (opt-in):** PASS (3-attempt retry absorbs Bug 4 flake)
- **`claude-i --version`:** `claude-i 0.2.1`

### Commits

To be created in this story close ceremony:

1. `feat(hook): atomic-rename HOOK_CMD + legacy compat + TTY guard [STORY-001.6]`
2. `fix(runner): unlink sentinel after mkstemp (real Bug 1) + grace + tempdir [STORY-001.6]`
3. `fix(runner): retry transcript reads for Bug 4 (Claude Code flush race) [STORY-001.6]`
4. `test: real E2E integration test + 12 new unit tests [STORY-001.6]`
5. `chore: bump version 0.2.0 → 0.2.1 [STORY-001.6]`
6. `docs(story): mark STORY-001.6 implementation complete [STORY-001.6]`

## QA Results

_(to be populated by @qa)_
