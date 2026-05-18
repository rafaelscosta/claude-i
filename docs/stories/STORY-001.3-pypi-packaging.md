# STORY-001.3: PyPI Packaging — Build, Trusted Publishing, pipx/uv Validation

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Depends on | STORY-001.0, STORY-001.1, STORY-001.2 |
| Estimated | 3 pts (~1 day) |

## User Story

As a developer who wants to install `claude-i` without cloning the repo, I want to run `pipx install claude-i` or `uv tool install claude-i` on a clean machine and get a working `claude-i` binary, so that the tool is distributable to anyone without manual setup.

## Acceptance Criteria

- AC-1: `python -m build` from the repo root produces a wheel (`claude_i-0.2.0-py3-none-any.whl`) and a source distribution (`claude-i-0.2.0.tar.gz`) in `dist/`, both passing `twine check dist/*` with exit 0.
- AC-2: A GitHub Actions workflow `.github/workflows/publish.yml` triggers on `git tag` push matching `v*.*.*` and publishes to PyPI using **Trusted Publishing (OIDC)** — no `PYPI_TOKEN` or long-lived secret in repository settings or workflow environment.
- AC-3: The PyPI project (`claude-i`) has a Pending Publisher configured on pypi.org pointing to `rafaelscosta/claude-i` repository, `publish.yml` workflow, and `publish` environment. This is a one-time human action documented as a prerequisite task; the workflow cannot succeed until this is done.
- AC-4: On a clean machine (no source clone), `pipx install claude-i` succeeds and `claude-i --version` prints `claude-i 0.2.0` and exits 0.
- AC-5: On a clean machine, `uv tool install claude-i` succeeds and `claude-i --version` prints `claude-i 0.2.0` and exits 0.
- AC-6: The `publish.yml` workflow uses a dedicated GitHub Actions `environment: publish` with required reviewers (or branch protection) to prevent accidental publishes.
- AC-7: `pyproject.toml` includes all required PyPI metadata: `description`, `readme = "README.md"`, `license`, `authors`, `keywords`, `classifiers` (Python version, OS, license), and `project.urls` (`Homepage`, `Repository`, `Bug Tracker`).

## Tasks / Subtasks

- [ ] 4.1 — Complete `pyproject.toml` metadata for PyPI
  - [ ] Add `description`, `readme = "README.md"`, `license = {text = "MIT"}` (or repo license)
  - [ ] Add `authors = [{name = "...", email = "..."}]`
  - [ ] Add `keywords = ["claude", "ai", "cli", "automation"]`
  - [ ] Add classifiers: `"Programming Language :: Python :: 3"`, `"Programming Language :: Python :: 3.11"`, `"Programming Language :: Python :: 3.12"`, `"Operating System :: POSIX"`, `"License :: OSI Approved :: MIT License"`
  - [ ] Add `[project.urls]`: `Homepage`, `Repository`, `Bug Tracker`
  - [ ] Bump `version = "0.2.0"` (remove `.dev0` pre-release marker for the release tag)

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

## Dev Notes

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

(empty — populated by @dev)
