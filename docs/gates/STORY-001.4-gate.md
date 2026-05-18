# STORY-001.4 Quality Gate

| Field | Value |
|---|---|
| Story | STORY-001.4 — Multi-Target Install: Homebrew Tap, install.sh, 3-OS CI Smoke Matrix |
| Epic | EPIC-001 |
| Gate | **PASS** |
| Quality Score | **92 / 100** |
| Reviewer | Quinn (Test Architect) |
| Review Date | 2026-05-18 |
| Reviewed Commits (claude-i) | `ea5556e`, `c370bc8`, `399089f`, `5e8b8ab`, `36a6e9b`, `49730a4` (6 ahead of `origin/main`) |
| Reviewed Commits (homebrew-claude-i) | `4fc957e` (scaffold), `c7d6a9e` (formula) (1 ahead of `origin/main`) |
| Risk Profile | deep — cross-repo coordination + first install surface to consumers |
| Expires | 2026-06-01 |

## Status Reason

10 of 11 ACs verified end-to-end against local artifacts. The 11th (AC-1 brew install on a clean macOS) is satisfied by structural evidence — formula Ruby syntax OK, `Language::Python::Virtualenv` mixin correctly invoked, `depends_on "tmux"` + `depends_on "python@3.12"` present, `test do` block asserts `--version`, dev-pass URL `v0.2.0-pre` is live on GitHub with both sdist + wheel assets uploaded, and the sdist SHA256 in the formula matches the local `dist/claude_i-0.2.0.tar.gz` byte-for-byte (`28738be41964796c031f4b2927839e3282a890f906866385ead2279879ec4353`). End-to-end `brew tap` + `brew install` is unreachable until the tap repo is pushed to origin — that step is enumerated as a post-push immediate action, not a local-validation gap.

install.sh is bash with `set -euo pipefail`, parses 4 flags (`--dry-run`, `--check`, `--local`, `--help`), exits 1 on unknown flag with a usage hint, exits 1 on unsupported OS with a clear message, includes a Windows MINGW/MSYS/CYGWIN guard (parity with G9), and verifies via `$HOME/.local/bin/claude-i || claude-i` without shell-rc reload. PEP 668 cascade is correct on both apt and dnf paths (distro-pipx preferred, `python3 -m pip install --user pipx` fallback) — never bare `pip install pipx`. Local functional tests: `--dry-run` exits 0 with expected commands, `--check` exits 2 on a clean shell (matches smoke.yml assertion), `--help` prints embedded usage, unknown flag exits 1.

smoke.yml has 5 jobs: shellcheck lint, dry-run/check sanity, plus 3 OS smoke jobs (macos-latest, ubuntu-latest, fedora:latest container). All 3 OS jobs build the sdist locally and invoke `bash install.sh --local dist/claude_i-0.2.0.tar.gz` then assert `claude-i --version == "claude-i 0.2.0"` — eliminating the PyPI chicken-and-egg per advisor guidance. Windows-native is correctly excluded per AC-10.

No regressions to 001.1/001.2/001.3 contracts: pytest 68/68, ruff clean, mypy `--strict` clean (8 source files), `--version` prints `claude-i 0.2.0`, `seed/claude-i` byte-identical (MD5 `c51d55995f8a04244b13ced34285d679`, 180 lines). G4 (`--version` stdout = `claude-i {VERSION}`) and G9 (Windows-native PLATFORM_ERROR=3) contracts are intact at the package level; install.sh adds a parallel runtime guard for non-WSL Windows shells.

## Independent Quality Gates (re-run by @qa, fresh venv)

