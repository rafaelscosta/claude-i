# EPIC-001: Packaging and Hardening

| Field | Value |
|---|---|
| **ID** | EPIC-001 |
| **Title** | Packaging and Hardening for `claude-i` |
| **Status** | In Progress |
| **Progress** | 3/6 stories Done (50.0%) |
| **Owner** | @pm (Morgan) |
| **Created** | 2026-05-17 |
| **Repository** | rafaelscosta/claude-i (private) |
| **Branch** | main |
| **Seed** | `seed/claude-i` (180 LOC, single-file Python script from gist `isingh/62bdfd0886b0b72bf6231c44f0389ecc`) |

---

## Goal

Promote `claude-i` from a 180-line single-file script into a production-grade, installable Python CLI distributed via PyPI (`pip`, `pipx`, `uv tool`), Homebrew (tap formula), and a one-line `install.sh` curl bootstrap. The 0.2.0 release must close 18 identified gaps (4 critical, 5 important, 6 quality, 3 nice-to-have), ship with a `claude-i doctor` self-diagnostic, a `claude-i uninstall` reversal path, and validated installation on macOS, Ubuntu, and Fedora. Success is measured by a clean-machine smoke test that installs `claude-i`, runs `claude-i "echo hello"`, and gets a deterministic assistant reply with metadata — across 3 OSes — with `claude-i doctor` returning all green on a clean install.

---

## Background / Origin

`claude-i` originated as a gist (`isingh/62bdfd0886b0b72bf6231c44f0389ecc`) that solved a real friction: `claude -p` (Claude Code one-shot mode) skips interactive-session machinery (hooks, MCPs, skills, plugins), while interactive `claude` cannot be scripted prompt-in → text-out. The seed script bridges this by driving an interactive `claude` inside a headless `tmux` session, capturing the final assistant message via a gated Stop hook (sentinel-keyed at `$CLAUDE_I_SENTINEL` to avoid colliding with user-installed Stop hooks), and tearing down the tmux process tree on exit.

A prior analysis pass on the seed code identified **18 gaps** organized in 4 severity tiers — 4 critical (block adoption), 5 important (block reliability), 6 quality (block trust), 3 nice-to-have (block polish). This Epic addresses all 18 alongside the complete multi-target packaging strategy. The Epic is decomposed into 6 sequential stories (Story-0 through Story-5) plus a bootstrap story that is a hard prerequisite for the rest.

**Sources:**
- Seed script: `seed/claude-i` (preserved verbatim for traceability)
- Gist: https://gist.github.com/isingh/62bdfd0886b0b72bf6231c44f0389ecc
- Gap inventory: enumerated below in *Gap Coverage*
- README at repo root linking back to this Epic

---

## In Scope

- Refactor `seed/claude-i` into a proper Python package under `src/claude_i/` with modules (`cli.py`, `hook.py`, `runner.py`, `deps.py`, `reaper.py`, `settings.py`).
- Build system: `pyproject.toml` + Hatchling backend.
- Test suite: `pytest` scaffold, unit + integration tests, CI on GitHub Actions (lint + test matrix).
- Close all **18 gaps** (G1-G18) detailed below.
- PyPI publishing via Trusted Publishing (OIDC, no API tokens in CI).
- Homebrew tap formula with `tmux` as `depends_on`.
- `install.sh` one-liner with OS + package-manager auto-detection (brew / apt / dnf).
- Subcommands: `claude-i doctor`, `claude-i uninstall`, `claude-i reap`, `claude-i --version`.
- Structured output: `--output-format json` exposing assistant text + metadata (cost, tokens, duration).
- Smoke test matrix in CI: macOS-latest, ubuntu-latest, fedora-latest.

## Out of Scope (Non-Goals)

- **No fork of the Claude CLI.** `claude-i` shells out to the official `claude` binary and treats it as an opaque dependency.
- **No MCP server.** `claude-i` is a process-level wrapper, not a Model Context Protocol surface.
- **No language other than Python.** No Go/Rust/Node rewrite. The Python implementation is the canonical artifact.
- **No Windows native support in v0.2.0.** WSL2 is the documented path; native Windows is deferred to a future Epic. Story-2 includes a platform guard that exits with a WSL hint on native Windows.
- **No GUI.** CLI only.
- **No telemetry / phone-home.** All operations are local.
- **No bundled Claude Code or tmux.** Both remain external system dependencies, checked at runtime by `deps.py`.

---

## Gap Coverage Inventory

The 18 gaps from prior analysis, mapped to the stories that close them:

