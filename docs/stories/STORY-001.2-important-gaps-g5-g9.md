# STORY-001.2: Important Hardening — mkstemp, Reaper/atexit, flock, Exit Codes, Windows Guard, Encoding

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Depends on | STORY-001.0, STORY-001.1 |
| Estimated | 5 pts (~2 days) |

## User Story

As a developer running `claude-i` in long-running automation or on flaky systems, I want temporary files to be created safely, orphaned tmux sessions to be cleaned up even on unexpected exits, `settings.json` writes to be race-free, exit codes to be machine-readable, and an early guard on Windows, so that `claude-i` is reliable enough to embed in scripts and CI pipelines.

## Acceptance Criteria

- AC-1: No call to `tempfile.mktemp()` exists anywhere in `src/claude_i/`. All temporary file creation uses `tempfile.mkstemp()` or `tempfile.NamedTemporaryFile`. The sentinel file path returned by `mkstemp()` is passed to the hook as before; the file descriptor returned by `mkstemp()` is closed immediately after creation.
- AC-2: An `atexit` handler and `SIGTERM` signal handler registered at startup guarantee that the tmux session named `claude-i-<pid>` is killed when `claude-i` exits — including on normal exit, `KeyboardInterrupt`, or `SIGTERM`. `SIGKILL` is documented as best-effort in `--help` (cannot be intercepted).
- AC-3: `hook.install_hook()` acquires an exclusive `fcntl.flock` on `settings.json` (or a lock file sibling) before reading and writing the file, and releases it after. If the lock cannot be acquired within 5 seconds, `claude-i` exits with code `1` and an informative message.
- AC-4: Exit code `1` is used for all runtime failures (timeout waiting for Stop hook, transcript parse failure, empty response from sub-claude when that is unexpected). Exit code `0` is used only on successful extraction of a non-empty response OR an explicitly empty response that the caller opted into via `--allow-empty`. `--allow-empty` flag is added to `cli.py`.
- AC-5: Running `claude-i` on native Windows (not WSL2) exits with code `3` immediately after startup, printing: `claude-i requires Linux or macOS. On Windows, use WSL2: https://docs.microsoft.com/windows/wsl/`. No tmux session is started.
- AC-6: Prompts are written to the tmux buffer using explicit UTF-8 encoding. If the prompt contains characters that cannot be represented in the detected locale, `claude-i` logs a warning and proceeds (best-effort) rather than crashing.
- AC-7: `runner.run()` returns a distinguishable value when the response is legitimately empty vs. when parsing failed: empty string `""` for verified-empty assistant turn; raises `RuntimeError` (caught by cli.py, exits code `1`) for payload-present-but-unparseable case.

## Tasks / Subtasks

- [ ] 3.1 — Replace `tempfile.mktemp()` with `mkstemp()` in `runner.py`
  - [ ] Replace seed line 90: `sentinel = Path(tempfile.mktemp(...))` with:
    ```python
    fd, sentinel_str = tempfile.mkstemp(prefix="claude-i-", suffix=".done")
    os.close(fd)
    sentinel = Path(sentinel_str)
    ```
  - [ ] Confirm `payload = Path(str(sentinel) + ".json")` is still correct (no race — payload is written by the hook, not by `claude-i`)
  - [ ] Unit test: `test_runner.py::test_sentinel_uses_mkstemp` — patch `tempfile.mkstemp`; verify `mktemp` is never called
  - [ ] Add `ruff` rule `S322` (bandit: `tempfile.mktemp`) to `pyproject.toml` `[tool.ruff.lint.select]` to prevent regression