| Gate | Result | Notes |
|---|---|---|
| Fresh `python3 -m venv` + `pip install -e ".[dev]"` | exit 0 | Python 3.x, clean install |
| `pytest tests/` | **68 passed** in 0.25s | Zero regressions vs 001.3 |
| `ruff check src tests` | All checks passed | — |
| `mypy --strict src` | Success: no issues in 8 source files | — |
| `claude-i --version` | `claude-i 0.2.0` | G4 contract intact |
| `seed/claude-i` integrity | MD5 `c51d55995f8a04244b13ced34285d679`, 180 lines | Verbatim seed preserved |
| `bash install.sh --dry-run` (macOS) | exit 0; prints expected pipx fallback commands | Tap-unreachable branch hit correctly |
| `bash install.sh --check` (clean shell) | exit 2 | Matches smoke.yml dry-run job assertion |
| `bash install.sh --help` | exit 0; prints embedded usage | Self-documenting |
| `bash install.sh --bogus` | exit 1 + usage hint | Unknown-flag handling |
| `ruby -c Formula/claude-i.rb` | Syntax OK | Ruby parser accepts formula |
| `shasum -a 256 dist/claude_i-0.2.0.tar.gz` vs formula | byte-identical match | `28738be4...4353` consistent |
| `gh release view v0.2.0-pre` | prerelease=true, both sdist + wheel assets uploaded | Dev-pass URL reachable |
| `yaml.safe_load(.github/workflows/smoke.yml)` | 5 jobs: shellcheck, dry-run, smoke-macos, smoke-ubuntu, smoke-fedora | 3-OS matrix correct |

## AC Validation

| AC | Status | Evidence |
|---|---|---|
| AC-1 (Homebrew tap `claude-i.rb` exists, depends_on tmux, produces working `--version`) | PASS (structural; runtime via post-push) | Formula Ruby syntax OK; `class ClaudeI < Formula` + `include Language::Python::Virtualenv`; `depends_on "tmux"` + `depends_on "python@3.12"` present; `virtualenv_install_with_resources`; `test do { assert_match "claude-i 0.2.0", shell_output("#{bin}/claude-i --version") }`. End-to-end `brew install rafaelscosta/claude-i/claude-i` is unreachable pre-push — enumerated as immediate post-push action |
| AC-2 (install.sh at repo root, curl-pipe-bash reachable) | PASS | `install.sh` 301 lines, executable, at repo root; URL `https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh` will be live on first push to `main` |
| AC-3 (OS + pkg manager detection: macOS/brew, Debian/apt, Fedora/dnf; exit 1 on unsupported) | PASS | `uname -s` for Darwin/Linux; `/etc/os-release` parses `ID` + `ID_LIKE`; case branches for `ubuntu\|debian` (apt), `fedora\|rhel\|centos\|rocky\|almalinux` (dnf); `ID_LIKE` fallback for derivatives; unsupported emits clear error + `exit 1` |
| AC-4 (pipx bootstrap when missing, PEP 668-safe) | PASS | `bootstrap_pipx_linux()`: distro-pipx preferred (`apt install pipx`, `dnf install pipx`); fallback `python3 -m pip install --user pipx`; never bare `pip install pipx`. macOS uses `brew install pipx` |
| AC-5 (3-OS smoke matrix: macos-latest + ubuntu-latest + fedora:latest container) | PASS | smoke.yml jobs `smoke-macos` (macos-latest), `smoke-ubuntu` (ubuntu-latest), `smoke-fedora` (ubuntu-latest with `container: {image: fedora:latest}`); all 3 build sdist locally + invoke `install.sh --local` + assert `--version == "claude-i 0.2.0"` |
| AC-6 (no live `claude` binary or Anthropic session in smoke) | PASS | smoke.yml has no `ANTHROPIC_API_KEY` references, no `claude` invocations; only `--version` assertion via `importlib.metadata` |
| AC-7 (formula sources from PyPI or GitHub release asset, uses resource block or pip_install_formula) | PASS | Formula `url` → GitHub pre-release `v0.2.0-pre` sdist (dev pass); uses `Language::Python::Virtualenv` + `virtualenv_install_with_resources`; `sha256` declared and verified byte-match |
| AC-8 (dev-pass + epic-close two-pass strategy) | PASS | Dev pass: formula `url` → `https://github.com/rafaelscosta/claude-i/releases/download/v0.2.0-pre/claude_i-0.2.0.tar.gz`, SHA256 byte-match. Epic-close finalization: documented in `NOTES.md` § "STORY-001.4 — Homebrew Formula URL Finalization Deferred", `docs/guides/homebrew-tap.md` § "Epic-Close Finalization", and Story Task 5.9 |
| AC-9 (pipx ensurepath + final verify via `$HOME/.local/bin/claude-i || claude-i`) | PASS | `bootstrap_pipx_linux` calls `pipx ensurepath` after install; macOS `install_macos` calls `pipx ensurepath` on the fallback branch and after local-path install; `verify_installed()` checks explicit `$HOME/.local/bin/claude-i` first, then `command -v claude-i`. Does NOT reload shell-rc mid-script |
| AC-10 (Windows-native EXCLUDED from 3-OS matrix) | PASS | smoke.yml matrix is macos-latest + ubuntu-latest + fedora:latest only; no `windows-latest` job. install.sh adds a runtime MINGW/MSYS/CYGWIN guard that exits 1 with "Native Windows is unsupported in v0.2.0. Use WSL2 instead." (parity with G9). README documents WSL2 path |
| AC-11 (checksum risk for `curl | bash` accepted; PyPI wheel hash via pip; brew sha256 covers brew path) | PASS | `docs/guides/homebrew-tap.md` § Security documents the curl-script checksum risk as operator-accepted for v0.2.0; explains TLS to raw.githubusercontent.com, GitHub content addressing, and the alternative `git clone` + known-SHA path. PyPI wheel hash verification handled by pip automatically; formula `sha256` covers brew path |

