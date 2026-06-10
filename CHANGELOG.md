# Changelog

All notable changes to `claude-i` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] — 2026-06-10

### Fixed
- Clean up late Stop-hook `.done` artifacts even when a timed-out sub-`claude`
  writes after the runner already returned.
- Classify final `No Stop hook signal` failures as documented environmental
  Bug 5 and print actionable retry guidance instead of a raw timeout only.

### Changed
- Prepare the first PyPI Trusted Publishing release as `0.2.4` so the PyPI
  artifact matches the current `main` fixes instead of the older `v0.2.3` tag.
- Upgrade GitHub Actions to Node 24-compatible official action majors:
  `actions/checkout@v5` and `actions/setup-python@v6`.
- Move the Fedora smoke job to `registry.fedoraproject.org/fedora:latest` after
  repeated Docker Hub pull timeouts during PR validation.
- Make PyPI the primary install path for the public package once the Trusted
  Publisher dispatch completes.

## [0.2.3] — 2026-05-19

### Fixed
- **Bug 6 (BLOCKER for real automation) — tmux paste-buffer / Enter race.** The seed's `set-buffer + paste-buffer + send-keys Enter` triple delivers the prompt asynchronously to the TUI input field. For prompts longer than ~40 chars, the `send-keys Enter` lands BEFORE the paste has been fully absorbed → claude receives Enter against an empty/partial input → silent no-op, `AGT idle`, Stop hook never fires. Symptom: `claude-i: No Stop hook signal after Ns` for any prompt above ~40 chars. Empirical bench (2026-05-19) showed this making real AIOX automation unusable (`/idea`, `@analyst` invocations, anything with reasoning context).
- **Bug 6 Fix (two parts):**
  1. Replace the paste-buffer chain with `tmux send-keys -l <prompt>` (literal keystroke injection).
  2. Add `_wait_for_pane_to_contain()` — poll `tmux capture-pane` until a recognizable suffix of the prompt is visible in the input area BEFORE dispatching Enter. `send-keys -l` is still async (keystrokes arrive over frames); the pane-content confirmation closes the residual race for long prompts.
- **Bug 9 (discovered during Bug 6 validation) — chat-title / SKIP misattribution.** claude-code 2.1.143 fires the Stop hook TWICE per prompt: first with a title-generation hint (`"Chat: Geography"`, `"Risk: ..."`, or literal `"SKIP"`), then 5-15s later with the real assistant response. The payload-first path (v0.2.2) accepted whichever fire it saw first → users got `"SKIP"` / chat-titles instead of real answers for `@agent` invocations and skill prompts.
- **Bug 9 Fix:** `_looks_like_chat_title()` predicate detects title artifacts (12 known prefixes + literal `SKIP`). The runner's Stop-hook wait loop drops title fires (clears sentinel+payload, keeps polling within the `--timeout` budget) until it sees a real response. `_extract_text_from_payload()` rejects titles too as a belt-and-suspenders defense.

### Added
- 6 new unit tests in `test_runner.py`:
  - `test_prompt_uses_send_keys_literal_not_paste_buffer` — asserts NO `set-buffer` / `paste-buffer` argv anywhere; exactly one `send-keys -l <prompt>` + exactly one `send-keys Enter`.
  - `test_prompt_send_keys_handles_multiline` — newline-bearing prompt preserved in argv.
  - `test_prompt_send_keys_handles_special_chars` — quotes, backslashes, `$`, Portuguese accents all passed verbatim.
  - `test_looks_like_chat_title_recognizes_known_patterns` — title prefixes + SKIP detected; real answers passed.
  - `test_run_skips_chat_title_fire_and_returns_real_answer` — two-fire sequence (SKIP then real); runner returns the real answer.
  - `test_run_returns_directly_when_no_title_fire` — single non-title payload returns immediately (no false-positive retry).
- 3 new opt-in integration tests in `test_integration_e2e.py`:
  - `test_e2e_long_prompts` — 5 prompts of 30/60/100/150/200 chars all succeed single-shot.
  - `test_e2e_aiox_agent_invocation` — `@analyst` prompt of ~125 chars (above Bug 6 threshold + triggers Bug 9 title fire).
  - `test_e2e_slash_skill_invocation` — `/idea` prompt that empirically failed on v0.2.2 even with `--timeout 300`.

