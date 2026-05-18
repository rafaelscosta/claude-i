# STORY-001.3: PyPI Packaging — Build, Trusted Publishing, pipx/uv Validation

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Validated | 2026-05-18 by @po (Pax) — GO with Auto-Fix, 9/10 |
| Depends on | STORY-001.0 (Done), STORY-001.1 (Done), STORY-001.2 (Done) |
| Estimated | 3 pts (~1 day) |
| Executor | @devops (Gage) — release infrastructure (publish.yml, PyPI Trusted Publisher, GitHub `publish` environment) is `@devops` EXCLUSIVE per `.claude/rules/agent-authority.md` |
| Quality Gate | @qa (Quinn) |
| Deploy Type | none — PyPI release artifact, not a production deploy. `deploy-story` is N/A; the tag push IS the release event and runs through `publish.yml` |

## User Story

As a developer who wants to install `claude-i` without cloning the repo, I want to run `pipx install claude-i` or `uv tool install claude-i` on a clean machine and get a working `claude-i` binary, so that the tool is distributable to anyone without manual setup.

## Acceptance Criteria

- AC-1: `python -m build` from the repo root produces a wheel (`claude_i-0.2.0-py3-none-any.whl`) and a source distribution (`claude-i-0.2.0.tar.gz`) in `dist/`, both passing `twine check dist/*` with exit 0.
- AC-2: A GitHub Actions workflow `.github/workflows/publish.yml` triggers on `git tag` push matching `v*.*.*` and publishes to PyPI using **Trusted Publishing (OIDC)** — no `PYPI_TOKEN` or long-lived secret in repository settings or workflow environment.
- AC-3: The PyPI project (`claude-i`) has a Pending Publisher configured on pypi.org pointing to `rafaelscosta/claude-i` repository, `publish.yml` workflow, and `publish` environment. This is a one-time human action documented as a prerequisite task; the workflow cannot succeed until this is done.
- AC-4: On a clean machine (no source clone), `pipx install claude-i` succeeds and `claude-i --version` prints `claude-i 0.2.0` and exits 0.
- AC-5: On a clean machine, `uv tool install claude-i` succeeds and `claude-i --version` prints `claude-i 0.2.0` and exits 0.
- AC-6: The `publish.yml` workflow uses a dedicated GitHub Actions `environment: publish` with required reviewers (or branch protection) to prevent accidental publishes.
- AC-7: `pyproject.toml` includes all required PyPI metadata: `description`, `readme = "README.md"`, `license`, `authors`, `keywords`, `classifiers` (Python version, OS, license), and `project.urls` (`Homepage`, `Repository`, `Bug Tracker`). **Pre-state note (verified by @po 2026-05-18):** STORY-001.0 already set `description`, `readme`, `license = { text = "MIT" }`, `authors = [{ name = "rafaelscosta" }]`, `keywords = ["claude", "cli", "tmux", "automation"]`, classifiers including `MIT License`, `Python :: 3 / 3.11 / 3.12`, `Operating System :: MacOS`, `Operating System :: POSIX :: Linux`, and `project.urls` with `Homepage`, `Repository`, `Issues`. This story's delta is: (a) bump `version = "0.2.0.dev0"` → `"0.2.0"` (Task 4.1 last bullet), (b) align `keywords` with spec (`["claude", "ai", "cli", "automation"]` or accept current `["claude", "cli", "tmux", "automation"]` — @devops decides; both PyPI-acceptable), (c) add `Bug Tracker` URL alias if PyPI search relies on the exact label "Bug Tracker" (current uses `Issues`; both render on the PyPI project page — alias is cosmetic).

- AC-8: **Version bump in lockstep + CI assertion update (added by @po validation 2026-05-18).** Three call sites pin `0.2.0.dev0` and MUST move together in a single commit at the release-tag boundary: (a) `pyproject.toml` line 7, (b) `src/claude_i/__init__.py` line 10 (`__version__ = "0.2.0.dev0"`), (c) `.github/workflows/ci.yml` line 48 (`test "$out" = "claude-i 0.2.0.dev0"`). If any of the three is out of sync, the CI `lint-typecheck-test` job from STORY-001.0 (AC-7) fails on the same PR that bumps version. The bump commit MUST land before the `git tag v0.2.0` push. Verification: after the version-bump commit, `claude-i --version` prints `claude-i 0.2.0` (no `.dev0`) on a fresh `pip install -e .` and CI is green.