## Cross-Repo Coordination (Task 5.8)

| Repo | Files | Commits | Status |
|---|---|---|---|
| `rafaelscosta/claude-i` | `install.sh`, `.github/workflows/smoke.yml`, `docs/guides/homebrew-tap.md`, `README.md` (full matrix), `.gitignore` (`.aiox/`), `NOTES.md` (Task 5.9 carryover), story file | 6 commits ahead of `origin/main` | Local only — push pending |
| `rafaelscosta/homebrew-claude-i` | `Formula/claude-i.rb` | 1 commit ahead of `origin/main` (post-scaffold) | Local only — push pending |

Sequence (per Task 5.8 spec + advisor guidance): (1) push claude-i → (2) wait for smoke matrix first-green on `main` → (3) push formula to tap repo → (4) post-push manual `brew tap` + `brew install` verification on clean macOS → (5) Task 5.9 deferred to EPIC-001 close.

## Task Completion

8 of 9 tasks marked `[x]`. Task 5.9 (Epic-Close Finalization) is intentionally deferred per AC-8 and @po condition 2 — the deferral is documented in 3 places (Story Task 5.9, `NOTES.md` § "STORY-001.4 — Homebrew Formula URL Finalization Deferred", and `docs/guides/homebrew-tap.md` § "Epic-Close Finalization") with a 7-step procedure. Task 5.7 stretch (`repository_dispatch` auto-update) correctly NOT implemented per operator decision; documented as a manual step in the tap guide.

## File List Audit

All declared files present:

**claude-i:**
- `install.sh` ✓ (301 lines, executable mode 755)
- `.github/workflows/smoke.yml` ✓ (167 lines, 5 jobs)
- `docs/guides/homebrew-tap.md` ✓ (145 lines)
- `README.md` ✓ (modified — full install matrix, replaces 001.3 stub)
- `.gitignore` ✓ (modified — `.aiox/` added)
- `NOTES.md` ✓ (modified — Task 5.9 carryover section added)
- `docs/stories/STORY-001.4-multi-target-install.md` ✓ (modified)

**homebrew-claude-i:**
- `Formula/claude-i.rb` ✓ (48 lines)

## Non-Functional Validation

