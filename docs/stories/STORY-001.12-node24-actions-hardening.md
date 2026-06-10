# STORY-001.12: GitHub Actions Node 24 Hardening

| Field | Value |
|---|---|
| Status | Done |
| Epic | EPIC-001 maintenance |
| Owner | @devops (Gage) |
| Executor | @devops |
| Quality Gate | @qa |
| Accountable | rafaelscosta |
| deploy_type | none |
| Created | 2026-06-10 |
| Estimated | 1 pt |

## User Story

As an operator maintaining `claude-i` release infrastructure, I want GitHub
Actions workflows to use Node 24-compatible official actions, so CI, smoke,
and publish jobs do not carry a dated Node.js 20 deprecation warning into the
next release cycle.

## Context

Post-merge checks for STORY-001.10 and STORY-001.11 passed, but GitHub Actions
annotated jobs using `actions/checkout@v4` and `actions/setup-python@v5` with
the Node.js 20 action-runtime deprecation warning. Official action releases now
provide Node 24-compatible majors:

- `actions/checkout@v5`
- `actions/setup-python@v6`

This story treats the warning as environmental CI/CD drift, not an application
bug.

Remote validation also exposed an unrelated environmental registry issue:
`fedora:latest` resolved through Docker Hub and failed twice before any workflow
step ran. The Fedora smoke job now pulls `registry.fedoraproject.org/fedora:latest`
directly so the distro smoke does not depend on Docker Hub availability.

## Acceptance Criteria

- **AC-1:** All `actions/checkout@v4` references are upgraded to
  `actions/checkout@v5`.
- **AC-2:** All `actions/setup-python@v5` references are upgraded to
  `actions/setup-python@v6`.
- **AC-3:** `ci`, `smoke`, and `publish` workflow trigger semantics remain
  unchanged.
- **AC-4:** The PyPI publish workflow remains `workflow_dispatch`-only and
  still uses the existing confirmation guard plus `environment: publish`.
- **AC-5:** Local validation confirms no remaining old action references and
  no YAML syntax regression.
- **AC-6:** Fedora smoke uses an explicit Fedora registry image instead of the
  Docker Hub shorthand.
- **AC-7:** PR and post-merge GitHub Actions checks pass.

## Tasks / Subtasks

- [x] 13.1 Verify official Node 24-compatible action majors.
- [x] 13.2 Update CI workflow action versions.
- [x] 13.3 Update smoke workflow action versions.
- [x] 13.4 Update publish workflow action versions without changing release
  guards.
- [x] 13.5 Document the environmental hardening decision.
- [x] 13.6 Move Fedora smoke away from Docker Hub shorthand after registry
  pull failures.
- [x] 13.7 Run local and remote validation.

## File List

**Modified:**

- `.github/workflows/ci.yml`
- `.github/workflows/smoke.yml`
- `.github/workflows/publish.yml`
- `NOTES.md`
- `docs/stories/STORY-001.12-node24-actions-hardening.md`
- `docs/gates/STORY-001.12-gate.md`

## Dev Notes

- This story does not publish to PyPI.
- This story does not change package version, source code, test code, or
  `publish.yml` dispatch/security semantics.
- GitHub-hosted runners are expected to satisfy the required runner baseline
  for Node 24-compatible official actions.

## Dev Agent Record

### Implementation Summary

- Updated all official GitHub checkout/setup-python action references to the
  Node 24-compatible majors.
- Moved Fedora smoke to `registry.fedoraproject.org/fedora:latest` after
  repeated Docker Hub pull timeouts during PR validation.
- Preserved every workflow trigger, permission block, matrix, and release
  guard.
- Added NOTES traceability for the environmental warning and resolution.

### Validation

See `docs/gates/STORY-001.12-gate.md`.