| ID | Severity | Gap | Story |
|---|---|---|---|
| G1 | Critical | Permission prompts hang the session (no default `--permission-mode`) | Story-1 |
| G2 | Critical | Pre-existing user Stop hooks fire alongside `claude-i`'s hook | Story-1 |
| G3 | Critical | No dependency check (`tmux`, `claude` not validated on PATH) | Story-1 |
| G4 | Critical | `CLAUDE_I_SENTINEL` env var leaks into sub-Claude process | Story-1 |
| G5 | Important | `tempfile.mktemp()` is deprecated and insecure | Story-2 |
| G6 | Important | Cleanup doesn't survive `SIGKILL` — tmux session orphaned | Story-2 |
| G7 | Important | Hook installer lacks `flock` — race condition on `settings.json` | Story-2 |
| G8 | Important | No way to distinguish error from legitimate empty response | Story-2 |
| G9 | Important | Cross-platform: Windows native breaks silently | Story-2 |
| G10 | Quality | No streaming output (UX feels frozen on long responses) | Story-5 |
| G11 | Quality | No metadata exposure (cost, token counts) | Story-5 |
| G12 | Quality | Hook installation verification is fragile (string compare) | Story-1 + Story-5 |
| G13 | Quality | Encoding / locale issues on very large prompts | Story-2 |
| G14 | Quality | `SubagentStop` hook event not handled | Story-5 |
| G15 | Quality | Stale sentinel files accumulate in `/tmp` | Story-5 |
| G16 | Nice-to-have | No `--uninstall-hook` or `doctor` subcommands | Story-5 |
| G17 | Nice-to-have | Fixed `--ready-wait` value instead of readiness polling | Story-5 |
| G18 | Nice-to-have | Zero test coverage | Story-0 (scaffold) + every story (tests per story) |

**Total: 18/18 gaps closed across stories 0-5.** Confidence: ALTA — direct read of `seed/claude-i` cross-referenced with the gap analysis supplied in this Epic's brief.

---

## Stories

> Story drafting is the **exclusive authority of @sm**. The table below lists stories @sm will draft from this Epic. Do not interpret entries here as final ACs — they are scope anchors. Each story will be drafted, then validated by @po (10-point check), implemented by @dev, gated by @qa, pushed by @devops.

| ID | Title | Status | Depends On | Gaps Covered | Estimated Effort |
|---|---|---|---|---|---|
| STORY-001.0 | Bootstrap: package skeleton, pyproject, CI, pytest, seed refactor | **Done** | — | G18 (scaffold) | 5 pts (~2 days) |
| STORY-001.1 | Critical hardening: permission-mode, hook scoping, dep check, env var hygiene | **Done** | STORY-001.0 ✓ | G1, G3, G4, G12 (partial) — G2 deferred with NOTES | 5 pts (~2 days) |
| STORY-001.2 | Important hardening: tempfile, reaper, flock, exit codes, platform guard, encoding | **Done** | STORY-001.0 ✓, STORY-001.1 ✓ | G5, G6, G7, G8, G9, G13 | 5 pts (~2 days) |
| STORY-001.3 | PyPI packaging: build, publish (OIDC), `pipx` + `uv tool` validation, `--version` | Draft | STORY-001.0 ✓, STORY-001.1, STORY-001.2 | — (distribution) | 3 pts (~1 day) |
| STORY-001.4 | Multi-target install: Homebrew tap, `install.sh`, OS matrix smoke tests | Draft | STORY-001.3 | — (distribution) | 5 pts (~2 days) |
| STORY-001.5 | UX & operations: `doctor`, `uninstall`, `reap`, JSON output, streaming, polling, residual gap tests | Draft | STORY-001.1, STORY-001.2 | G10, G11, G12, G14, G15, G16, G17 | 5 pts (~2 days) |

**Effort: 28 story-points, ~11 working days (≈2.5 weeks at a sustainable pace).** Confidence: MEDIA — based on seed LOC (180), gap count (18), and typical packaging-and-hardening effort distribution. Missing-evidence: no historical velocity baseline for this repo; estimate is calibrated against analogous Python CLI packaging work in adjacent projects.

### High-Level Acceptance Criteria per Story

> These are **high-level scope anchors only**. @sm produces the full Given/When/Then ACs during story drafting.

**STORY-001.0 — Bootstrap**
- A fresh clone of `main` runs `pip install -e .` successfully and exposes `claude-i` on PATH.
- `pytest` runs (even with zero meaningful tests) and CI's lint + test job passes on `ubuntu-latest`.
- `seed/claude-i` is preserved unchanged; modular code lives in `src/claude_i/` with the modules listed in *In Scope*.

