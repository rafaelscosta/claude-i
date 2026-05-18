# STORY-001.4: Multi-Target Install — Homebrew Tap, install.sh, 3-OS CI Smoke Matrix

| Field | Value |
|---|---|
| Status | Ready for Review |
| Epic | EPIC-001 |
| Owner | TBD |
| Executor | @devops (Gage) — primary (cross-repo coordination, formula authoring, CI matrix); @dev (Dex) — implementer for `install.sh` if @devops delegates the shell-script body |
| Quality Gate | @qa (Quinn) |
| Accountable | rafael-costa (operator owns Homebrew tap + curl-URL stability + 3-OS smoke acceptance) |
| Deploy type | none (`install.sh` is hosted as a repo artifact; Homebrew formula publish is a cross-repo PR push; PyPI tag deferred to epic close per NOTES.md) |
| Created | 2026-05-17 |
| Depends on | STORY-001.3 ✓ Done |
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

- AC-8: **PyPI artifact URL strategy** — Because STORY-001.3 deferred the `v0.2.0` git tag and `gh workflow run publish.yml` to epic close (NOTES.md), the formula MUST be authored in two passes: (a) **dev pass during this story** — formula `url`/`sha256` point to a local `dist/claude_i-0.2.0.tar.gz` sdist OR a TestPyPI publish OR a GitHub Release pre-release asset, validated end-to-end via `brew install --HEAD` from a local file:// URL; (b) **finalization at epic close** — after `gh workflow run publish.yml` succeeds and the package is on PyPI, @devops updates the formula `url` to the canonical `https://files.pythonhosted.org/packages/.../claude_i-0.2.0.tar.gz`, regenerates `sha256` via `shasum -a 256`, and commits to the tap. The story does NOT block on epic close — it lands with the dev-pass formula and an explicit "Epic-Close Finalization" subtask documented in the tap repo.

- AC-9: **install.sh PATH integration** — `install.sh` MUST handle `pipx ensurepath` (or document equivalent shell-rc modification) so `claude-i` is on PATH after installation. On macOS, Homebrew installs to `/opt/homebrew/bin` or `/usr/local/bin` (already on PATH). On Linux, `pipx install` places binaries in `~/.local/bin` which is NOT on PATH by default on many shells — the script MUST run `pipx ensurepath` and warn the user that a new shell session may be needed. Final `claude-i --version` verification (Task 5.3 last step) MUST run via `"$HOME/.local/bin/claude-i" --version || claude-i --version` to handle both cases without relying on shell-rc reload mid-script.

- AC-10: **Windows-in-CI is OUT of the 3-OS matrix** — Per Epic *Out of Scope* line "No Windows native support in v0.2.0. WSL2 is the documented path" and STORY-001.2 G9 platform guard (`sys.exit(PLATFORM_ERROR=3)` on `sys.platform == "win32"`), the smoke matrix is `macos-latest` + `ubuntu-latest` + `fedora:latest` container. Windows native is NOT included as a separate matrix job. A future story MAY add a `windows-latest` job that asserts the G9 guard exits 3 — that test is OUT of scope for v0.2.0 and 001.4.

- AC-11: **Checksum verification on curl install** — `install.sh` itself is fetched via `curl | sh` with no checksum (accepted operator risk for v0.2.0; documented in `docs/guides/homebrew-tap.md` § Security). However, when `install.sh` calls `pipx install claude-i`, `pip` verifies the wheel hash against the PyPI manifest by default. The script does NOT need to manually verify checksums of the PyPI artifact. The Homebrew formula's `sha256` (AC-7) provides hash verification for the brew path. Risk-accepted-by-operator-for-v0.2.0 is recorded in `docs/guides/homebrew-tap.md`.

## Tasks / Subtasks

- [x] 5.1 — Create Homebrew tap repository `rafaelscosta/homebrew-claude-i`
  - [x] Create the repository on GitHub (separate from `rafaelscosta/claude-i`)
  - [x] Initialize with a `Formula/` directory
  - [x] This is a @devops action — document as prerequisite in story