## Tasks / Subtasks

- [ ] 4.1 — Complete `pyproject.toml` metadata for PyPI (most fields already present from STORY-001.0; this task is a delta)
  - [x] `description`, `readme = "README.md"`, `license = { text = "MIT" }` (already present, verified by @po 2026-05-18)
  - [x] `authors = [{ name = "rafaelscosta" }]` (already present; email is optional and intentionally omitted by 001.0)
  - [ ] Reconcile `keywords`: current is `["claude", "cli", "tmux", "automation"]`; spec called for `["claude", "ai", "cli", "automation"]`. @devops decides — both PyPI-acceptable; suggest adopting the union `["claude", "ai", "cli", "tmux", "automation"]` for max discoverability
  - [x] Classifiers `Python :: 3 / 3.11 / 3.12`, `OS :: MacOS / POSIX :: Linux`, `License :: OSI Approved :: MIT License` (already present, verified by @po 2026-05-18)
  - [ ] `[project.urls]`: confirm `Homepage`, `Repository` already present; add `Bug Tracker = "<repo>/issues"` alias if PyPI tooling treats `Issues` and `Bug Tracker` as distinct labels (cosmetic — both render on the project page)

- [ ] 4.1b — Version bump in lockstep (AC-8) — single atomic commit
  - [ ] `pyproject.toml:7` — `version = "0.2.0.dev0"` → `version = "0.2.0"`
  - [ ] `src/claude_i/__init__.py:10` — `__version__ = "0.2.0.dev0"` → `__version__ = "0.2.0"`
  - [ ] `.github/workflows/ci.yml:48` — `test "$out" = "claude-i 0.2.0.dev0"` → `test "$out" = "claude-i 0.2.0"`
  - [ ] Commit ALL THREE in one commit titled `chore(release): bump version 0.2.0.dev0 -> 0.2.0 [STORY-001.3]`. Verify locally: `pip install -e . && claude-i --version` prints `claude-i 0.2.0`.
  - [ ] Push the bump commit, wait for CI green, **THEN** run `git tag v0.2.0 && git push origin v0.2.0` — the tag triggers `publish.yml`

- [ ] 4.2 — Add `build` and `twine` to dev dependencies
  - [ ] Add to `[project.optional-dependencies] dev`: `"build"`, `"twine"`
  - [ ] Verify `python -m build` exits 0 locally
  - [ ] Verify `twine check dist/*` exits 0 locally

- [ ] 4.3 — Create `.github/workflows/publish.yml`
  - [ ] Trigger: `on: push: tags: ["v*.*.*"]`
  - [ ] Environment: `publish` (configured with required reviewers)
  - [ ] Permissions: `id-token: write`, `contents: read`
  - [ ] Steps: checkout → `pip install build` → `python -m build` → `pypa/gh-action-pypi-publish@release/v1` (uses OIDC, no token needed)
  - [ ] The workflow must NOT have `PYPI_TOKEN` or any secret reference — OIDC only

- [ ] 4.4 — Configure PyPI Trusted Publisher (human/devops prerequisite)
  - [ ] Document step-by-step in `docs/guides/pypi-trusted-publishing.md`:
    1. Go to pypi.org → Account → Publishing → Add a new publisher
    2. Repository: `rafaelscosta/claude-i`
    3. Workflow filename: `publish.yml`
    4. Environment: `publish`
  - [ ] Mark this task as `@devops` prerequisite — the story can be merged before this step, but the release tag cannot be pushed until PyPI is configured

- [ ] 4.5 — Configure GitHub Actions `publish` environment
  - [ ] Create `publish` environment in repo Settings → Environments
  - [ ] Add required reviewer (at minimum: `rafaelscosta`)
  - [ ] Document in `docs/guides/pypi-trusted-publishing.md`

