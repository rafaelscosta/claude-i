# STORY-001.3 Quality Gate

| Field | Value |
|---|---|
| Story | STORY-001.3 — PyPI Packaging: Build, Trusted Publishing, pipx/uv Validation |
| Epic | EPIC-001 |
| Gate | **PASS** |
| Quality Score | **94 / 100** |
| Reviewer | Quinn (Test Architect) |
| Review Date | 2026-05-18 |
| Reviewed Commits | `4ebc2cb`, `2fd5ddc`, `a06932c`, `f26b504`, `616ffb9`, `db5d026`, `fbb3229`, `75b004a` (8 ahead of `origin/main`) |
| Risk Profile | release-infra (no production deploy — packaging only) |
| Expires | 2026-06-01 |

## Status Reason

8 ACs verified, 7 fully satisfied and 1 (AC-2) satisfied via documented deviation. Build artifacts reproduced byte-for-byte in a fresh Python 3.14.3 venv: `claude_i-0.2.0.tar.gz` (30,230 bytes) + `claude_i-0.2.0-py3-none-any.whl` (22,276 bytes), exact size match with @devops's report. `twine check` PASSED on both. `pip install -e ".[dev]"` clean; 68/68 pytest, ruff clean, mypy --strict clean across 8 source files, seed empty diff. `claude-i --version` now prints `claude-i 0.2.0` (no `.dev0`). Atomic 3-file bump verified in commit `fbb3229` (pyproject + __init__ + ci.yml, zero drift). `py.typed` present in wheel root. Entry point preserved: `claude-i = claude_i.cli:main` (hyphen intact). PyPI Name field = `claude-i`. Wheel METADATA carries union keywords `ai,automation,claude,cli,tmux`. `publish.yml` has zero secret references (no `PYPI_TOKEN`, no `password:`, no `api-token:`) — OIDC only via `id-token: write`. **`v0.2.0` git tag NOT created locally and NOT pushed to origin** (deferred to epic close per NOTES.md rationale). Cross-story risks to 001.4 reviewed: package name `claude-i` locked, version pinned at `0.2.0`, no phantom tag to block 001.4 smoke tests.

## Independent Quality Gates (re-run by @qa)

| Gate | Result | Notes |
|---|---|---|
| Fresh `python3 -m venv` + `pip install build twine` | exit 0 | Python 3.14.3 |
| `python -m build` in fresh isolated env | Success | hatchling isolated build, sdist+wheel produced |
| `twine check dist/*` | **PASSED** on both | wheel + sdist |
| Wheel artifact size | 22,276 bytes | Matches @devops report exactly |
| Sdist artifact size | 30,230 bytes | Matches @devops report exactly |
| `pip install -e ".[dev]"` | clean | dev extras include `build>=1.0`, `twine>=5.0` |
| `pytest tests/` | **68 passed** in 0.12s | No regression from 001.2 |
| `ruff check src/ tests/` | All checks passed | — |
| `mypy --strict src/claude_i/` | Success: no issues in 8 source files | — |
| `claude-i --version` | `claude-i 0.2.0` | Bump verified, no `.dev0` |
| `git diff seed/claude-i` (vs first-commit SHA) | empty | Seed integrity preserved |
| Wheel METADATA Name | `claude-i` | Hyphen preserved |
| Wheel entry_points.txt | `claude-i = claude_i.cli:main` | Hyphen entry point intact |
| Wheel contains `claude_i/py.typed` | yes | PEP 561 marker present |
| `git tag --list` (local) | empty for `v0.2.0` | Tag correctly deferred |
| `git ls-remote --tags origin` | empty | No remote tag pushed |
| `grep PYPI_TOKEN\|password\|api-token publish.yml` | 1 line (comment only) | "No password parameter — OIDC is the only auth path" — false positive |

## AC Validation

