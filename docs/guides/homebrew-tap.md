# Homebrew Tap — `rafaelscosta/homebrew-claude-i`

This guide documents the Homebrew tap, the dev-pass URL strategy used during the v0.2.0 epic, the epic-close finalization steps, and the curl-install security posture.

## Tap Repository

| Item                | Value                                                          |
|---------------------|----------------------------------------------------------------|
| GitHub repo         | https://github.com/rafaelscosta/homebrew-claude-i              |
| Tap invocation      | `brew tap rafaelscosta/claude-i`                               |
| Formula path        | `Formula/claude-i.rb`                                          |
| Direct install      | `brew install rafaelscosta/claude-i/claude-i`                  |
| Maintainer          | rafaelscosta (operator)                                        |

The tap name is **`homebrew-claude-i`** by Homebrew convention. The `homebrew-` prefix is stripped when invoking `brew tap`, so the tap is referenced as `rafaelscosta/claude-i`.

## Formula

The formula installs `claude-i` into a Homebrew-managed virtualenv at `libexec`, symlinks the entry-point into `bin/claude-i`, and declares `tmux` as a runtime dependency so a fresh `brew install` produces a working `claude-i` in one shot.

Source URL strategy varies by phase:

| Phase                       | Source URL                                                                                                              | `sha256`                              |
|-----------------------------|-------------------------------------------------------------------------------------------------------------------------|---------------------------------------|
| **v0.2.0 dev pass** (current) | `https://github.com/rafaelscosta/claude-i/releases/download/v0.2.0-pre/claude_i-0.2.0.tar.gz` (pre-release sdist asset) | `28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353` |
| **v0.2.0 final** (epic close) | `https://files.pythonhosted.org/packages/.../claude_i-0.2.0.tar.gz` (canonical PyPI URL after `publish.yml`)             | regenerated via `shasum -a 256`       |

The dev-pass URL points at a GitHub pre-release tagged `v0.2.0-pre`. This is deliberate:

- The pre-release URL is **portable and public** (no `file://` paths in the committed formula — see `.claude/rules/portable-paths.md`).
- The pre-release does **not** burn the canonical `v0.2.0` git tag, which is reserved for the final epic-close release (see `NOTES.md` § "v0.2.0 Release Tag — Deferred to Epic Close").
- The pre-release sdist is byte-identical to the artifact that will be uploaded to PyPI by `publish.yml` at epic close. The SHA256 above is the source of truth.

## Epic-Close Finalization (STORY-001.4 Task 5.9)

When the epic-close subtask runs:

1. Tag and push `v0.2.0`:
   ```bash
   cd /Users/rafaelcosta/Projects/AIOX/claude-i
   git tag v0.2.0
   git push origin v0.2.0
   ```
2. Trigger the publish workflow:
   ```bash
   gh workflow run publish.yml
   ```
   Approve the `publish` environment gate when prompted.
3. Once `claude-i==0.2.0` is on PyPI, capture the canonical sdist URL and SHA:
   ```bash
   pip download --no-deps --no-binary :all: claude-i==0.2.0 -d /tmp/claude-i-pypi/
   shasum -a 256 /tmp/claude-i-pypi/claude_i-0.2.0.tar.gz
   # The URL prints during pip download — typically https://files.pythonhosted.org/packages/<hash>/claude_i-0.2.0.tar.gz
   ```
4. In `rafaelscosta/homebrew-claude-i`, edit `Formula/claude-i.rb`:
   - Set `url` to the canonical `files.pythonhosted.org` URL.
   - Set `sha256` to the freshly captured value.
5. Verify locally on a clean macOS:
   ```bash
   brew untap rafaelscosta/claude-i || true
   brew tap rafaelscosta/claude-i
   brew install rafaelscosta/claude-i/claude-i
   brew test rafaelscosta/claude-i/claude-i
   claude-i --version
   ```
6. Commit + push the tap:
   ```bash
   cd /Users/rafaelcosta/Projects/AIOX/homebrew-claude-i
   git add Formula/claude-i.rb
   git commit -m "release: finalize v0.2.0 url to canonical PyPI [EPIC-001 close]"
   git push origin main
   ```
