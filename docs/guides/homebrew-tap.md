# Homebrew Tap — `rafaelscosta/homebrew-claude-i`

This guide documents the Homebrew tap, the current PyPI source strategy, and the curl-install security posture.

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

Current source URL strategy:

| Phase | Source URL | `sha256` |
|---|---|---|
| **Current public formula** | `https://files.pythonhosted.org/packages/eb/e1/77672eeb8eace8dfe7b272a1226c4ae1b558aed2bd6715c682fed0c69508/claude_i-0.2.4.tar.gz` | `ca0a6575917f945fa6cb09c858130c0ae6094500500b70d7ffd9789219c3b9dc` |
| **Historical v0.2.3 fallback** | `https://github.com/rafaelscosta/claude-i/releases/download/v0.2.3/claude_i-0.2.3.tar.gz` | `ba7d4f6fcf7608c8681c0bfa2f14fd47c992f705d1211350988ebc967838513c` |

The current formula points at the canonical PyPI sdist:

- PyPI is the primary public package index for `claude-i`.
- No local `file://` paths are committed.
- Homebrew verifies the declared `sha256` before installation.
- The GitHub Release wheel/sdist remain available as fallback distribution artifacts.

## Release Update Procedure

For each future `claude-i` release, update the tap after the PyPI publish succeeds:

1. Trigger the publish workflow for the current release:
   ```bash
   cd /Users/rafaelcosta/Projects/AIOX/claude-i
   gh workflow run publish.yml --ref v0.2.4 \
     --field confirm_release=I-CONFIRM-PUBLIC-PERMANENT-PYPI-RELEASE
   ```
2. Once the package is on PyPI, capture the canonical sdist URL and SHA:
   ```bash
   pip download --no-deps --no-binary :all: claude-i==0.2.4 -d /tmp/claude-i-pypi/
   shasum -a 256 /tmp/claude-i-pypi/claude_i-0.2.4.tar.gz
   # The URL prints during pip download, usually https://files.pythonhosted.org/packages/<hash>/claude_i-0.2.4.tar.gz
   ```
3. In `rafaelscosta/homebrew-claude-i`, edit `Formula/claude-i.rb`:
   - Set `url` to the canonical `files.pythonhosted.org` URL.
   - Set `sha256` to the freshly captured value.
4. Verify locally on a clean macOS:
   ```bash
   brew untap rafaelscosta/claude-i || true
   brew tap rafaelscosta/claude-i
   brew install rafaelscosta/claude-i/claude-i
   brew test rafaelscosta/claude-i/claude-i
   claude-i --version
   ```
5. Commit + push the tap:
   ```bash
   cd /Users/rafaelcosta/Projects/AIOX/homebrew-claude-i
   git add Formula/claude-i.rb
   git commit -m "release: update claude-i formula to <version>"
   git push origin <branch>
   ```

## Multi-OS Smoke (`smoke.yml`)

The 3-OS install smoke matrix lives in `.github/workflows/smoke.yml` and runs on:

- `macos-latest` — builds sdist, invokes `bash install.sh --local dist/claude_i-<version>.tar.gz`, asserts `claude-i --version` exits 0 with the expected version string.
- `ubuntu-latest` — same flow.
- `registry.fedoraproject.org/fedora:latest` container (running on `ubuntu-latest`) — same flow.

Windows native remains out of scope. A future story may add a `windows-latest` job that asserts `claude-i` exits 3 (`PLATFORM_ERROR`) on `sys.platform == "win32"`.

The smoke matrix asserts **install + version**, not end-to-end prompt execution. A live `claude` binary and Anthropic credentials are not required and not available in public CI.

## Security

### `curl ... | bash` checksum risk

The bootstrap one-liner is:

```bash
curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh | bash
```

This trusts:

1. TLS to `raw.githubusercontent.com` (HTTPS validates GitHub's certificate).
2. The integrity of GitHub's content addressing — the URL serves whatever is committed to `main`.

It does **not** verify a checksum of the script bytes. An attacker who compromises the `main` branch can change `install.sh` and any download performed between the compromise and detection will execute the tampered code. This risk is accepted for the current bootstrap path:

- The script is small (~10 KB) and human-auditable.
- A future story may add a separate hash-verified install path (`install.sh.sha256` published alongside the script, with a wrapper that downloads, verifies, then executes).
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

Confirm the tap is reachable: `brew tap rafaelscosta/claude-i && brew info rafaelscosta/claude-i/claude-i`. If the tap repo exists but the formula `url` returns 404, verify the PyPI sdist URL in the public PyPI JSON and update the tap formula to the current `files.pythonhosted.org` URL.

### Fedora minimal container missing build tools

If `install.sh` runs inside a fresh `fedora:latest` container (as in `smoke.yml`), it expects `tar`, `python3`, and `python3-pip` to be present. The smoke workflow installs these as a prereq step before invoking `install.sh`.

## Related

- `install.sh` — bootstrap script.
- `.github/workflows/smoke.yml` — 3-OS install smoke matrix.
- `NOTES.md` § "IP Status — Public Release" — current public release and PyPI status.
- `docs/stories/STORY-001.4-multi-target-install.md` — acceptance criteria for this story.
- `docs/guides/pypi-trusted-publishing.md` — OIDC trusted publishing setup (STORY-001.3).
