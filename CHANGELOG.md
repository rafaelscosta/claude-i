# Changelog

All notable changes to `claude-i` are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.2.2]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.2
[0.2.1]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.1
[0.2.0]: https://github.com/rafaelscosta/claude-i/releases/tag/v0.2.0