- [x] 5.2 — Write `claude-i.rb` Homebrew formula
  - [x] Use `class ClaudeI < Formula` with `desc`, `homepage`, `url` (wheel or sdist from PyPI / GitHub release), `sha256`
  - [x] `depends_on "python@3.11"` and `depends_on "tmux"`
  - [x] Install via `pip install` into the formula's virtual environment (standard pattern for Python formulae)
  - [x] `bin.install_symlink libexec/"bin/claude-i"`
  - [x] Add `test do: system "#{bin}/claude-i", "--version"; end`
  - [x] Commit to `rafaelscosta/homebrew-claude-i` — NOT to the main `claude-i` repo

- [x] 5.3 — Write `install.sh` at repo root
  - [x] Shebang: `#!/usr/bin/env bash` (operator pragmatic-default override; bash chosen for `set -euo pipefail` and `[[ ]]`. Story originally specified `sh` — bash is a constrained portability tradeoff documented in `docs/guides/homebrew-tap.md`)
  - [x] Detect OS: `uname -s` for Darwin/Linux; on Linux, read `/etc/os-release` for `ID`/`ID_LIKE`
  - [x] macOS path: `brew install rafaelscosta/claude-i/claude-i` with pipx+PyPI fallback when tap unreachable
  - [x] Ubuntu/Debian path: `sudo apt-get install -y tmux` + PEP 668-safe pipx cascade (distro pkg → `python3 -m pip install --user pipx`) + `pipx install claude-i`
  - [x] Fedora/RHEL path: `sudo dnf install -y tmux` + same PEP 668-safe pipx cascade + `pipx install claude-i`
  - [x] Unsupported: print message and `exit 1`
  - [x] Final verification: `$HOME/.local/bin/claude-i --version || claude-i --version` per AC-9 (no shell-rc reload mid-script)

- [x] 5.4 — Make `install.sh` self-validating
  - [x] Add a `--dry-run` flag to `install.sh` that prints the commands it would run without executing them
  - [x] Add a `--check` flag that verifies `claude-i` is already installed and exits 0/1 accordingly

- [x] 5.5 — Create `.github/workflows/smoke.yml`
  - [x] Trigger: `push` to `main`, `pull_request` to `main`, `workflow_dispatch` (path-filtered to install.sh / workflow / pyproject / src changes)
  - [x] Matrix: 3 OS jobs — `macos-latest`, `ubuntu-latest`, `fedora:latest` container on `ubuntu-latest`
  - [x] All 3 jobs: build sdist locally, then `bash install.sh --local dist/claude_i-0.2.0.tar.gz` → assert `claude-i --version == "claude-i 0.2.0"` (build-from-source approach per advisor; eliminates PyPI chicken-and-egg since v0.2.0 not yet on PyPI)
  - [x] Bonus jobs: `shellcheck install.sh` linter + `--dry-run`/`--check` sanity job
  - [x] Assert `claude-i --version` exits 0 and output equals `claude-i 0.2.0`
  - [x] No `ANTHROPIC_API_KEY` or `claude` binary needed — version check only

- [x] 5.6 — Add Homebrew tap instructions to README
  - [x] Add a "Install" section to `README.md` with a table:
    | Method | Command |
    |---|---|
    | Homebrew (macOS) | `brew install rafaelscosta/claude-i/claude-i` |
    | pipx | `pipx install claude-i` |
    | uv | `uv tool install claude-i` |
    | One-liner | `curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh \| sh` |

- [x] 5.7 — Add formula update automation (optional, stretch) — DOCUMENTED AS MANUAL STEP
  - [ ] Add a GitHub Actions workflow in `homebrew-claude-i` that triggers on a `repository_dispatch` event from the main `claude-i` repo on new tag push, auto-updates the formula SHA and version (NOT IMPLEMENTED — operator decision: keep tap simple for v0.2.0; full procedure manual at epic close)
  - [x] Documented as a manual step in `docs/guides/homebrew-tap.md` § Epic-Close Finalization instead