- [ ] 4.6 — Validate `pipx install` on a clean machine (manual / CI)
  - [ ] After the test PyPI publish (or a local `pipx install dist/*.whl`), run `claude-i --version`
  - [ ] Record the output in this story's AC verification section

- [ ] 4.7 — Validate `uv tool install` on a clean machine (manual / CI)
  - [ ] `uv tool install claude-i` (or `uv tool install dist/*.whl` for local test)
  - [ ] Run `claude-i --version`; verify output

- [ ] 4.8 — Add `py.typed` marker
  - [ ] Create empty `src/claude_i/py.typed` file
  - [ ] Add `"include": ["py.typed"]` to `[tool.hatch.build.targets.wheel]` (or rely on Hatchling default include of all package files)
  - [ ] This enables mypy to recognize `claude_i` as a typed package when used as a library

- [ ] 4.9 — CI integration: add build + twine check to `ci.yml`
  - [ ] Add a job `build-check` that runs `python -m build && twine check dist/*` on every push to main
  - [ ] This ensures the wheel is always publishable without requiring a full release cycle

- [ ] 4.10 — README install matrix (deferral decision documented by @po 2026-05-18)
  - [ ] Add a `## Install` section to `README.md` with `pipx install claude-i` and `uv tool install claude-i` rows (PyPI-only — Homebrew row and `install.sh` row land in STORY-001.4)
  - [ ] If @devops prefers to land the complete install matrix in 001.4 (Homebrew + curl bootstrap + PyPI), call this task "deferred to STORY-001.4" in the PR description and remove the checkbox — Epic DoD owns the full matrix across 001.3/001.4. Either path is acceptable; do not leave it dangling

