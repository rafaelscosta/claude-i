# PyPI Trusted Publishing — Setup Guide

This guide documents the one-time operator prerequisites for publishing
`claude-i` to PyPI via GitHub Actions Trusted Publishing (OIDC). All long-lived
API token-based workflows are deliberately avoided.

**Audience:** repository operator (rafaelscosta) — these steps require
PyPI account credentials and GitHub repository admin access.

**When to execute:** before the first `claude-i` PyPI release. After completion,
the `publish.yml` workflow can be triggered manually via
`gh workflow run publish.yml` (or, if tag-trigger is later enabled, by pushing
`git tag v*.*.*`).

---

## Prerequisites

1. PyPI account at https://pypi.org (must be the same account that will own
   the `claude-i` project on PyPI).
2. GitHub repository admin on `rafaelscosta/claude-i`.
3. `claude-i` package name available on PyPI. The project endpoint still
   returned 404 during the v0.2.3 release-surface sync, so the first PyPI
   publish should register the project.

---

## Step 1 — Configure PyPI Pending Publisher

This step creates a Trusted Publisher record on pypi.org pointing to this
repository BEFORE the first release. Once a Pending Publisher is configured
and a successful publish occurs, the project is registered and the Pending
Publisher becomes a regular Trusted Publisher.

1. Sign in to https://pypi.org with the operator account.
2. Navigate to **Your account** → **Publishing** (or directly:
   https://pypi.org/manage/account/publishing/).
3. Scroll to **Add a new pending publisher** and click it.
4. Fill in the form:
   - **PyPI project name:** `claude-i`
   - **Owner:** `rafaelscosta`
   - **Repository name:** `claude-i`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `publish`
5. Click **Add**.
6. Verify the Pending Publisher appears in the list.

Reference: https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/

---

## Step 2 — Configure GitHub `publish` Environment

This environment gates the publish workflow with a required reviewer (a human
must explicitly approve each publish run). Without this gate, anyone with push
access to `main` could trigger a publish.

1. Navigate to https://github.com/rafaelscosta/claude-i/settings/environments.
2. Click **New environment**.
3. Name it `publish` (must match `environment: publish` in
   `.github/workflows/publish.yml`).
4. Under **Deployment protection rules** → **Required reviewers**:
   - Check the box.
   - Add `rafaelscosta` as a reviewer.
5. Under **Deployment branches** → restrict to `main` only (optional but
   recommended).
6. Click **Save protection rules**.

---

## Step 3 — Trigger the First Publish

After Steps 1 and 2 are complete:

1. Ensure `main` is up to date with the intended release version
   (`version = "0.2.3"` in `pyproject.toml` for the current public release).
2. Trigger the workflow manually:

   ```bash
   gh workflow run publish.yml --ref v0.2.3 \
     --field confirm_release=I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE
   ```

3. Approve the deployment in the GitHub UI when prompted (the required
   reviewer from Step 2 must click **Approve and deploy**).
4. Watch the workflow run:

   ```bash
   gh run watch
   ```

5. After success, verify the artifact appears on PyPI:

   ```bash
   curl -fsSL https://pypi.org/pypi/claude-i/json | python -m json.tool | grep version
   ```

---

## Step 4 — Validate Install

After the publish succeeds:

```bash
# pipx
pipx install claude-i
claude-i --version  # → claude-i 0.2.3

# uv tool
uv tool install claude-i
claude-i --version  # → claude-i 0.2.3
```

---

## Manual Override — TestPyPI

For a dry-run against TestPyPI before going to production PyPI:

1. Configure a separate Pending Publisher on https://test.pypi.org/ with
   identical settings (different workflow filename or environment optional;
   easiest is to add `--repository testpypi` config).
2. Use a parallel workflow or `twine upload --repository testpypi dist/*`
   from a local checkout authenticated with a TestPyPI API token.
3. Install from TestPyPI to validate:

   ```bash
   pipx install --index-url https://test.pypi.org/simple/ claude-i
   ```

TestPyPI validation is not required for the current release path — local
`pipx install dist/*.whl` and `uv tool install dist/*.whl` smoke tests
(documented in STORY-001.3) provide equivalent coverage.

---

## Recovery — Publish Failure

If `publish.yml` fails after a tag has been pushed (future tag-triggered
activation):

1. Inspect the failed run via `gh run view <run-id>`.
2. Fix the underlying issue.
3. If the failure was on the publish step (PyPI rejected the artifact), DELETE
   the tag and the GitHub Release before re-attempting:

   ```bash
   git push --delete origin v0.2.3
   gh release delete v0.2.3 --yes
   ```

   PyPI will not accept a re-upload of the same version-filename combination.
   You must either delete the failed PyPI artifact (PyPI has a yank/delete
   window) or bump the version and re-tag.

4. After recovery, re-push the tag (or use `workflow_dispatch`) to trigger
   a fresh run.

---

## References

- PyPI Trusted Publishing docs: https://docs.pypi.org/trusted-publishers/
- GitHub Action: https://github.com/pypa/gh-action-pypi-publish
- OIDC overview: https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