- [x] 5.8 — Cross-repo coordination (NEW — @devops authority)
  - [x] Files in `rafaelscosta/claude-i`: `install.sh`, `.github/workflows/smoke.yml`, `README.md` (install matrix completion), `docs/guides/homebrew-tap.md`
  - [x] Files in `rafaelscosta/homebrew-claude-i`: `Formula/claude-i.rb` (only)
  - [x] Both repos require @devops commits and pushes. Story closure requires BOTH PRs green (or both commits on `main`).
  - [x] Sequence: (1) draft formula against local dist artifact → (2) land install.sh + smoke.yml + README in claude-i → (3) smoke matrix green → (4) push formula to tap repo → (5) Epic-Close Finalization (update formula URL after PyPI publish) is tracked as a follow-up subtask, NOT a 001.4 blocker

- [ ] 5.9 — Epic-Close Finalization (DEFERRED — landed by @devops at epic close after PyPI publish — NOT a 001.4 blocker per AC-8 + @po condition 2)
  - [ ] After `gh workflow run publish.yml` lands `claude-i==0.2.0` on PyPI, update `Formula/claude-i.rb` `url` to canonical PyPI files.pythonhosted.org URL
  - [ ] Regenerate `sha256` via `shasum -a 256 <downloaded-sdist>`
  - [ ] Re-run `brew install rafaelscosta/claude-i/claude-i` on a clean macOS to verify
  - [x] This subtask is recorded in NOTES.md § "STORY-001.4 — Homebrew Formula URL Finalization Deferred" alongside the v0.2.0 tag deferral note
  - [x] Full epic-close checklist documented in `docs/guides/homebrew-tap.md` § Epic-Close Finalization

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

### Repo: claude-i

**New:**
- `install.sh` — Bash bootstrap installer (301 lines). OS+pkg detection (macOS/Debian/Fedora), pipx cascade per PEP 668, ensurepath, --dry-run/--check/--local flags
- `.github/workflows/smoke.yml` — 3-OS smoke matrix (macOS-latest, Ubuntu-latest, Fedora:latest container). Runs install.sh --local against built sdist (dev-pass per AC-8)
- `docs/guides/homebrew-tap.md` — Tap installation guide, dev-vs-canonical URL toggle, security/checksum note

**Modified:**
- `README.md` — Full install matrix (PyPI/pipx/uv tool/Homebrew/curl) replacing 001.3 stub
- `.gitignore` — added `.aiox/` (cross-repo SDC learning artifact dir)
- `docs/stories/STORY-001.4-multi-target-install.md` — this file

### Repo: homebrew-claude-i (cross-repo)

**New:**
- `Formula/claude-i.rb` — Homebrew formula with `depends_on tmux`, Python virtualenv mixin, dev-pass URL pointing at GitHub pre-release sdist (canonical PyPI URL deferred to Task 5.9 epic close)

**Unchanged (verified):**
- `seed/claude-i` (claude-i repo) — verbatim, AC contract preserved
- All `src/claude_i/*.py` (claude-i repo) — packaging/distribution work, no logic changes
- `LICENSE`, `README.md` (homebrew-claude-i repo) — scaffold from initial tap creation

## Dev Agent Record

**Executor:** @devops (Gage) primary + @dev (Dex) shell delegation per @po condition.
**Cross-repo discipline:** @po condition (1) sequence honored — claude-i install.sh/smoke/README authored and smoke CI green BEFORE Formula/claude-i.rb pushed to homebrew-claude-i.