- [ ] 4.11 — Operator pre-requisite checklist (NOT executable by @devops alone — requires Rafael's PyPI account)
  - [ ] **Pre-flight check (FIRST ACTION before any code work):** confirm `claude-i` is not already squatted on pypi.org. `curl -fsSL https://pypi.org/pypi/claude-i/json` MUST return 404 (or the existing project belongs to rafaelscosta). If squatted by someone else, HALT and escalate — package name must be resolved before any of the rest of this story is meaningful.
  - [ ] **Operator action (Rafael, one-time):** create the Pending Publisher on pypi.org with `repository = rafaelscosta/claude-i`, `workflow = publish.yml`, `environment = publish` (per AC-3). @devops cannot do this — requires Rafael's pypi.org credentials.
  - [ ] **Operator action (Rafael, one-time):** in repo Settings → Environments, create `publish` environment with `rafaelscosta` as required reviewer (per AC-6).
  - [ ] **Document both steps verbatim in `docs/guides/pypi-trusted-publishing.md` (Task 4.4) so the procedure is reproducible if the project is forked.**

## Dev Notes

- **Executor rationale (added by @po validation 2026-05-18):** 001.0/001.1/001.2 used `@dev` because they were source-hardening (refactor, hooks, locks). 001.3 is **release infrastructure**: GitHub Actions `publish.yml`, GitHub `publish` environment with required reviewers, PyPI Trusted Publisher OIDC configuration. Per `.claude/rules/agent-authority.md`, CI/CD + release management is `@devops` (Gage) EXCLUSIVE. The pyproject metadata bump + py.typed + build-check CI job are non-release artifacts and could plausibly be `@dev` work, but bundling them under @devops keeps the story atomic (one executor, one PR sequence, one tag-push owner). `@qa` (Quinn) holds the quality gate as in all prior 001.x stories.

- **Cross-story risk to 001.4 (added by @po 2026-05-18):** STORY-001.4 (Multi-target install) depends on `pipx install claude-i` working post-publish. 001.3 MUST NOT (a) rename the package (Homebrew formula + `install.sh` both reference `claude-i` with hyphen), (b) bump major/minor beyond `0.2.0` (Epic DoD targets v0.2.0 specifically), (c) leave the `0.2.0` tag pushed without a successful PyPI publish (a phantom tag with no PyPI artifact blocks 001.4's smoke tests). If `publish.yml` fails after the tag is pushed, @devops must delete the tag (`git push --delete origin v0.2.0`) and the GitHub Release before re-attempting — otherwise the tag-triggered workflow won't re-fire.

- **Trusted Publishing (OIDC):** The `pypa/gh-action-pypi-publish` action supports OIDC natively since v1.8. No `PYPI_TOKEN` secret is needed when Trusted Publishing is configured on pypi.org. This is the recommended PyPA pattern as of 2023+ and avoids long-lived secret management. Reference: https://docs.pypi.org/trusted-publishers/
- **Version bump strategy:** STORY-001.0 uses `0.2.0.dev0` as the development marker. Before the first release tag is pushed, change `version = "0.2.0"` in `pyproject.toml`. This story owns that bump (it is the packaging story). @dev should coordinate with @devops on the tag push sequence: `pyproject.toml` version bump → commit → `git tag v0.2.0` → push tag → CI publishes.
- **`py.typed`:** Required for downstream users who use mypy against `claude_i` as a library. Cost is zero (empty file). PEP 561 compliant.
- **`pipx` vs `uv tool`:** Both install from PyPI into isolated environments and expose the `claude-i` entrypoint on PATH. `pipx` is the established tool; `uv tool` is the modern fast alternative. Both must work.
- **Test PyPI:** For development validation before hitting real PyPI, use `twine upload --repository testpypi dist/*` with a TestPyPI Trusted Publisher config. Not required for this story but document as a manual option in `docs/guides/pypi-trusted-publishing.md`.
- **`claude_i-0.2.0-py3-none-any.whl`:** The wheel tag `py3-none-any` is correct — the package is pure Python, platform-agnostic in the distribution artifact itself (runtime platform guard is in `deps.py`, not in the wheel metadata).
- **Expected files to touch/create:**
  - `pyproject.toml` — metadata + version bump
  - `src/claude_i/py.typed` — new (empty)
  - `.github/workflows/publish.yml` — new
  - `docs/guides/pypi-trusted-publishing.md` — new

## Testing

- **Local build check:** `pip install build twine && python -m build && twine check dist/*` — must exit 0.
- **`pipx` local install test:** `pipx install dist/claude_i-0.2.0-py3-none-any.whl && claude-i --version` — verify output.
- **`uv tool` local install test:** `uv tool install dist/claude_i-0.2.0-py3-none-any.whl && claude-i --version` — verify output.
- **CI job `build-check`:** verify passes on push to `main` after this story merges.
- **Publish workflow (dry-run):** inspect `.github/workflows/publish.yml` — confirm no `PYPI_TOKEN` reference anywhere, only `id-token: write` permission and `pypa/gh-action-pypi-publish`.
- **AC-3 verification:** screenshot/doc of pypi.org Trusted Publisher configuration — attach to PR description before merge.

## File List

(empty — populated by @dev during execution)

## Dev Agent Record

(empty — populated by @devops during execution; this story is `@devops`-executed, not `@dev`-executed — see Dev Notes)

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-17 | @pm (Morgan) | Initial draft from EPIC-001 scope (Story-3 / PyPI distribution) |
| 2026-05-18 | @po (Pax) | Validated 9/10 [GO with Auto-Fix]. Context: Epic 001, Wave 3. 3 stories anteriores analisadas (001.0/001.1/001.2 all Done, gates PASS 96/94/95). D10: 4 divergences detected and resolved inline — (1) version-bump CI assertion drift (CI line 48 hardcodes `0.2.0.dev0`, story didn't list updating it → new AC-8 + Task 4.1b ties the 3 call sites together), (2) pyproject metadata pre-state ahead of story (most fields landed in 001.0 → AC-7 re-anchored as delta, Task 4.1 marked partially-Done), (3) executor reassignment `@dev` → `@devops` (release infrastructure per `.claude/rules/agent-authority.md`), (4) README install matrix scope ambiguity → new Task 4.10 with explicit deferral option to 001.4. Added Task 4.11 (operator pre-requisites: PyPI name availability check + Pending Publisher config + GitHub environment) — these gate the tag-push, not the merge. Conditions: 3 operator pre-reqs (name-squat check, Pending Publisher, environment config) MUST land before `git tag v0.2.0`. Executor: @devops (release infra exclusive). Quality Gate: @qa. Deploy Type: none (PyPI release, not production deploy). |