### Changed
- `runner.run()` Stop-hook wait loop rewritten to filter chat-title fires (Bug 9) and the prompt-delivery section rewritten to document the `send-keys -l` + pane-confirmation contract (Bug 6).

### Empirical validation (2026-05-20, real claude binary)
- 70-char prompt: full Rayleigh-scattering answer in 7s (was: timeout on v0.2.2).
- `@analyst` 125-char invocation: full Atlas risk analysis in 23s (was: `"SKIP"` on v0.2.2).
- `/idea` slash skill: actually executed, wrote to `docs/inbox/ideas.md` (was: `"SKIP"` / chat-title on v0.2.2).
- 10/10 math prompts single-shot, 0 chat-title contamination.

## [0.2.2] — 2026-05-19

### Added
- **`--retries N` flag** (default `0`) — opt-in full-session retry loop in `cli.main()`. On `TimeoutError` / `RuntimeError`, the runner tears down the hung tmux session and spawns a fresh one up to `N` additional times before propagating exit code 1. Recommended for non-interactive automation: `claude-i --retries 3 "<prompt>"`. Each retry logs an `attempt N/total failed; retrying...` line to stderr.
- New unit tests covering `--retries`: default single-shot, transient-failure absorption, exhaustion behavior, negative-value clamping (4 tests in `test_cli.py`).
- New unit tests covering payload-first extraction (6 tests in `test_runner.py`).
- New integration test `test_e2e_reliability_with_retries` locking the automation-reliability contract (10 invocations with `--retries 3`, all must pass).
- `NOTES.md` section "STORY-001.7 / Bug 4 + Bug 5" documents the empirical discovery, root causes, and operator guidance.
- `CHANGELOG.md` (this file).

### Changed
- **`runner.run()` now reads `payload["last_assistant_message"]` first** and skips the transcript JSONL parse entirely on the happy path. Eliminates **Bug 4a** (assistant turn not flushed to JSONL) and **Bug 4b** (transcript file referenced by `transcript_path` never written to disk — observed in ~60% of test runs during diagnostics).
- New helper `_extract_text_from_payload(hook_input) -> tuple[str, bool]`. Returns `(text, True)` when the payload field is a non-empty string; `(""; False)` otherwise to trigger the transcript fallback.
- Transcript-parsing fallback path preserved verbatim (with 10s retry from v0.2.1) for older claude-code versions and the verified-empty Branch 1 case.
- Integration test surface refactored:
  - `test_e2e_simple_prompt_returns_text` (the v0.2.1 3-retry test) → renamed to `test_e2e_single_shot_smoke`. Narrowed to a Bug 1 / Bug 3b regression guard; no longer asserts exit code 0 because Bug 5 (Anthropic-side burst hang) can cause single-shot failure without being a claude-i regression.
  - `_E2E_RETRIES` reduced from 3 to 1; reliability is locked in the new `test_e2e_reliability_with_retries` test instead.
- README updated for v0.2.2: URLs, checksums, automation usage, subcommand reference, exit codes table.

### Discovered (but not fixable in claude-i layer)
- **Bug 5 — Anthropic-side session hang under burst load.** Sub-`claude` occasionally produces no output during prompt processing → Stop hook never fires → `claude-i: No Stop hook signal after 90s`. Empirically observed at 30-60% failure rate under tight sequential Python `subprocess.run` invocations; 10/10 in interactive shell. Cannot be eliminated at the claude-i layer — mitigated via the new `--retries` flag.

## [0.2.1] — 2026-05-19