**STORY-001.1 — Critical hardening (G1-G4 + partial G12)**
- `claude-i` invokes the sub-`claude` with `--permission-mode acceptEdits` by default (overridable via flag).
- The installed Stop hook uses a `matcher` or sentinel-keyed scoping that prevents collision with pre-existing user Stop hooks.
- `claude-i` exits with a clear, OS-specific install hint when `tmux` or `claude` is missing from PATH (Linux: `apt install tmux` / `dnf install tmux`; macOS: `brew install tmux`).
- The sub-`claude` process is spawned with `env -u CLAUDE_I_SENTINEL` so the sentinel does not leak.

**STORY-001.2 — Important hardening (G5-G9, G13)**
- All temporary file creation uses `tempfile.mkstemp()` or `NamedTemporaryFile` — no `mktemp()` calls remain.
- An `atexit` handler + signal handlers + a `reaper` module guarantee tmux sessions are torn down even on `SIGTERM` (best-effort note on `SIGKILL`).
- The hook installer acquires `fcntl.flock` on `settings.json` before mutation.
- Exit codes distinguish: 0 success, non-zero codes for missing-dep / hook-failure / timeout / empty-response / sub-claude-error (documented in `--help`).
- Running on native Windows (not WSL) exits with a clear "WSL2 required" message.

**STORY-001.3 — PyPI packaging**
- `python -m build` produces a wheel + sdist that pass `twine check`.
- A GitHub Actions workflow publishes to PyPI on tag push using **Trusted Publishing (OIDC)** — no long-lived secrets.
- `pipx install claude-i` and `uv tool install claude-i` both produce a working `claude-i --version` on a clean machine.

**STORY-001.4 — Multi-target install**
- A Homebrew tap (`homebrew-claude-i`) exposes a formula with `depends_on "tmux"` and a working `brew install rafaelscosta/claude-i/claude-i`.
- `install.sh` (hostable at a stable URL) detects OS + package manager, installs missing system deps (`tmux`), then `pipx install`s the package.
- CI matrix runs end-to-end smoke (`claude-i "echo ping"` returns "pong"-style deterministic output) on macOS-latest, ubuntu-latest, and a Fedora container.

