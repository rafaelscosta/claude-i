# STORY-001.1: Critical Hardening — Permission Mode, Hook Scoping, Dep Check, Env Var Hygiene

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Depends on | STORY-001.0 |
| Estimated | 5 pts (~2 days) |

## User Story

As a developer running `claude-i` on a system with pre-existing Claude Code hooks and custom permission profiles, I want `claude-i` to launch the sub-`claude` with safe permission defaults, never collide with my own Stop hooks, validate that system dependencies are present, and not pollute the sub-process environment, so that I can adopt `claude-i` without fear of breaking my existing Claude Code setup.

## Acceptance Criteria

- AC-1: `claude-i "<prompt>"` invokes the sub-`claude` with `--permission-mode acceptEdits` by default. A `--permission-mode <mode>` CLI flag allows override; the flag value is passed through verbatim to `claude`.
- AC-2: When `tmux` is not on `$PATH`, `claude-i` exits with code `2` and prints an OS-specific install hint: `brew install tmux` (macOS), `sudo apt install tmux` (Ubuntu/Debian), `sudo dnf install tmux` (Fedora/RHEL). No tmux session is started.
- AC-3: When `claude` is not on `$PATH`, `claude-i` exits with code `2` and prints a link to the Claude Code install docs. No tmux session is started.
- AC-4: The sub-`claude` process is spawned with `CLAUDE_I_SENTINEL` removed from its inherited environment. Post-spawn, the sub-process cannot read `CLAUDE_I_SENTINEL` by any means available to an unprivileged process.
- AC-5: The installed Stop hook entry in `settings.json` includes a `matcher` field (or equivalent scoping mechanism supported by the Claude Code hook format) that restricts the hook to fire only when `CLAUDE_I_SENTINEL` is set, **in addition to** the existing `if [ -n "$CLAUDE_I_SENTINEL" ]` shell guard. If the `matcher` field is not supported in the detected Claude Code version, `claude-i` logs a warning and falls back to the shell guard only.
- AC-6: `hook_installed()` in `hook.py` verifies both the presence of `HOOK_CMD` and the presence of the `matcher` or scoping field (where applicable) — the seed's plain `command == HOOK_CMD` string compare (seed line 34) is no longer the sole verification mechanism.
- AC-7: `deps.check_deps()` is called before any tmux or hook operation in `cli.py`. Missing-dependency errors are surfaced to the user before the hook install prompt.
- AC-8: Exit codes are documented in `--help` output: `0` = success, `1` = runtime error (timeout, parse failure), `2` = dependency missing or config error.

## Tasks / Subtasks

- [ ] 2.1 — Implement `deps.check_deps()` in `src/claude_i/deps.py`
  - [ ] Check `shutil.which("tmux")` — if None, detect OS via `platform.system()` + `/etc/os-release` and emit the correct install hint, then `sys.exit(2)`
  - [ ] Check `shutil.which("claude")` — if None, emit install hint with link, then `sys.exit(2)`
  - [ ] Unit test: `test_deps.py::test_missing_tmux_exits_2` and `test_deps.py::test_missing_claude_exits_2` (mock `shutil.which`)

- [ ] 2.2 — Wire `deps.check_deps()` into `cli.main()` before `ensure_hook()`
  - [ ] Confirm `cli.py` calls `deps.check_deps()` as the first substantive action in `main()`
  - [ ] Unit test: `test_cli.py::test_deps_called_before_hook` (patch both, verify call order)

- [ ] 2.3 — Add `--permission-mode` flag to `cli.py`
  - [ ] `ap.add_argument("--permission-mode", default="acceptEdits", metavar="MODE", help="Claude permission mode (default: acceptEdits)")`
  - [ ] Pass `["--permission-mode", args.permission_mode]` to `runner.run()` as part of `extra_args` before user-supplied extras
  - [ ] Unit test: `test_cli.py::test_permission_mode_default` and `test_cli.py::test_permission_mode_override`

