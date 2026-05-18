# STORY-001.1 Quality Gate

| Field | Value |
|---|---|
| Story | STORY-001.1 — Critical Hardening: Permission Mode, Hook Scoping, Dep Check, Env Var Hygiene |
| Epic | EPIC-001 |
| Gate | **PASS** |
| Quality Score | **94 / 100** |
| Reviewer | Quinn (Test Architect) |
| Review Date | 2026-05-17 |
| Reviewed Commits | `bcb411f`, `b0e9eea`, `8e663e0`, `6fd4497`, `635809f` (5 ahead of `origin/main`) |
| Risk Profile | standard |
| Expires | 2026-05-31 |

## Status Reason

All 8 ACs verified satisfied. 30/30 pytest pass in a fresh venv, ruff clean, mypy strict clean across 7 source files, seed untouched, `--version` regression intact, exit-code epilog rendered correctly. G2 matcher deferral is well-documented in `NOTES.md` with 4 cited sources and forward-link conditions; AC-5's fallback clause explicitly covers this branch. G4 two-layer contract correct — both env-strip and sh-prefix assertions present and passing, anti-pattern smoke documented. 4 atomic commits, each bisectable. Forward-compat seams clean for STORY-001.2.

## Independent Quality Gates (re-run by @qa)

| Gate | Result | Notes |
|---|---|---|
| `python3 -m venv` + `pip install -e ".[dev]"` (fresh) | exit 0 | Python 3.14.3 |
| `pytest tests/` | **30 passed** in 0.10s | Matches @dev's count |
| `ruff check src/ tests/` | All checks passed | — |
| `mypy --strict src/claude_i/` | Success: no issues in 7 source files | — |
| `git diff seed/claude-i` | empty | Seed integrity preserved |
| `claude-i --version` | `claude-i 0.2.0.dev0` | No callbacks fired |
| `claude-i --help` | Exit-code epilog rendered | All 3 lines visible |

## Acceptance Criteria Coverage

| AC | Status | Evidence |
|---|---|---|
| AC-1 (`--permission-mode acceptEdits` default + overridable) | ✅ COVERED | `test_permission_mode_default`, `test_permission_mode_override`, `test_permission_mode_precedes_user_extras`. `cli.py:120` prepends `["--permission-mode", args.permission_mode]` to `extra_args`. |
| AC-2 (`tmux` missing → exit 2 + OS hint) | ✅ COVERED | `test_missing_tmux_exits_2` + `test_tmux_hint_macos/ubuntu/fedora/generic_fallback/no_os_release`. |
| AC-3 (`claude` missing → exit 2 + install URL) | ✅ COVERED | `test_missing_claude_exits_2` asserts `CLAUDE_INSTALL_URL` in stderr. |
| AC-4 (CLAUDE_I_SENTINEL stripped from sibling subprocess env, retained in sh prefix) | ✅ COVERED | Both assertions present: `test_sentinel_stripped_from_subprocess_env` AND `test_sentinel_still_in_sh_command`. `test_sanitized_env_strips_only_sentinel` validates unrelated vars preserved. |
| AC-5 (matcher field OR shell-guard fallback) | ✅ COVERED (fallback branch) | NOTES.md documents matcher investigation; shell guard inside `HOOK_CMD` (settings.py:20-25) remains the isolation mechanism. AC-5's "if not supported, falls back to shell guard only" branch is the operative path. |
| AC-6 (`hook_installed()` structural check beyond plain `command == HOOK_CMD`) | ✅ COVERED | `_is_claude_i_hook_entry()` checks `type == "command"` AND `command == HOOK_CMD`. `test_hook_installed_detects_legacy_hook` proves the seed's loose check would have false-positived on `type: http` entries. |
| AC-7 (`deps.check_deps()` before any tmux/hook operation) | ✅ COVERED | `test_deps_called_before_hook` asserts call order `["deps", "hook"]`. `cli.py:113` invokes `deps.check_deps()` at line 113, `hook.ensure_hook()` at line 114. |
| AC-8 (Exit codes documented in `--help`) | ✅ COVERED | `test_help_contains_exit_code_epilog`; manual `--help` invocation confirms epilog rendering. |

**ac_covered:** [1, 2, 3, 4, 5, 6, 7, 8]
**ac_gaps:** []

## Assessment of Specific Concerns Flagged in Mission

### 1. G2 Deferral Justification — **ACCEPTED WITH NOTES**