7. Delete the `v0.2.0-pre` pre-release once the canonical formula is live:
   ```bash
   cd /Users/rafaelcosta/Projects/AIOX/claude-i
   gh release delete v0.2.0-pre --yes --cleanup-tag
   ```
   This is optional — leaving the pre-release in place is harmless but tidier to remove once it has no consumers.

## Multi-OS Smoke (`smoke.yml`)

The 3-OS install smoke matrix lives in `.github/workflows/smoke.yml` and runs on:

- `macos-latest` — builds sdist, invokes `bash install.sh --local dist/claude_i-0.2.0.tar.gz`, asserts `claude-i --version` exits 0 with the expected version string.
- `ubuntu-latest` — same flow.
- `fedora:latest` container (running on `ubuntu-latest`) — same flow.

Windows is **out of scope** for v0.2.0 per the Epic *Out of Scope* clause and AC-10. A future story may add a `windows-latest` job that asserts `claude-i` exits 3 (`PLATFORM_ERROR`) on `sys.platform == "win32"`.

The smoke matrix asserts **install + version**, not end-to-end prompt execution. A live `claude` binary and Anthropic credentials are not required and not available in public CI.

## Security

### `curl ... | bash` checksum risk — accepted for v0.2.0

The bootstrap one-liner is:

```bash
curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh | bash
```

This trusts:

1. TLS to `raw.githubusercontent.com` (HTTPS validates GitHub's certificate).
2. The integrity of GitHub's content addressing — the URL serves whatever is committed to `main`.

It does **not** verify a checksum of the script bytes. An attacker who compromises the `main` branch can change `install.sh` and any download performed between the compromise and detection will execute the tampered code. This risk is **accepted by the operator for v0.2.0**:

- The script is small (~10 KB) and human-auditable.
- A future story may add a separate hash-verified install path (`install.sh.sha256` published alongside the script, with a wrapper that downloads, verifies, then executes), but that is not a v0.2.0 blocker.
- Users who want stronger guarantees can `git clone` the repo and run `bash install.sh` from a known SHA.

### Wheel/sdist hash verification

When `install.sh` calls `pipx install claude-i`, `pip` verifies the wheel hash against the PyPI manifest by default (`pip` requires a manifest match unless `--no-deps --force-reinstall` bypasses it). No additional `sha256` plumbing is needed in the script.

For the Homebrew path, the formula's `sha256` provides hash verification (AC-7). Homebrew refuses to install if the downloaded source does not match.

## Troubleshooting

### `claude-i: command not found` after install

`pipx ensurepath` writes `~/.local/bin` to your shell-rc but does not reload the current shell. Either:

- Open a new shell session, or
- Source your shell-rc: `source ~/.bashrc` (or `~/.zshrc` on macOS default).

The install script's final verification step uses the explicit path `$HOME/.local/bin/claude-i` so the script can confirm a successful install without requiring a shell-rc reload mid-execution.

### `brew install` fails with `404`

Confirm the tap is reachable: `brew tap rafaelscosta/claude-i && brew info rafaelscosta/claude-i/claude-i`. If the tap repo exists but the formula `url` returns 404, this is the dev-pass pre-release URL still propagating through GitHub's CDN (typically resolves within 5-15 minutes of release creation). Retry the install in a few minutes, or pin a specific commit of the tap via `brew install ./Formula/claude-i.rb` after `git clone`.

### Fedora minimal container missing build tools

If `install.sh` runs inside a fresh `fedora:latest` container (as in `smoke.yml`), it expects `tar`, `python3`, and `python3-pip` to be present. The smoke workflow installs these as a prereq step before invoking `install.sh`.

## Related

- `install.sh` — bootstrap script.
- `.github/workflows/smoke.yml` — 3-OS install smoke matrix.
- `NOTES.md` § "v0.2.0 Release Tag — Deferred to Epic Close" — rationale for deferring the canonical tag.
- `docs/stories/STORY-001.4-multi-target-install.md` — acceptance criteria for this story.
- `docs/guides/pypi-trusted-publishing.md` — OIDC trusted publishing setup (STORY-001.3).
