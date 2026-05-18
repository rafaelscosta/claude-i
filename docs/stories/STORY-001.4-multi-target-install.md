# STORY-001.4: Multi-Target Install — Homebrew Tap, install.sh, 3-OS CI Smoke Matrix

| Field | Value |
|---|---|
| Status | Draft |
| Epic | EPIC-001 |
| Owner | TBD |
| Created | 2026-05-17 |
| Depends on | STORY-001.3 |
| Estimated | 5 pts (~2 days) |

## User Story

As a developer on macOS, Ubuntu, or Fedora who prefers their native package manager, I want to install `claude-i` via `brew install`, a one-line `curl | sh`, or `pipx install` and immediately have a working `claude-i` binary with `tmux` as a pre-installed dependency, so that the tool is accessible without any manual dependency hunting.

## Acceptance Criteria

- AC-1: A Homebrew tap repository (`rafaelscosta/homebrew-claude-i`) exists with a formula `claude-i.rb` that includes `depends_on "tmux"`. Running `brew install rafaelscosta/claude-i/claude-i` on a macOS machine with Homebrew installed produces a working `claude-i --version` output.
- AC-2: `install.sh` is committed at `install.sh` in the root of `rafaelscosta/claude-i` (reachable at `https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh`) and is executable via `curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh | sh`.
- AC-3: `install.sh` detects the OS and package manager: on macOS with Homebrew present, installs via `brew install rafaelscosta/claude-i/claude-i`; on Debian/Ubuntu, installs `tmux` via `apt` then `pipx install claude-i`; on Fedora/RHEL, installs `tmux` via `dnf` then `pipx install claude-i`. On unsupported OS/PM combinations, the script exits 1 with a clear "unsupported" message.
- AC-4: `install.sh` installs `pipx` if not present (via `pip install pipx` or the distro-packaged `python3-pipx`), before calling `pipx install claude-i`.
- AC-5: The CI matrix in `.github/workflows/smoke.yml` runs on `macos-latest`, `ubuntu-latest`, and a Fedora container (`fedora:latest`) using `strategy.matrix`. Each job: installs `claude-i` via the method appropriate to the OS (brew / install.sh / install.sh), then runs `claude-i --version` and asserts exit 0.
- AC-6: The smoke matrix CI jobs do NOT require a live `claude` binary or active Anthropic session — the smoke test only validates installation and `--version` output, not end-to-end prompt execution (which requires secrets not available in public CI).
- AC-7: The Homebrew formula sources the wheel from the published PyPI release (not a GitHub tarball) or from the GitHub release asset, whichever is standard for Python-based Homebrew formulae. The formula uses the `resource` block for PyPI wheel or `pip_install_formula` pattern.

## Tasks / Subtasks

- [ ] 5.1 — Create Homebrew tap repository `rafaelscosta/homebrew-claude-i`
  - [ ] Create the repository on GitHub (separate from `rafaelscosta/claude-i`)
  - [ ] Initialize with a `Formula/` directory
  - [ ] This is a @devops action — document as prerequisite in story

- [ ] 5.2 — Write `claude-i.rb` Homebrew formula
  - [ ] Use `class ClaudeI < Formula` with `desc`, `homepage`, `url` (wheel or sdist from PyPI / GitHub release), `sha256`
  - [ ] `depends_on "python@3.11"` and `depends_on "tmux"`
  - [ ] Install via `pip install` into the formula's virtual environment (standard pattern for Python formulae)
  - [ ] `bin.install_symlink libexec/"bin/claude-i"`
  - [ ] Add `test do: system "#{bin}/claude-i", "--version"; end`
  - [ ] Commit to `rafaelscosta/homebrew-claude-i` — NOT to the main `claude-i` repo

- [ ] 5.3 — Write `install.sh` at repo root
  - [ ] Shebang: `#!/usr/bin/env sh` (POSIX sh, not bash — maximum portability)
  - [ ] Detect OS: `uname -s` for Darwin/Linux; on Linux, read `/etc/os-release` for `ID`/`ID_LIKE`
  - [ ] macOS path: `brew install rafaelscosta/claude-i/claude-i` (taps the tap and installs)
  - [ ] Ubuntu/Debian path: `sudo apt-get update -q && sudo apt-get install -y tmux pipx || pip install pipx && pipx install claude-i`
  - [ ] Fedora/RHEL path: `sudo dnf install -y tmux && pip install pipx && pipx install claude-i`
  - [ ] Unsupported: print message and `exit 1`
  - [ ] Final verification: `claude-i --version` — if exit nonzero, print install failure message and exit 1