- [ ] 2.4 — Implement env var isolation in `runner.run()`
  - [ ] Build a sanitized env: `env = {k: v for k, v in os.environ.items() if k != "CLAUDE_I_SENTINEL"}`
  - [ ] Remove the `CLAUDE_I_SENTINEL=...` prefix from `claude_cmd` (it was the seed's mechanism at line 96 — it becomes redundant once env isolation is implemented)
  - [ ] Pass `env=env` to `subprocess.run()` calls that spawn the tmux session (specifically the `sh -c claude_cmd` step)
  - [ ] Unit test: `test_runner.py::test_sentinel_not_in_child_env` (mock subprocess, capture env kwarg)

- [ ] 2.5 — Investigate `matcher` field support in Claude Code hook format
  - [ ] Read Claude Code `settings.json` schema (check `claude --help` output and any local schema file in `~/.claude/`)
  - [ ] If `matcher` is supported: update `HOOK_CMD` entry in `settings.py` to include `"matcher": {"env": {"CLAUDE_I_SENTINEL": {"exists": true}}}` (or equivalent schema)
  - [ ] If `matcher` is not supported or the schema is undocumented: document the finding in a `NOTES.md` at repo root and fall back to shell guard only, emitting a `WARNING: hook-matcher unsupported` to stderr on install
  - [ ] Record the finding (supported/unsupported/unknown) in a `# Hook Matcher Support` section of `NOTES.md`

- [ ] 2.6 — Upgrade `hook_installed()` in `hook.py`
  - [ ] Replace the seed's single `command == HOOK_CMD` check (seed lines 33-37) with a two-part check:
    - Part A: command string matches `HOOK_CMD`
    - Part B: if `matcher` was installed, verify the matcher field is present and correct
  - [ ] Return `False` (and log a warning) if an old-style hook without the matcher is detected — forces reinstall
  - [ ] Unit test: `test_hook.py::test_hook_installed_detects_legacy_hook` and `test_hook.py::test_hook_installed_detects_correct_hook`

- [ ] 2.7 — Update `install_hook()` in `hook.py`
  - [ ] Write the new hook entry format (with matcher if applicable)
  - [ ] Preserve all pre-existing hook entries in `settings.json` under `Stop` — do not replace the whole list, only append
  - [ ] Unit test: `test_hook.py::test_install_hook_preserves_existing_hooks`

- [ ] 2.8 — Document exit codes in `cli.py` `--help`
  - [ ] Add an epilog to `ArgumentParser`: `Exit codes: 0 success, 1 runtime error, 2 missing dependency or config error`
  - [ ] Verify `claude-i --help` displays the epilog

## Dev Notes

- **G1 (permission mode):** The seed's `claude_cmd` at line 96 passes no `--permission-mode`. The fix is simply prepending `["--permission-mode", args.permission_mode]` to the `extra_args` forwarded to `claude`. The `--permission-mode acceptEdits` default is the safest value that still permits the tool to do useful work.
- **G2 (hook scoping):** The seed already has a shell-guard (`if [ -n "$CLAUDE_I_SENTINEL" ]` in `HOOK_CMD`), which prevents the hook from writing output on normal `claude` sessions. The gap is that Claude Code may fire the hook callback for ALL `Stop` events before the shell guard runs — causing a visible no-op error in normal claude use. If the `matcher` field exists, it filters at the Claude Code layer before the command is invoked, eliminating the no-op noise. If `matcher` is not supported, the shell guard remains the only protection. **Do not hardcode a matcher schema without first verifying it exists in the installed Claude Code version.**
- **G3 (dep check):** `shutil.which()` is the correct stdlib function. OS detection for the install hint: `platform.system() == "Darwin"` → brew; otherwise read `/etc/os-release` for `ID` or `ID_LIKE` (`ubuntu`/`debian` → apt; `fedora`/`rhel` → dnf). Default fallback: `"install tmux via your system package manager"`.
- **G4 (env isolation):** The seed's mechanism (setting `CLAUDE_I_SENTINEL=...` in the shell command prefix at line 96) works at the shell level but still exposes the var to the child process tree. The fix is to NOT pass the var in the env at all, and instead pass the sentinel path as part of the hook command template itself — but since `HOOK_CMD` uses `$CLAUDE_I_SENTINEL` by reference, the sentinel path must still be in env. The correct approach: set `CLAUDE_I_SENTINEL` in the tmux session's environment only (via `tmux set-environment` or by passing `CLAUDE_I_SENTINEL=<val>` in the shell command to `sh -c`) and strip it from the parent `subprocess.run` env so it does not bleed into other subprocesses spawned by `claude-i` itself. Specifically, strip it from any subprocess that is NOT the tmux-hosted claude session.
- **G12 (partial):** This story upgrades the `hook_installed()` check. The remaining G12 fix (doctor runtime verification) is in STORY-001.5.
- **Exit code 2** for dependency/config errors follows POSIX convention (misuse of shell command). Use `sys.exit(2)` not `raise SystemExit`.
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
  - `test_runner.py::test_sentinel_not_in_child_env` — patch subprocess; verify `CLAUDE_I_SENTINEL` not in captured env.
  - `test_cli.py::test_permission_mode_default` — assert `--permission-mode acceptEdits` appears in subprocess call.
  - `test_cli.py::test_permission_mode_override` — pass `--permission-mode bypassPermissions`; assert overridden value appears.
- **Manual smoke (requires real tmux + claude):** Run `claude-i "echo hello"` and verify no collision with pre-existing Stop hooks (if any). Run with `tmux` removed from PATH; verify exit 2 with brew/apt/dnf hint.

## File List

(empty — populated by @dev during execution)

## Dev Agent Record

(empty — populated by @dev)