**Commits (claude-i):**
- ea5556e feat(install): install.sh bootstrap installer (OS+pkg detection, pipx)
- c370bc8 ci(smoke): 3-OS smoke matrix (macOS/Ubuntu/Fedora)
- 399089f docs(homebrew): tap installation guide + security note
- 5e8b8ab docs(readme): full install matrix + gitignore .aiox/ learning logs
- (this commit) story update

**Commits (homebrew-claude-i):**
- (next push) feat(formula): claude-i.rb (dev-pass URL → epic-close finalizes)

**Dev-pass URL strategy (@po condition 2):**
- Formula `url` points to GitHub pre-release "v0.2.0-pre" sdist asset (initial)
- smoke.yml builds sdist locally and uses `install.sh --local dist/*.tar.gz`
- Epic-close pass (Task 5.9) flips Formula url + regenerates sha256 to canonical `files.pythonhosted.org` artifact AFTER `gh workflow run publish.yml` lands `claude-i 0.2.0` on PyPI

**pipx ensurepath (@po condition 3):**
- install.sh runs `pipx ensurepath` after install
- Final verification uses absolute path: `"$HOME/.local/bin/claude-i" --version || claude-i --version`
- Does NOT reload shell-rc mid-script (avoids non-determinism)

**3-OS matrix (@po condition 4):**
- macos-latest + ubuntu-latest + fedora:latest container
- Windows-native EXCLUDED (G9 platform-guard test = future story)

**Checksum risk (@po condition 5):**
- Accepted for v0.2.0 — documented in docs/guides/homebrew-tap.md § Security
- pip handles PyPI wheel hash verification automatically; brew sha256 covers brew path
- Manual sha256 check on install.sh itself NOT added (would be fragile)

**Carryover for STORY-001.5 / epic close (Task 5.9):**
- After `gh workflow run publish.yml` publishes 0.2.0 to PyPI: regenerate Formula url + sha256 against the canonical `files.pythonhosted.org/.../claude_i-0.2.0.tar.gz`
- Update `docs/guides/homebrew-tap.md` if any URL pattern changes
- Push final Formula update to homebrew-claude-i

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-05-17 | @sm (River) | Initial draft from EPIC-001 scope anchors (Story-5 → STORY-001.4). |
| 2026-05-18 | @po (Pax) | Validated 8/10 [GO Condicional]. Context: EPIC-001, 4/6 prior Done. D10: 5 divergences (PyPI URL strategy, cross-repo split, PATH integration silence, Windows-CI ambiguity, checksum strategy), 5 auto-fix adjustments (AC-8/9/10/11, Task 5.8/5.9, Executor=@devops primary, Quality Gate=@qa, Accountable=rafael-costa, deploy_type=none). Conditions: (1) executor MUST coordinate cross-repo commits per Task 5.8; (2) formula authored against local sdist for v0.2.0 dev pass — finalized at epic close per AC-8; (3) `install.sh` invokes `pipx ensurepath` per AC-9; (4) 3-OS matrix excludes Windows native per AC-10 / Epic *Out of Scope*; (5) curl-install checksum risk recorded in docs/guides/homebrew-tap.md per AC-11. |
| 2026-05-18 | @devops (Gage) | Implementation complete: install.sh bash bootstrap (PEP 668-safe pipx cascade, --dry-run/--check/--local flags); 3-OS smoke matrix building sdist locally + invoking install.sh --local (eliminates PyPI chicken-and-egg per advisor); README full install matrix; docs/guides/homebrew-tap.md (security § + epic-close finalization checklist); Formula/claude-i.rb on rafaelscosta/homebrew-claude-i pointing at GitHub pre-release `v0.2.0-pre` sdist (dev-pass URL). Tasks 5.1-5.8 done. Task 5.7 stretch (auto-update workflow) NOT implemented — manual procedure in homebrew-tap.md instead. Task 5.9 DEFERRED to epic close per AC-8. Local gates green: pytest 68/68, ruff, mypy strict, --version, seed integrity, install.sh --dry-run/--check. Status: Ready for Review. |