- [ ] 5.4 — Make `install.sh` self-validating
  - [ ] Add a `--dry-run` flag to `install.sh` that prints the commands it would run without executing them
  - [ ] Add a `--check` flag that verifies `claude-i` is already installed and exits 0/1 accordingly

- [ ] 5.5 — Create `.github/workflows/smoke.yml`
  - [ ] Trigger: `push` to `main`, `pull_request` to `main`, `workflow_dispatch`
  - [ ] Matrix: `[{os: macos-latest, method: brew}, {os: ubuntu-latest, method: install-sh}, {os: ubuntu-latest, container: fedora:latest, method: install-sh}]`
  - [ ] macOS job: tap the repo + `brew install rafaelscosta/claude-i/claude-i` → `claude-i --version`
  - [ ] Ubuntu/Fedora job: `curl -fsSL .../install.sh | sh` → `claude-i --version`
  - [ ] Assert `claude-i --version` exits 0 and output contains `0.2.0`
  - [ ] No `ANTHROPIC_API_KEY` or `claude` binary needed — version check only

- [ ] 5.6 — Add Homebrew tap instructions to README
  - [ ] Add a "Install" section to `README.md` with a table:
    | Method | Command |
    |---|---|
    | Homebrew (macOS) | `brew install rafaelscosta/claude-i/claude-i` |
    | pipx | `pipx install claude-i` |
    | uv | `uv tool install claude-i` |
    | One-liner | `curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh \| sh` |

- [ ] 5.7 — Add formula update automation (optional, stretch)
  - [ ] Add a GitHub Actions workflow in `homebrew-claude-i` that triggers on a `repository_dispatch` event from the main `claude-i` repo on new tag push, auto-updates the formula SHA and version
  - [ ] If time-constrained, document as a manual step in `docs/guides/homebrew-tap.md` instead

## Dev Notes

- **Homebrew tap naming convention:** The tap repository MUST be named `homebrew-claude-i` (Homebrew prefix convention). The tap is invoked as `brew tap rafaelscosta/claude-i` which maps to `rafaelscosta/homebrew-claude-i` on GitHub.
- **Python Homebrew formula pattern:** Modern Homebrew Python formulae use `pip install` in a virtualenv. Reference `awscli` or `yt-dlp` formulae for the pattern. The key is `libexec` as the virtualenv prefix and symlinking the binary.
- **install.sh portability:** Use `/etc/os-release` for Linux distro detection — it is the `systemd` standard and present on Ubuntu, Fedora, Debian, and derivatives. Parse `ID` and `ID_LIKE` fields. `uname -s` distinguishes Darwin from Linux.
- **pipx bootstrap:** Many fresh Ubuntu/Fedora installs do not have `pipx`. The install script should handle: `pip3 install pipx` (fallback) or `apt-get install python3-pipx` (preferred on Ubuntu 23.04+) or `dnf install python3-pipx` (Fedora 38+). Check what's available before deciding.
- **Smoke test — no live claude required:** The smoke matrix must be self-contained. `claude-i --version` only loads `importlib.metadata` — it does not invoke tmux, hook, or claude. This is safe in public CI. End-to-end tests (requiring `claude` binary + API key) are deferred to a `integration.yml` workflow gated on secrets.
- **`install.sh` URL stability:** The URL `https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh` is stable as long as the file remains at the repo root on `main`. This is the canonical one-liner URL.
- **Fedora container in GitHub Actions:** Use `container: {image: fedora:latest}` in the job definition. `dnf` is pre-installed.
- **Expected files to touch:**
  - `install.sh` — new (in `rafaelscosta/claude-i` root)
  - `.github/workflows/smoke.yml` — new
  - `README.md` — install table
  - `docs/guides/homebrew-tap.md` — new
  - `Formula/claude-i.rb` in `rafaelscosta/homebrew-claude-i` — new (separate repo)

## Testing

- **Local `install.sh --dry-run`:** Verify output shows correct commands for detected OS without executing.
- **`install.sh --check` on a machine with pipx-installed `claude-i`:** Verify exits 0.
- **CI smoke matrix:** All 3 matrix jobs (macOS brew, Ubuntu install.sh, Fedora install.sh) must pass. This is the primary acceptance gate.
- **Homebrew formula `brew test claude-i`:** Runs the `test do` block in the formula (`claude-i --version`). Must pass on macOS.
- **Manual `brew install rafaelscosta/claude-i/claude-i`:** Run on a clean macOS machine; verify `claude-i --version` output and `tmux` is installed as a dependency.
- **One-liner manual test:** `curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh | sh` on a fresh Ubuntu VM; verify exit 0 and `claude-i --version`.

## File List

(empty — populated by @dev during execution)

## Dev Agent Record

(empty — populated by @dev)