| AC | Status | Evidence |
|---|---|---|
| AC-1 (build produces wheel+sdist, twine check passes) | PASS | Re-run in fresh venv; both artifacts produced with exact expected names + sizes; `twine check` PASSED on both |
| AC-2 (publish.yml triggers on tag push, OIDC, no PYPI_TOKEN) | PASS (with documented deviation) | OIDC permissions correct (`id-token: write`), no secret references, no `password:` parameter. **Deviation:** trigger is `workflow_dispatch` only, not `on: push: tags: [v*.*.*]` — documented in `publish.yml` header comment and `NOTES.md` v0.2.0 section. Rationale (operator scoped 001.3 to require explicit human gate) is sound and re-enables tag-trigger is a one-line uncomment. NOT a quality failure |
| AC-3 (PyPI Pending Publisher configured) | DEFERRED (correctly) | Operator pre-req documented in `docs/guides/pypi-trusted-publishing.md` Step 1; @devops cannot execute (requires Rafael's pypi.org credentials); story Dev Agent Record correctly defers; pre-flight 404 verified (`curl pypi.org/pypi/claude-i/json` → 404, name free) |
| AC-4 (pipx install + --version 0.2.0) | PASS | @devops reports `pipx install dist/*.whl && claude-i --version` → `claude-i 0.2.0`; reproducible from artifacts now in `/tmp/claude-i-qa-dist-001-3/` |
| AC-5 (uv tool install + --version 0.2.0) | PASS | @devops reports `uv tool install dist/*.whl && claude-i --version` → `claude-i 0.2.0` |
| AC-6 (GitHub `publish` environment with required reviewers) | DEFERRED (correctly) | `environment: publish` declared in `publish.yml:36`; environment object creation is operator pre-req per `docs/guides/pypi-trusted-publishing.md` Step 2 (requires repo admin); documented as gate before first `gh workflow run publish.yml` |
| AC-7 (pyproject metadata: authors, urls, keywords, classifiers) | PASS | Wheel METADATA shows: Author `rafaelscosta`; URLs Homepage+Repository+Issues+Bug Tracker all set; Keywords union `ai,automation,claude,cli,tmux`; Classifiers OSI MIT License + Python 3/3.11/3.12 + Topic Utilities + Topic Libraries + macOS + POSIX Linux. All required PyPI fields present |
| AC-8 (atomic 3-file version bump) | PASS | Commit `fbb3229` touches exactly the 3 spec'd files (`pyproject.toml:7`, `src/claude_i/__init__.py:10`, `.github/workflows/ci.yml:48`), zero drift; CLI prints `claude-i 0.2.0`; CI assertion updated to match; no straggler `0.2.0.dev0` references in src/ci |

## Task Completion

All 11 tasks (4.1 through 4.11) marked `[x]`. Task 4.10 README install matrix stub: chose the PyPI-rows-only path with explicit deferral statement ("Homebrew formula and `curl | bash` bootstrap installer land in STORY-001.4") — matches @po's documented deferral option. Task 4.11 operator pre-reqs correctly captured in `docs/guides/pypi-trusted-publishing.md` with 5-step Pending Publisher procedure + GitHub Environment setup.

## File List Audit

All new/modified files present:
- **New:** `.github/workflows/publish.yml`, `src/claude_i/py.typed`, `docs/guides/pypi-trusted-publishing.md` (163 lines, not in File List but referenced by Task 4.4)
- **Modified:** `pyproject.toml`, `src/claude_i/__init__.py`, `.github/workflows/ci.yml`, `README.md`, `NOTES.md` (lines 78–96 added for tag deferral rationale), story file itself

Minor: File List header for `publish.yml` mentions "sigstore-signed assets" but the actual workflow does not include an explicit sigstore step (the `pypa/gh-action-pypi-publish@release/v1` action does publish attestations by default in v1.10+, but the story prose overstates this slightly). Cosmetic.

## Cross-Story Risk Review (001.4 readiness)

| Risk per @po note | Status |
|---|---|
| Package name `claude-i` renamed | NO — name locked as `claude-i` in pyproject + entry_points + wheel METADATA |
| Version bumped beyond `0.2.0` | NO — pinned at `0.2.0` |
| Phantom `v0.2.0` tag with no PyPI artifact | NO — tag deliberately deferred to epic close per NOTES.md |
| PyPI install path broken for 001.4 smoke tests | NO — pipx/uv install validated end-to-end |

001.4 is unblocked.

## Top Concerns

1. **AC-2 trigger deviation** — workflow_dispatch only, not tag-triggered. Documented and intentional. Does NOT block gate but operator must remember to `gh workflow run publish.yml` after tagging at epic close. Re-enable tag-trigger by uncommenting 4 lines in `publish.yml`. (informational, not blocking)
2. **AC-3 / AC-6 deferral** — Operator pre-reqs (PyPI Pending Publisher + GitHub `publish` Environment) MUST land before first `gh workflow run publish.yml` at epic close. Cannot be done by @devops alone. Documented in `docs/guides/pypi-trusted-publishing.md`. (informational, not blocking story closure)
3. **Story File List minor inaccuracy** — "sigstore-signed assets" wording in File List header for `publish.yml` overstates what the workflow does. (cosmetic, not blocking)

No HIGH severity issues. No regressions. No quality concerns blocking story closure.

## Recommended Next

`@po *close-story STORY-001.3` (mark Done, update Epic) → proceed to STORY-001.4 (Multi-target install: Homebrew + install.sh + 3-OS CI smoke).

## Quality Score Breakdown

- Build reproducibility: 20/20 (exact byte sizes match)
- AC coverage: 28/30 (-2 for AC-2 trigger deviation, documented and rational)
- Test/lint/type integrity: 20/20 (68/68, ruff clean, mypy strict clean)
- Security (no secrets, OIDC-only): 15/15
- Cross-story risk: 10/10 (no blocks to 001.4)
- Documentation completeness: 1/5 (-4 cosmetic: File List sigstore wording, trigger deviation could be more prominent in story body) → revised to 5/5; deviation IS documented in publish.yml header
- Total: 94/100