**STORY-001.5 — UX & operations**
- `claude-i doctor` checks: `tmux` present, `claude` present, hook installed-and-correct, `settings.json` valid JSON, no stale sentinels — emits structured pass/fail report (exit non-zero on any failure).
- `claude-i uninstall` removes the Stop hook from `settings.json` (preserving other hooks) and reports what was removed.
- `claude-i reap` kills orphaned tmux sessions matching the `claude-i-*` naming pattern.
- `--output-format json` returns `{text, cost_usd, tokens_in, tokens_out, duration_ms}` (best-effort — fields nullable if upstream `claude` doesn't expose them).
- Readiness polling (probe instead of fixed sleep) replaces `--ready-wait`.
- Stale sentinel files older than 24h are cleaned on every run.
- Tests cover G14 (`SubagentStop` event) and G15 (stale sentinel cleanup).

---

## Dependencies / Risks

| ID | Type | Description | Mitigation | Confidence |
|---|---|---|---|---|
| DEP-1 | External binary | `tmux` must be available on the target system | Document as system dep; `install.sh` and Homebrew formula install it automatically; `doctor` flags absence | ALTA |
| DEP-2 | External binary | The official `claude` CLI must be on PATH and authenticated | Document upstream install link in README; `doctor` flags absence | ALTA |
| DEP-3 | Upstream contract | Claude Code hook format (`Stop` event payload shape, transcript path location) is currently **not under SLA** from Anthropic | Version-pin behavior via integration tests; surface upstream changes as `doctor` warnings | MEDIA — missing evidence: no public Anthropic doc commits to hook payload stability |
| DEP-4 | Upstream contract | Anthropic `claude` CLI flag stability (`--permission-mode`, `--output-format`) | Wrap flag invocations behind feature detection in `deps.py`; fall back gracefully if flags change | MEDIA |
| RISK-1 | Reliability | tmux sessions orphaned by SIGKILL leak file descriptors | `reaper` subcommand + periodic cleanup; documented as known limitation | ALTA |
| RISK-2 | Cross-platform | macOS / Linux distros have divergent `flock` behavior | Use `fcntl.flock` (POSIX); test on macOS + Ubuntu + Fedora in CI | MEDIA |
| RISK-3 | Security | Sub-`claude` could be invoked with elevated permissions if user customizes `--permission-mode` | Default to safest mode (`acceptEdits`); document the risk in `--help` | ALTA |
| RISK-4 | Publishing | PyPI Trusted Publishing requires GitHub repo owner action (one-time pending publisher config) | Story-001.3 includes the one-time PyPI publisher setup step | ALTA |
| RISK-5 | Scope creep | The 18-gap inventory may grow during implementation as new edge cases surface | Out-of-scope-for-v0.2.0 gaps land as Issues on the repo, deferred to a future Epic | ALTA |

---

## Definition of Done (Epic-Level)

The Epic is **Done** when all of the following are simultaneously true:

- [ ] All 6 stories (STORY-001.0 through STORY-001.5) are in `Done` status with @qa PASS verdicts.
- [ ] All 18 gaps (G1-G18) are closed and tagged in their respective stories' PR descriptions.
- [ ] **PyPI release `v0.2.0` is published** and `pipx install claude-i==0.2.0` succeeds on a clean machine.
- [ ] **Homebrew formula is merged** to the tap (`rafaelscosta/homebrew-claude-i`) and `brew install rafaelscosta/claude-i/claude-i` succeeds on macOS.
- [ ] **`install.sh` is hosted on `main`** at a stable repo path and `curl -fsSL <url> | sh` succeeds on a clean Ubuntu and Fedora VM.
- [ ] **3-OS smoke test matrix is green** in CI (macOS-latest, ubuntu-latest, fedora-latest): `claude-i "<deterministic prompt>"` returns expected output.
- [ ] **`claude-i doctor` returns all-green** on a fresh install on all 3 OSes.
- [ ] README is updated with: install matrix (pipx / uv / brew / install.sh), quickstart, troubleshooting (`doctor`), and upgrade / uninstall instructions.
- [ ] `seed/claude-i` is preserved unchanged in `main` for traceability.
- [ ] CHANGELOG.md is created with the `v0.2.0` entry enumerating all closed gaps.

---

## Estimated Effort

**Total: 28 story-points, ~11 working days (≈2.5 weeks).**

| Story | Points | Days |
|---|---|---|
| STORY-001.0 | 5 | 2 |
| STORY-001.1 | 5 | 2 |
| STORY-001.2 | 5 | 2 |
| STORY-001.3 | 3 | 1 |
| STORY-001.4 | 5 | 2 |
| STORY-001.5 | 5 | 2 |
| **Total** | **28** | **11** |

Confidence on estimate: **MEDIA** — calibrated against typical Python CLI packaging work (seed = 180 LOC, 18 gaps, 6 stories, 3-OS matrix). Missing evidence: no prior velocity baseline on this fresh repo. Will be recalibrated after STORY-001.0 closes (the bootstrap story is the velocity probe).

---

## Stakeholders

- **@pm (Morgan)** — Epic owner, scope authority
- **@sm (River)** — Story drafting (exclusive authority — drafts STORY-001.0 through STORY-001.5)
- **@po (Pax)** — Story validation (10-point check per story)
- **@dev (Dex)** — Implementation across all 6 stories
- **@qa (Quinn)** — Quality gate per story + Epic-level smoke validation
- **@devops (Gage)** — PyPI publish workflow, Homebrew tap, install.sh hosting, OS matrix CI, all `git push` operations (exclusive authority)
- **@architect (Aria)** — Consulted for the modular refactor of `seed/claude-i` (module boundaries: `cli.py` / `hook.py` / `runner.py` / `deps.py` / `reaper.py` / `settings.py`)

---

## Change Log

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-05-17 | 0.1 | Initial Epic draft from gap analysis + scope decision (full packaging + hardening) | @pm (Morgan) |
| 2026-05-17 | 0.2 | STORY-001.0 closed → Done. Epic status Draft → **In Progress**. Progress: 1/6 (16.7%). QA PASS 96/100. CI run #26010042733 GREEN. Velocity baseline established: 5 pts / same-day delivery. Next: STORY-001.1 (G1-G4 + G12 partial) ready for @sm draft refinement → @po validation → @dev execution. | @po (Pax) |
| 2026-05-17 | 0.3 | **STORY-001.1 closed → Done.** Progress: 1/6 → **2/6 (33.3%)**. QA PASS 94/100. CI run #26011076243 GREEN (3 jobs). G1+G3+G4 implemented; G2 deferred-with-notes (matcher field undocumented for `Stop` events — NOTES.md cites 4 authority sources; AC-5 fallback branch is operative path; structural `hook_installed()` check is forward-compatible). G12 partial landed (structural hook check). 5 commits on `origin/main` (4 atomic per-gap + status + gate file). Velocity: 5 pts same-day delivery (matches 001.0 baseline). Next: **STORY-001.2** (G5/G6/G7/G8/G9/G13 — important hardening) ready for refinement; deps met (001.0 ✓, 001.1 ✓). | @po (Pax) |
| 2026-05-18 | 0.4 | **STORY-001.2 closed → Done.** Progress: 2/6 → **3/6 (50.0%)**. QA PASS 95/100. CI run #26012342162 GREEN (3 jobs). G5+G6+G7+G8+G9+G13 all implemented. 8 atomic commits on `origin/main` (6 per-gap + 1 test consolidation + 1 docs/gate). HEAD `26bb711`. G4 contract from 001.1 preserved verbatim across all `runner.py` edits (test pair `test_sentinel_stripped_from_subprocess_env` + `test_sentinel_still_in_sh_command` passes). `assert_not_windows()` stub REPLACED (single definition in `deps.py:128`). All 4 AC-7 parse-failure branches landed (3 RuntimeError + 1 explicit empty-string return). New `exit_codes` module is source of truth for 001.5. 68/68 pytest in fresh Python 3.14.3 venv, ruff clean (S306 active), mypy strict clean. CHK-8/9/10 N/A (`deploy_type: none`, no AIOX governance surface in claude-i). Velocity: 5 pts same-day delivery (matches 001.0/001.1 baseline). Forward-compat carryovers to 001.5: G14 (SubagentStop discovery) + G17 (readiness polling) + `exit_codes` reuse. Next: **STORY-001.3** (PyPI packaging — build, OIDC publish, `pipx`/`uv tool` validation, `--version`); deps met (001.0 ✓, 001.1 ✓, 001.2 ✓). | @po (Pax) |

---

## Development Log

### Story 001.0 — Bootstrap: Package Skeleton, pyproject, CI, pytest, Seed Refactor (2026-05-17)

**Built:**
- `pyproject.toml` — Hatchling build backend, Python 3.11+, `claude-i` entry point, ruff/mypy(strict)/pytest config, `[dev]` extras.
- `src/claude_i/__init__.py` — Package docstring + `__version__ = "0.2.0.dev0"`.
- `src/claude_i/settings.py` — Canonical `HOOK_CMD` + `SETTINGS` path; typed `load_settings()` / `write_settings()` helpers.
- `src/claude_i/hook.py` — Verbatim port of `hook_installed()` / `install_hook()` / `ensure_hook()` (seed lines 26-65); delegates I/O to `settings.py`.
- `src/claude_i/deps.py` — `check_deps()` + `assert_not_windows()` stubs; `EXPECTED_BINARIES = ("tmux", "claude")`.
- `src/claude_i/runner.py` — Verbatim port of `tmux()` / `tail_pane()` / `run()` (seed lines 68-160). `tempfile.mktemp` deliberately retained with G5 forward-compat marker.
- `src/claude_i/reaper.py` — `reap_orphans()` / `register_cleanup()` stubs; full impl deferred to STORY-001.2 (G6).
- `src/claude_i/cli.py` — argparse entry point with `--version` (`action="version"`, `%(prog)s {ver}` format) short-circuiting BEFORE `ensure_hook()`; `doctor`/`uninstall`/`reap` placeholders raise `NotImplementedError` (G15/G16 → STORY-001.5).
- `tests/test_import.py` — 4 smoke tests: package imports, all submodules import, `HOOK_CMD` SoT identity, `EXPECTED_BINARIES` enumerated.
- `.github/workflows/ci.yml` — `lint-typecheck-test` job (Python 3.11/3.12, ubuntu-latest, ruff + mypy + pytest + `--version` assertion) + `check-seed-integrity` job (`git diff` against the first commit that introduced `seed/claude-i`).

**Patterns established:**
- Module boundary contract: `settings.py` owns all `~/.claude/settings.json` I/O and the canonical `HOOK_CMD`; `hook.py` / `runner.py` / `deps.py` / `reaper.py` delegate to it; `cli.py` is a thin argparse wiring layer.
- Forward-compat anchors as inline comments: each module carries explicit `G{N}` markers at the exact line downstream stories will edit.
- `HOOK_CMD` single-source-of-truth enforced by `test_hook_cmd_is_single_source_of_truth` — uses identity check (`is`), not equality, to prevent accidental shadowing.
- `--version` MUST short-circuit before any interactive code path (`ensure_hook()` is unreachable on `--version`) so CI never hits the `input()` prompt.
- Defensive type guards (`isinstance(parsed, dict)` in `load_settings`, fallback to `__version__` in `_version_string`) are required by mypy strict and do NOT count as behavior changes — AC-9 preserved.
- CI seed-integrity check compares against the first commit that introduced `seed/`, not `HEAD~1..HEAD`, catching drift across multiple commits.

**Key decisions:**
- Hatchling chosen over setuptools (PyPA-recommended for new projects, native `pyproject.toml`).
- `requires-python = ">=3.11"` to get `tomllib` stdlib + stable `argparse.REMAINDER`.
- `importlib.metadata.version("claude-i")` is the version source — auto-syncs with `pyproject.toml`.
- All 6 downstream stories' tech debt (G2/G5/G6/G7/G15/G17) anchored as inline comments rather than enforced via lint rules — keeps STORY-001.0 minimal while making downstream edits surgical.

**Tech debt identified:**
- `tests/.gitkeep` redundant (LOW, cosmetic) — `tests/__init__.py` already serves as package marker.
- `runner.tail_pane` broad-except (LOW, AC-9 verbatim seed) — tighten opportunistically in STORY-001.2 when touching `runner.py`.

**Tests:** 4 new (smoke). **Deploy:** N/A (`deploy_type: none` — library/CLI scaffold). **CodeRabbit:** 0 iter (skipped — cross-repo, WSL-bound; compensating control: @qa manual gate re-run on fresh venv).

---

### Story 001.1 — Critical Hardening: Permission Mode, Hook Scoping, Dep Check, Env Var Hygiene (2026-05-17)

**Built:**
- `src/claude_i/deps.py` — full G3 implementation: `check_deps()` exits 2 with OS-specific install hints; `_tmux_install_hint()`, `_linux_distro_ids()`, `_parse_os_release()` helpers; `CLAUDE_INSTALL_URL` constant.
- `src/claude_i/cli.py` — `--permission-mode` flag (default `acceptEdits`) prepended to `extra_args` (G1); `deps.check_deps()` invoked before `hook.ensure_hook()`; exit-code epilog added with `RawDescriptionHelpFormatter`.
- `src/claude_i/runner.py` — `_STRIPPED_ENV_VARS` tuple constant + `_sanitized_env()` helper; `tmux()` gains optional `env: dict[str, str] | None = None` kwarg; new-session call site passes `env=_sanitized_env()` (G4 Layer 2). Shell prefix `CLAUDE_I_SENTINEL=<path>` preserved verbatim (G4 Layer 1). Module docstring rewritten to document the two-layer contract + forward-links to G5/G6/G8.
- `src/claude_i/hook.py` — `hook_installed()` tightened to structural check via `_is_claude_i_hook_entry()` helper (G12 partial); module docstring records G2 matcher deferral with forward-link.
- `tests/test_deps.py` (new, 8 tests), `tests/test_cli.py` (new, 6 tests), `tests/test_runner.py` (new, 3 tests), `tests/test_hook.py` (new, 9 tests) — 26 new tests + 4 pre-existing = 30/30 pass.
- `NOTES.md` (new) — operator-facing log; § "Hook Matcher Support" records Task 2.5 investigation (sources, decision, revisit conditions).

**Patterns established:**
- **G4 two-layer contract** (delivery via shell prefix + isolation via env strip): documented in both module docstring and test docstrings. Both `test_sentinel_stripped_from_subprocess_env` AND `test_sentinel_still_in_sh_command` are load-bearing — the second was anti-pattern-smoke-tested (mutate runner.py to remove prefix → test fails with expected diagnostic, then restore). Future stories touching `runner.py` MUST preserve both layers.
- **Strip-list extensibility**: `_STRIPPED_ENV_VARS` as tuple constant gives 001.2 / 001.5 a single anchor to extend without touching call sites.
- **Optional `env` kwarg on `tmux()` helper**: defaults to `None` (inherits `os.environ`). Read-side calls (capture-pane, set-buffer, paste-buffer, send-keys, kill-session) need zero modification. Only the new-session call passes `env=_sanitized_env()`. Keeps `tmux()` as single entrypoint.
- **OS-specific install hints**: `platform.system()` for Darwin → brew; `/etc/os-release` `ID`/`ID_LIKE` cascade for Linux (ubuntu/debian → apt; fedora/rhel/centos → dnf; generic fallback). Pattern reusable for any future OS-aware messaging.
- **Structural hook entry check**: `_is_claude_i_hook_entry()` checks `type == "command"` AND `command == HOOK_CMD`. Catches legacy entries (right command, wrong type). Extension point for any future matcher requirement.
- **Exit code 2 for POSIX dependency/config errors**: documented in `--help` epilog; `sys.exit(2)` (not `raise SystemExit`).
- **Investigation-with-documented-deferral pattern**: Task 2.5 hit the 90-min cap budget rule. When external schema can't be verified, the durable record (NOTES.md) + forward-compatible structural foundation (`_is_claude_i_hook_entry`) is the right pattern, not invention.

**Key decisions:**
1. **G4 — `tmux()` env kwarg vs direct subprocess.run**: chose optional kwarg on the helper (symmetric API surface, single tmux entrypoint, read-side calls untouched).
2. **G4 — strip-list as tuple constant**: factored from inline comprehension to give 001.2 / 001.5 an extension point.
3. **G2 — DEFER over try-and-test**: `matcher` undocumented for `Stop` events; 90-min cap honored (~15 min used); NOTES.md is durable record; shell guard provides practical isolation; structural `hook_installed()` is forward-compatible foundation.
4. **G3 install URL**: `CLAUDE_INSTALL_URL = "https://docs.claude.com/en/docs/claude-code/setup"` as constant so future updates don't touch test assertions.
5. **G4 anti-pattern smoke**: deliberately mutated runner.py to remove shell prefix, confirmed `test_sentinel_still_in_sh_command` fails with expected diagnostic, restored. Confirms the test is genuinely load-bearing.

**Tech debt identified:**
- **G2 carryover (matcher field)**: documented in NOTES.md § "Hook Matcher Support". Revisit when Anthropic publishes Stop-event matcher schema. Current shell-guard branch is AC-compliant.
- **G4 contract tripwire (low priority)**: consider CI `grep -q 'CLAUDE_I_SENTINEL=' src/claude_i/runner.py` as belt-and-braces alongside the test pair. Tests already catch removal via mocked subprocess; grep adds second guard if tests are deleted.
- **`claude-i --help` ANSI color codes under TTY** (cosmetic): argparse default; CI fixture authors should strip if comparing against uncolored.
- **CodeRabbit SKIPPED**: CLI requires WSL (not present on macOS dev box). 30 unit tests + strict mypy + ruff cover the static analysis surface CodeRabbit would have flagged. Documented fallback per skill spec.

**Tests:** 30 / 30 pass (4 pre-existing regression intact + 26 new). 3.75 tests per AC avg. **Deploy:** N/A (`deploy_type: none`). **CodeRabbit:** 0 iter (skipped — WSL-bound on macOS dev box; compensating gates: ruff + mypy strict + pytest in fresh venv).

---

### Story 001.2 — Important Hardening: mkstemp, Reaper/atexit, flock, Exit Codes, Windows Guard, Encoding (2026-05-18)

**Built:**
- `src/claude_i/exit_codes.py` (NEW) — `SUCCESS = 0`, `RUNTIME_ERROR = 1`, `CONFIG_ERROR = 2`, `PLATFORM_ERROR = 3` as `Final[int]` constants. Placed in package (not in `cli.py`) per @architect rationale to avoid circular import. Source of truth for 001.5 (`doctor` / `uninstall` / `reap` subcommands).
- `src/claude_i/reaper.py` — full G6 implementation: `register_cleanup(session)` + `_atexit_handler()` + `_sigterm_handler()` + module-level `_session_to_cleanup` state. `atexit.register` is idempotent (registered once). `signal.signal(SIGTERM, ...)` ensures atexit fires on SIGTERM. Also includes `reap_orphans()` + `_pid_alive()` helpers for 001.5.
- `src/claude_i/runner.py` — G5 (mkstemp + `os.close(fd)`); G6 (`reaper.register_cleanup(session)` wired immediately after `tmux("new-session", ...)`); G8/AC-7 (4-branch refactor: 3 RuntimeError + 1 explicit `return ""`); G13 (UTF-8 encoding for tmux IPC + best-effort `prompt.encode("utf-8")` pre-check). G4 contract from 001.1 preserved verbatim.
- `src/claude_i/hook.py` — G7 (`fcntl.flock` on `claude-i.lock` sibling file, `LOCK_EX | LOCK_NB` with deadline-based retry, 5s timeout → `RUNTIME_ERROR`). Wraps only `install_hook()` write path; `hook_installed()` read-only path untouched (G2 deferral from 001.1 preserved). String-form `sys.exit` at lines 93/119 migrated to `CONFIG_ERROR` / `RUNTIME_ERROR` (line 93 semantic correction 1→2 documented as intended).
- `src/claude_i/deps.py` — G9: REPLACED `assert_not_windows()` stub (single definition at line 128). Strict `sys.platform == "win32"` check (WSL2 reports `"linux"`, correctly bypasses). Verbatim AC-5 message text. `sys.exit(PLATFORM_ERROR)`. Called as first action in `check_deps()`. Existing `sys.exit(2)` calls at lines 111/117 migrated to `CONFIG_ERROR` constant.
- `src/claude_i/cli.py` — `--allow-empty` flag; `ExitCode` import; try/except wraps `runner.run()` to catch `RuntimeError` and `TimeoutError` → exit 1. `--help` epilog extended to 4 codes (0/1/2/3). SIGKILL best-effort note added per AC-2.
- `tests/test_reaper.py` (NEW) — atexit + SIGTERM cleanup + `reap_orphans` tests.
- `tests/test_runner.py`, `test_hook.py`, `test_deps.py`, `test_cli.py` — EXTENDED. 30 → 68 tests (38 new for 001.2).
- `pyproject.toml` — added ruff `S306` (suspicious-mktemp-usage) to `[tool.ruff.lint.select]` — actively prevents mktemp regression (verified to flag on test reintroduction).

**Patterns established:**
- **`exit_codes` as separate module, not in `cli.py`**: avoids circular import when downstream modules (`deps.py`, `hook.py`, `runner.py`, `reaper.py`) need to consume exit codes. Future stories adding subcommands should import from `claude_i.exit_codes`, not redefine.
- **String-form `sys.exit(message)` is an antipattern**: it exits with code 1 implicitly. Always use `print(message, file=sys.stderr); sys.exit(EXIT_CODE_CONSTANT)`. Migration applied at 4 call sites in this story.
- **G4 two-layer contract (delivery via shell prefix + isolation via env strip) survives refactoring**: 4 runner.py edits in this story (G5 + G6 + G8 + G13) and the test pair still passes. The contract is genuinely load-bearing; future stories touching `runner.py` must keep both layers.
- **AC-7 four-branch parse-failure pattern**: `runner.run()` must distinguish (1) verified-empty assistant turn (return `""`) from (2) no-assistant-message (RuntimeError) from (3) payload-missing (RuntimeError) from (4) transcript-missing (RuntimeError). `cli.py` catches RuntimeError → exit 1; empty string → exit 0 only with `--allow-empty`. Fake-success returns are eliminated — no more strings that print like success but signal failure.
- **`fcntl.flock` deadline-based retry (5s, 100ms sleep)**: better than blocking acquire because it gives a deterministic timeout with a useful error message. Pattern reusable for any future file-locking need.
- **`atexit` + `SIGTERM` handler is belt-and-braces with existing `finally` cleanup**: triple coverage (normal exit + KeyboardInterrupt + SIGTERM via signal handler → sys.exit → atexit). SIGKILL still uncoverable (documented in `--help`).
- **Stub-vs-replace discipline**: when an earlier story leaves a stub function (`reaper.register_cleanup`, `deps.assert_not_windows`), the later story REPLACES the body and verifies single definition via `grep -n "def <name>"`. Never add a duplicate function.

**Key decisions:**
1. **G8 — `exit_codes.py` separate module, not constants in `cli.py`**: avoids circular import when `deps.py`/`hook.py`/`runner.py`/`reaper.py` all need to consume exit codes. `cli.py` would have been imported by every module → circular. Module docstring documents rationale.
2. **G7 — lock file sibling (`claude-i.lock`), not lock on `settings.json` directly**: safer because Claude Code itself writes to `settings.json` and `claude-i`'s `fcntl.flock` is advisory (does not prevent Claude Code's own writes). Lock file is exclusive to `claude-i` invocations.
3. **G8 — RuntimeError uniformly across 4 branches, `cli.py` catches and routes to exit 1**: chosen over per-branch exit-code differentiation because the operator just needs to know "claude-i failed" with a descriptive message; finer-grained codes are 001.5's `doctor` subcommand domain.
4. **G9 — strict `sys.platform == "win32"`, not `startswith("win")`**: WSL2 reports `"linux"`, so the strict check correctly allows WSL2 while blocking native Windows. The current stub (from 001.0) used `startswith("win")` which had the same effect but is less precise.
5. **G13 — best-effort encoding (warn-and-continue), not fail-hard**: a user with an ASCII locale running a Unicode prompt should not have `claude-i` crash; the warning surfaces the issue without blocking work. AC-6 mandates this behavior.
6. **CodeRabbit SKIPPED per operator instruction**: ("Skip CodeRabbit. Re-run gates independently in fresh venv."). Compensating gates: ruff + mypy strict + pytest in a fresh Python 3.14.3 venv. All independent gates green.

**Tech debt identified:**
- **NOTES.md G14/G17 carryover documentation** (LOW): currently only in this story's Dev Agent Record + Closure. 001.1 convention puts deferrals in NOTES.md. Suggested owner: @dev, pick up at start of 001.5.
- **`reaper.py:74` bare `sys.exit(1)` in `_sigterm_handler`** (LOW, cosmetic): should be `sys.exit(RUNTIME_ERROR)` for consistency with G8 convention. Functionally identical. Suggested owner: @dev, migrate during 001.5 reap-subcommand work.

**Tests:** 68 / 68 pass (30 pre-existing regression intact + 38 new for 001.2). 5.4 tests per AC avg. **Deploy:** N/A (`deploy_type: none`). **CodeRabbit:** 0 iter (skipped per operator; compensating gates green in fresh venv).

---

*Epic v0.4 | Status: In Progress (3/6 Done, 50.0%) | Next step: STORY-001.3 — PyPI packaging (build, OIDC publish, `pipx`/`uv tool` validation, `--version`)*
