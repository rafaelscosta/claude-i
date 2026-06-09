# STORY-001.9: Release Surface Sync for v0.2.3

| Field | Value |
|---|---|
| Status | Done |
| Epic | EPIC-001 maintenance |
| Owner | @dev (Dex) |
| Executor | @dev |
| Quality Gate | @qa |
| Accountable | rafaelscosta |
| deploy_type | none |
| Created | 2026-06-09 |
| Estimated | 1 pt |

## User Story

As the maintainer of `claude-i`, I want public release instructions, operator notes, and publishing workflow copy to match the actual `v0.2.3` state, so users and future agents do not resume from stale `v0.2.0`/`v0.2.2` release assumptions or the reversed private-repo policy.

## Context

Live GitHub state confirms:

- Repository `rafaelscosta/claude-i` is public.
- Latest release is `v0.2.3`.
- Homebrew formula points at the `v0.2.3` GitHub Release sdist.
- PyPI package endpoint still returns 404, so PyPI remains pending Trusted Publisher setup.

## Acceptance Criteria

- **AC-1:** `README.md` status, install examples, checksums, verify command, and distribution table reference `v0.2.3`.
- **AC-2:** `.github/workflows/publish.yml` no longer claims the repo is permanently private or PyPI-forbidden; it preserves the manual confirmation guard.
- **AC-3:** `NOTES.md` public-release section documents `v0.2.3` as the current public release and keeps PyPI pending instructions current.
- **AC-4:** Operational guides for Homebrew and PyPI publish no longer direct operators through the obsolete `v0.2.0` epic-close path as the active path.
- **AC-5:** Historical story/changelog records remain unchanged unless they are current operational docs.
- **AC-6:** Local validation passes: unit suite, ruff, mypy, build, twine check, `claude-i --version`, and `claude-i doctor --json`.

## Tasks / Subtasks

- [x] 10.1 Update public install/readme surface.
- [x] 10.2 Update operator notes and publish workflow copy.
- [x] 10.3 Update Homebrew/PyPI guides to the current `v0.2.3` state.
- [x] 10.4 Run validation commands and close the story.

## File List

**Planned modified:**

- `README.md`
- `NOTES.md`
- `.github/workflows/publish.yml`
- `docs/guides/homebrew-tap.md`
- `docs/guides/pypi-trusted-publishing.md`
- `docs/stories/STORY-001.9-release-surface-sync.md`
- `docs/gates/STORY-001.9-gate.md`

## Dev Notes

- Use the GitHub Release asset digest for the wheel checksum. Local wheel rebuilds are not byte-identical, but the published sdist checksum matches the Homebrew formula.
- Keep the `confirm_release=I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE` guard: it is procedural safety, not a private-repo policy.

## Dev Agent Record

### Implementation Summary

- README now points at `v0.2.3` release assets, version check, and published artifact checksums.
- NOTES public-release section now names `v0.2.3` as the current release and keeps PyPI pending instructions current.
- `publish.yml` now describes public-release status while preserving the manual confirmation guard.
- Homebrew and PyPI guides now describe the current GitHub Release sdist source and optional future PyPI flip instead of the obsolete `v0.2.0` epic-close path.

### Release Evidence

- GitHub Release `v0.2.3` assets:
  - wheel digest: `sha256:05779011d0869373422019d4595d1bb25d218cfa008117fe0aab1fe8929dbc69`
  - sdist digest: `sha256:ba7d4f6fcf7608c8681c0bfa2f14fd47c992f705d1211350988ebc967838513c`
- Homebrew formula sdist SHA matches the `v0.2.3` GitHub Release sdist.
- PyPI `claude-i` endpoint still returns 404, so PyPI remains pending.

### Validation

- `rg` release-surface scan: no obsolete `0.2.0`/`0.2.2` active operational references remain in README, publish workflow, or current guides.
- Full local validation recorded in `docs/gates/STORY-001.9-gate.md`.