- [ ] 3.2 — Implement `reaper.register_cleanup()` in `reaper.py`
  - [ ] Define `_session_to_cleanup: str | None = None` module-level state
  - [ ] `register_cleanup(session: str) -> None` sets `_session_to_cleanup = session` and registers `_atexit_handler` via `atexit.register()` (idempotent — register once)
  - [ ] `_atexit_handler()`: calls `subprocess.run(["tmux", "kill-session", "-t", _session_to_cleanup], ...)` silently if `_session_to_cleanup` is set
  - [ ] Register `signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))` so atexit fires on SIGTERM
  - [ ] Unit test: `test_reaper.py::test_register_cleanup_calls_tmux_on_atexit` — use `subprocess.run` patch; trigger atexit manually

- [ ] 3.3 — Wire `reaper.register_cleanup()` into `runner.run()`
  - [ ] Call `reaper.register_cleanup(session)` immediately after `tmux("new-session", ...)` succeeds
  - [ ] The existing `finally` block's `tmux("kill-session", ...)` call is retained (belt-and-suspenders)
  - [ ] Unit test: `test_runner.py::test_cleanup_registered_after_session_start`

- [ ] 3.4 — Implement `fcntl.flock` in `hook.install_hook()`
  - [ ] Open (or create) a lock file at `SETTINGS.parent / "claude-i.lock"`
  - [ ] Acquire `fcntl.LOCK_EX` with `fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` inside a retry loop (max 5s, 100ms sleep between attempts)
  - [ ] If lock not acquired after 5s: `sys.exit(1)` with message `"settings.json is locked by another process"`
  - [ ] Release lock in `finally` block
  - [ ] Note: `fcntl` is POSIX-only; guard with `if sys.platform != "win32"` (Windows guard story handles the full exit before this code runs)
  - [ ] Unit test: `test_hook.py::test_install_hook_acquires_lock` — patch `fcntl.flock`; verify called with `LOCK_EX`

- [ ] 3.5 — Add `--allow-empty` flag and refine `runner.run()` return semantics
  - [ ] In `runner.py`: when no assistant message is found in transcript, raise `RuntimeError("empty response")` instead of returning `""`
  - [ ] In `cli.py`: catch `RuntimeError("empty response")` — if `args.allow_empty`, print `""` and exit 0; otherwise print error and exit 1
  - [ ] Update `runner.run()` docstring to document the distinction (empty string = verified empty; RuntimeError = parse failure)
  - [ ] Unit test: `test_runner.py::test_empty_response_raises` and `test_cli.py::test_allow_empty_flag`

- [ ] 3.6 — Implement Windows guard in `deps.py`
  - [ ] `assert_not_windows()`: check `sys.platform == "win32"` — if True, print the WSL2 hint and `sys.exit(3)`
  - [ ] Call `assert_not_windows()` as the absolute first action in `deps.check_deps()`
  - [ ] Unit test: `test_deps.py::test_windows_guard_exits_3` — mock `sys.platform = "win32"`; assert `SystemExit(3)`

- [ ] 3.7 — Enforce UTF-8 encoding in prompt delivery
  - [ ] In `runner.run()`, before calling `tmux("set-buffer", ...)`, attempt `prompt.encode("utf-8")`; if `UnicodeEncodeError`, log warning to stderr and continue (best-effort)
  - [ ] Pass `encoding="utf-8"` to `subprocess.run()` calls where `text=True` is set
  - [ ] Unit test: `test_runner.py::test_unicode_prompt_does_not_crash` — pass a prompt with multi-byte Unicode chars; verify no exception raised

- [ ] 3.8 — Document exit codes comprehensively in `cli.py` and `--help`
  - [ ] Extend the epilog: `Exit codes: 0 success, 1 runtime error (timeout / parse failure), 2 dependency or config error, 3 unsupported platform`
  - [ ] Define an `ExitCode` enum or constants in `cli.py` for `SUCCESS=0`, `RUNTIME_ERROR=1`, `CONFIG_ERROR=2`, `PLATFORM_ERROR=3`
  - [ ] Ensure all `sys.exit()` calls across modules use these constants or their integer values consistently

## Dev Notes