### Fixed
- **Bug 1 (BLOCKER) — REAL root cause: `sentinel.exists()` already True from `tempfile.mkstemp()`.** The v0.2.0 wait loop (`while not sentinel.exists()`) exited immediately because `mkstemp` had already created the sentinel as part of its claim. The handoff diagnosed this as a touch/cat race; that was wrong. Empirical fix: `sentinel.unlink(missing_ok=True)` after `mkstemp` so the loop blocks until the Stop hook re-touches the path. Atomic-rename `HOOK_CMD` also adopted as defense-in-depth.
- **Bug 2 (MEDIUM) — G15 cleanup hardcoded `/tmp/`.** `runner._cleanup_stale_sentinels` and `cli._stale_sentinels` now use `tempfile.gettempdir()` so cleanup actually runs on macOS (`$TMPDIR=/var/folders/.../T/`). v0.2.0 silently found nothing and let sentinels accumulate (437 observed in production).
- **Bug 3 (HIGH UX) — `ensure_hook()` EOFError without TTY.** Added `sys.stdin.isatty()` check + `CLAUDE_I_AUTO_INSTALL_HOOK=1` opt-in for non-interactive auto-install. Non-TTY without the env var now emits a structured error with 3 remediation paths instead of crashing.
- **Bug 4 (LOW-MEDIUM) — Anthropic transcript flush race**, mitigated with 10s polling retry on `_TRANSCRIPT_RETRY_SECONDS` (full elimination came in v0.2.2 via payload-first).
- **Branch 3b (defense-in-depth)** — payload file exists but is 0 bytes → `RuntimeError("hook fired but payload empty")` before `json.loads("")` would otherwise raise a raw `JSONDecodeError`.

### Added
- `HOOK_CMD_LEGACY` constant in `settings.py` so v0.2.0 installs are recognized as installed (no re-prompt on upgrade) and `claude-i uninstall` cleans up either form.
- Helper `_only_legacy_hook_installed()` triggers a silent in-place upgrade from legacy → atomic-rename HOOK_CMD on the first invocation after upgrading.
- `AUTO_INSTALL_ENV_VAR` constant (`CLAUDE_I_AUTO_INSTALL_HOOK`) — opt-in for non-TTY hook auto-install.
- Real E2E integration test gated on `CLAUDE_I_RUN_INTEGRATION=1` + `tmux` + `claude` on PATH (`tests/test_integration_e2e.py`).
- 13 new unit tests (6 hook, 5 runner, 1 cli, 1 legacy update).

### Changed
- Atomic-rename `HOOK_CMD`: `cat → .json.tmp && mv → .json && touch sentinel`. The `&&` chain ensures the touch never fires unless the payload is fully written and visible.
- `tests/test_cli.py::test_stale_sentinels_age_filter` updated to monkeypatch `tempfile.gettempdir()` instead of `Path("/tmp")`.

## [0.2.0] — 2026-05-18

### Added — EPIC-001 (6 stories)
- Bootstrap (`STORY-001.0`): `pyproject.toml`, CI workflow, module refactor from single-file seed, seed/integrity preserved.
- Critical gaps (`STORY-001.1`, G1-G4): `--permission-mode` default `acceptEdits`, dep check via `shutil.which`, env var isolation (two-layer G4: shell prefix delivery + `_sanitized_env()` strip).
- Important gaps (`STORY-001.2`, G5-G9 + G13): atomic `tempfile.mkstemp` (G5), atexit/SIGTERM reaper (G6), `fcntl.flock` on settings.json mutations (G7), named `ExitCode` constants + 4-branch `RuntimeError` contract (G8), Windows guard (G9), UTF-8 encoding (G13).
- PyPI packaging machinery (`STORY-001.3`): `hatchling` build, `publish.yml` GitHub Actions workflow with manual `confirm_release` safety guard.
- Multi-target install (`STORY-001.4`): `install.sh` bootstrap, Homebrew tap repo `rafaelscosta/homebrew-claude-i` scaffolded (formula marked TBD pending public release).
- Doctor/Reaper/UX subcommands (`STORY-001.5`, G10-G18): `claude-i doctor` (5 checks, `--json`), `claude-i uninstall`, `claude-i reap`, `--output-format json` for the main prompt flow, readiness polling (G17) replaces the seed's fixed `time.sleep(ready_wait)`, stale sentinel cleanup on every run (G15).

### Released
- GitHub Release v0.2.0 with wheel + sdist anexed (private repo at the time).
- 89 mocked unit tests, ruff + mypy `--strict` clean, seed/claude-i byte-identical.

### Known issues
- 3 production blockers surfaced via E2E real testing AFTER release ceremony (handoff 2026-05-18). Fixed in v0.2.1 / v0.2.2.

---

[0.2.4]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.4
[0.2.3]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.3
[0.2.2]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.2
[0.2.1]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.1
[0.2.0]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.0