NOTES.md investigation (lines 6-75) cites 4 authority sources in proper order: `claude --help`, local schema paths, live `~/.claude/settings.json`, hooks-architect reference. The finding — `matcher` is documented for `PreToolUse`/`PostToolUse` (tool-name regex), with no `matcher` field on `Stop` groups in any documented Anthropic source — is consistent with Claude Code's published hook format. The structural `hook_installed()` check (type + command + group shape tolerance) is a forward-compatible foundation: any future matcher requirement can be layered via a small extension to `_is_claude_i_hook_entry()` without rewriting the lookup. Time spent (~15 min of 90-min cap) is appropriate. **Verdict: deferral is sound, NOTES.md serves as durable record, AC-5 fallback clause is the operative path.**

### 2. G4 Design Correctness — **VERIFIED**

Both required assertions present in `tests/test_runner.py`:
- Lines 93-106: env-strip assertion (`assert "CLAUDE_I_SENTINEL" not in env`).
- Lines 109-130: sh-prefix preservation assertion (`assert claude_cmd.startswith("CLAUDE_I_SENTINEL=")`).

The anti-pattern smoke test (story Decisions §6) — mutate runner.py to remove shell prefix, confirm `test_sentinel_still_in_sh_command` fails with expected diagnostic, restore — confirms the second assertion is genuinely load-bearing and not redundant. `_sanitized_env()` + `_STRIPPED_ENV_VARS` factoring is correct extension point.

### 3. G1 Implementation — **VERIFIED**

`cli.py:120` builds `extra_args = ["--permission-mode", args.permission_mode, *args.extra]`. Default is `acceptEdits` (cli.py:87). Override path tested. User-supplied extras still appear after our injection (per `test_permission_mode_precedes_user_extras`), and claude's CLI parser takes last-occurrence so users can override by passing their own `--permission-mode` later.

### 4. G3 Deps Hints — **VERIFIED**

OS detection cascade (deps.py:80-93) handles Darwin → brew, ubuntu/debian → apt, fedora/rhel/centos → dnf, plus a graceful generic fallback for missing or unrecognized `/etc/os-release`. Exit code 2 used in both branches (deps.py:111, 117).

### 5. PO Conditions Adherence — **HONORED**

| Condition | Honored? |
|---|---|
| (a) Keep `CLAUDE_I_SENTINEL=` shell prefix in `sh -c claude_cmd`; only strip from env kwarg of sibling `subprocess.run` | ✅ runner.py:129 preserves prefix verbatim; runner.py:150 passes `env=_sanitized_env()` to the new-session call. |
| (b) Task 2.5 hard time-box of 90 min | ✅ ~15 min used; NOTES.md records investigation. |
| (c) Coordinate `runner.py` edits with STORY-001.2 (single-purpose commit) | ✅ Commit `8e663e0` touches only `runner.py` + `tests/test_runner.py` for env isolation; G5/G6/G8 explicitly deferred via module docstring comments. |
| (d) Both G4 test assertions required | ✅ Present and passing; `test_sanitized_env_strips_only_sentinel` adds extra coverage. |

### 6. Forward-Compat for STORY-001.2 — **CLEAN SEAMS**

- `_STRIPPED_ENV_VARS` constant is a tuple — STORY-001.2 can extend without touching call sites.
- `tmux()` `env` kwarg defaults to `None` — read-side calls (capture-pane, set-buffer, paste-buffer, send-keys, kill-session) need zero modification.
- Module docstring (`runner.py:28-30`) forward-links G5 (`tempfile.mkstemp`), G6 (`reaper.register_cleanup`), G8 (exit-code differentiation) explicitly.
- `cli.py:132-147` exposes placeholder `doctor()` / `uninstall()` / `reap()` raising `NotImplementedError` with story refs — clean stubs for 001.5.
- `deps.assert_not_windows()` (deps.py:120-131) already declared as no-op stub for STORY-001.2 / G9.

### 7. Atomic Commits — **BISECTABLE**

| Commit | Scope | Files | Verdict |
|---|---|---|---|
| `bcb411f` | G3 — deps OS hints | `src/claude_i/deps.py`, `tests/test_deps.py` | ✅ Single gap |
| `b0e9eea` | G1 — cli permission-mode + deps gating + exit-code epilog | `src/claude_i/cli.py`, `tests/test_cli.py` | ✅ Wires the CLI surface |
| `8e663e0` | G4 — runner env-strip | `src/claude_i/runner.py`, `tests/test_runner.py` | ✅ Per @po condition (c) |
| `6fd4497` | G2 — hook structural check + matcher deferral | `src/claude_i/hook.py`, `tests/test_hook.py`, `NOTES.md` | ✅ Includes durable matcher record |
| `635809f` | Story status update | `docs/stories/STORY-001.1-...` | ✅ Doc-only |