- **G5 (mkstemp):** `tempfile.mktemp()` (seed line 90) is a TOCTOU race — the file does not exist when the name is returned, so another process can create it between the call and the first open. `mkstemp()` creates and opens atomically. The fd must be closed immediately since the hook writes the `.json` payload, not `claude-i`.
- **G6 (reaper/atexit):** The seed already calls `tmux("kill-session", ...)` in the `finally` block (seed lines 157-160), but this does not survive `SIGKILL` (cannot) or abnormal exits that bypass `finally`. `atexit` + SIGTERM handler is belt-and-suspenders. Document SIGKILL limitation clearly.
- **G7 (flock):** `settings.json` can be concurrently modified by Claude Code itself. `fcntl.flock` is advisory — it prevents concurrent `claude-i` invocations from clobbering each other but not Claude Code's own writes. Use `LOCK_EX | LOCK_NB` with retry for non-blocking attempt. A lock file sibling (`claude-i.lock`) is safer than locking the settings file directly.
- **G8 (exit codes):** The seed returns `""` on empty (line 147) and `"(hook fired but no payload written)"` on payload-missing (line 132). Neither is machine-readable. Raising `RuntimeError` from `runner.run()` and catching in `cli.main()` is the clean pattern. `--allow-empty` is the escape hatch for callers who legitimately expect empty responses.
- **G9 (Windows):** `sys.platform == "win32"` is the correct check. WSL2 reports `"linux"`. The guard goes in `deps.py` not `runner.py` — it fires before any tmux or hook work.
- **G13 (encoding):** `subprocess.run()` with `text=True` uses the locale's default encoding. On some headless Linux systems this is ASCII. Passing `encoding="utf-8"` explicitly to all subprocess calls and encoding the tmux buffer content proactively prevents silent truncation on large Unicode prompts.
- **`fcntl` import:** Wrap in `try: import fcntl; HAS_FCNTL = True` at module level. If running on Windows (which should have been caught by `assert_not_windows()` already), `HAS_FCNTL = False` and `install_hook()` skips the lock.
- **Expected files to touch:**
  - `src/claude_i/runner.py` — mkstemp, encoding, run() return semantics
  - `src/claude_i/reaper.py` — full implementation
  - `src/claude_i/hook.py` — flock in `install_hook()`
  - `src/claude_i/deps.py` — `assert_not_windows()`
  - `src/claude_i/cli.py` — `--allow-empty`, exit code constants, wiring
  - `tests/test_reaper.py` — new
  - `tests/test_runner.py` — extend
  - `tests/test_hook.py` — extend
  - `tests/test_deps.py` — extend

## Testing

- **pytest unit tests** (all mocked — no real tmux/claude):
  - `test_runner.py::test_sentinel_uses_mkstemp` — verify `mktemp` never called.
  - `test_runner.py::test_empty_response_raises` — mock transcript with no assistant turn; assert `RuntimeError`.
  - `test_runner.py::test_unicode_prompt_does_not_crash` — emoji + CJK chars in prompt; assert no exception.
  - `test_runner.py::test_cleanup_registered_after_session_start` — verify `reaper.register_cleanup` called.
  - `test_reaper.py::test_register_cleanup_calls_tmux_on_atexit` — trigger atexit handler manually; verify tmux kill-session called.
  - `test_hook.py::test_install_hook_acquires_lock` — verify `fcntl.flock` called with LOCK_EX.
  - `test_deps.py::test_windows_guard_exits_3` — mock `sys.platform = "win32"`; assert `SystemExit(3)`.
  - `test_cli.py::test_allow_empty_flag` — mock `runner.run()` to raise `RuntimeError("empty response")`; assert exit 0 with `--allow-empty`.
- **Manual smoke:** On macOS, run `claude-i "return an empty string"` without `--allow-empty`; verify exit 1. With `--allow-empty`; verify exit 0.
- **Concurrent invocation test (manual):** Start two `claude-i` invocations simultaneously; verify second does not corrupt `settings.json`.

## File List

(empty — populated by @dev during execution)

## Dev Agent Record

(empty — populated by @dev)
