# EPIC-001: Packaging and Hardening

| Field | Value |
|---|---|
| **ID** | EPIC-001 |
| **Title** | Packaging and Hardening for `claude-i` |
| **Status** | Draft |
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
| STORY-001.0 | Bootstrap: package skeleton, pyproject, CI, pytest, seed refactor | Draft | — | G18 (scaffold) | 5 pts (~2 days) |
| STORY-001.1 | Critical hardening: permission-mode, hook scoping, dep check, env var hygiene | Draft | STORY-001.0 | G1, G2, G3, G4, G12 (partial) | 5 pts (~2 days) |
| STORY-001.2 | Important hardening: tempfile, reaper, flock, exit codes, platform guard, encoding | Draft | STORY-001.0, STORY-001.1 | G5, G6, G7, G8, G9, G13 | 5 pts (~2 days) |
| STORY-001.3 | PyPI packaging: build, publish (OIDC), `pipx` + `uv tool` validation, `--version` | Draft | STORY-001.0, STORY-001.1, STORY-001.2 | — (distribution) | 3 pts (~1 day) |
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

---

*Epic v0.1 | Status: Draft | Next step: handoff to @sm to draft STORY-001.0*