Each commit body cites the gap, references the story, explains rationale. Bisection on any AC failure would land cleanly on the responsible commit.

## NFR Validation

| NFR | Status | Notes |
|---|---|---|
| **Security** | PASS | Permission-mode default (`acceptEdits`) is the safest non-trivial value; user can opt into stricter modes. Env isolation contract prevents sentinel leakage to sibling subprocesses. Shell-guard remains the runtime isolation for the Stop hook itself. `install_hook` refuses to mutate malformed JSON (refuses-to-corrupt invariant). |
| **Performance** | PASS | All checks are O(1) startup overhead (`shutil.which` × 2, file-read of `/etc/os-release` once, JSON parse of `settings.json`). No regression. |
| **Reliability** | PASS | All error paths handled: missing settings file, malformed JSON, missing `/etc/os-release`, OSError on read. Graceful fallbacks throughout. `install_hook` uses `setdefault` for append-not-replace semantics. |
| **Maintainability** | PASS | Docstrings explain *why* not just *what* (G4 two-layer contract, G2 matcher deferral, forward-links to 001.2/001.5). Constants extracted (`_STRIPPED_ENV_VARS`, `EXPECTED_BINARIES`, `CLAUDE_INSTALL_URL`, `HOOK_CMD`). Helpers small and focused (`_is_claude_i_hook_entry`, `_sanitized_env`, `_parse_os_release`, `_linux_distro_ids`, `_tmux_install_hint`, `_claude_install_hint`). |

## Top Issues

None blocking.

### Minor / Observational (not gating)

1. **`_is_claude_i_hook_entry` is module-private but referenced in docstring as `_is_claude_i_hook_entry()`.** Naming is consistent; no action required. Noted because future docs generation might want to expose the predicate semantics.

2. **`claude-i --help` output uses ANSI color codes when invoked under a TTY** — confirmed from my run via the venv binary. Argparse's default behavior; nothing to fix. Noted in case CI captures the output and compares against an uncolored fixture.

3. **STORY-001.2 will re-touch `runner.py`** for G5/G6/G8. @dev's commit hygiene was correct (single-purpose 8e663e0 for env-strip). Reviewer of 001.2 should confirm 001.2's diff doesn't accidentally regress the G4 two-layer contract — this is the kind of regression that an audit ratio test would catch (`grep -q 'CLAUDE_I_SENTINEL=' src/claude_i/runner.py` post-merge).

## Recommendations

### Immediate (none — gate is PASS)

### Future (low priority)

- **Regression guard for G4 contract.** Consider adding a lightweight CI check that greps `src/claude_i/runner.py` for the literal `CLAUDE_I_SENTINEL=` shell prefix. The test suite catches removal via mocked subprocess, but a one-line `grep` adds a second tripwire that fails even if someone deletes the runner tests too. Low priority; the current test pair is sufficient.
- **Document `CLAUDE_INSTALL_URL` constant in deps.py docstring.** Currently it's used in `_claude_install_hint()` but the module docstring (deps.py:8-15) only mentions tmux hint detection. A one-line addition for symmetry would help future visitors. Cosmetic.

## Quality Score Calculation

- Base: 100
- FAIL count: 0 → −0
- CONCERNS count: 0 → −0
- Minor cosmetic adjustments (G2 deferred branch, no matcher write-path): −6
- **Final: 94 / 100**

The 6-point deduction reflects only that G2's matcher field remains unimplemented (the "stronger" branch of AC-5). The fallback branch is correct, well-documented, and AC-compliant, but the story would score 100 if Anthropic published a documented Stop matcher today and we had implemented it. This is a legitimate "code is exactly as good as it can be given external constraints" deduction, not a defect.

## Gate Decision

**PASS** — Ready for `@devops *push` → `@po *close-story`.

All ACs verified, all PO conditions honored, all gates green in a fresh venv, seed untouched, atomic commits, clean forward-compat seams for STORY-001.2.

---

*Gate file generated by Quinn (Test Architect) on 2026-05-17.*