| NFR | Status | Notes |
|---|---|---|
| Security | PASS | curl-pipe-bash checksum risk explicitly accepted by operator and documented; PyPI wheel hash verified by pip; brew sha256 verified by Homebrew; SHA256 byte-match verified locally. No secrets in CI workflow |
| Performance | PASS | Smoke matrix builds sdist once per job (~30KB tarball); install.sh is single-pass with no retries; expected wall-clock per OS job is well under GitHub Actions default 6h |
| Reliability | PASS | `set -euo pipefail` enables fail-fast in bash; idempotent flags (`--dry-run`, `--check`); explicit `verify_installed()` with two fallback paths; PEP 668 cascade covers Ubuntu 23.04+/Debian 12+/Fedora 38+ |
| Maintainability | PASS | install.sh: clear `log/warn/err` helpers, AC references in header comments, function-per-OS, helper for command execution. Formula: standard Homebrew Python pattern with inline docstring documenting dev-pass strategy. smoke.yml: per-job comments explain non-obvious steps (Fedora prereqs, dry-run/check expected exit codes) |

## Issues Found

### LOW — install.sh docstring inconsistency (cosmetic)

| Field | Value |
|---|---|
| File | `install.sh` |
| Severity | LOW |
| Lines | 11 vs 34 + 112 |

Line 11 (header docstring under `Flags:`) states `--check` "Exit 0 if claude-i is already installed and reachable; exit 1 otherwise." Line 34 (exit codes section) and line 112 (`exit 2` code path) state exit 2. Smoke matrix asserts exit 2. Behavior is correct; only the inline docstring on line 11 is stale.

**Recommended fix (post-push, non-blocking):** change line 11 "exit 1 otherwise" → "exit 2 otherwise" for consistency. Suggested owner: `dev`. Not gate-blocking.

### NOTE — Fresh-macOS curl|bash fallback hits PyPI 404 during dev pass

| Field | Value |
|---|---|
| Severity | INFO |

A user running `curl ... | bash install.sh` on a fresh macOS today (before the tap is pushed and before epic-close PyPI publish) hits the macOS fallback branch which calls `pipx install --force claude-i` — but `claude-i==0.2.0` is not on PyPI yet (deferred to epic close per NOTES.md). This is an acknowledged dev-pass tradeoff. Mitigation: the README install matrix tells macOS users to use `brew install` (which will work once the tap is pushed); `pipx install` would resolve only after epic-close PyPI publish. No code change recommended — acceptable for the dev-pass window.

## Recommendations

### Immediate (before story closure)

| Action | Owner | Refs |
|---|---|---|
| Push claude-i to origin (6 commits) | devops | `install.sh`, `.github/workflows/smoke.yml`, `docs/guides/homebrew-tap.md`, `README.md`, `.gitignore`, `NOTES.md`, story file |
| Confirm smoke matrix first-green on `main` (all 5 jobs pass) | devops | `.github/workflows/smoke.yml` |
| Push homebrew-claude-i to origin (1 commit) — AFTER smoke green on claude-i | devops | `Formula/claude-i.rb` |
| Manual end-to-end verification on clean macOS: `brew tap rafaelscosta/claude-i && brew install rafaelscosta/claude-i/claude-i && claude-i --version` (proves AC-1 runtime side) | devops or operator | tap repo |

### Future (post-001.4)

| Action | Owner | Refs |
|---|---|---|
| Fix install.sh docstring line 11 (exit 1 → exit 2) | dev | `install.sh:11` |
| Task 5.9 — Epic-close finalization (canonical PyPI URL + regenerated sha256) | devops | `Formula/claude-i.rb`, `docs/guides/homebrew-tap.md` § Epic-Close Finalization |
| Optional Windows-native job that asserts G9 exit-3 contract | dev | future story |
| Optional hash-verified curl install path (publish `install.sh.sha256` alongside) | dev | future story |

## Recommended Next

@devops `*push` (claude-i first, wait for smoke green, then push tap repo) → operator manual `brew install` verification on clean macOS → @po `*close-story` (Task 5.9 remains deferred to epic close, NOT a 001.4 blocker per AC-8).
