#!/usr/bin/env bash
#
# claude-i installer — one-line bootstrap for macOS / Ubuntu/Debian / Fedora/RHEL
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/rafaelscosta/claude-i/main/install.sh | bash
#   bash install.sh [--dry-run] [--check] [--local <sdist-or-wheel-path>]
#
# Flags:
#   --dry-run             Print the commands that would run, but do not execute them.
#   --check               Exit 0 if claude-i is already installed and reachable; exit 1 otherwise.
#   --local <path>        Install from a local sdist/wheel path instead of PyPI. Used by CI
#                         smoke tests during the v0.2.0 dev pass (before PyPI publish).
#
# Acceptance criteria covered (STORY-001.4):
#   AC-2  install.sh hosted at repo root, fetchable via curl-pipe-bash
#   AC-3  OS + package manager detection (macOS/Homebrew, Debian/apt, Fedora/dnf)
#   AC-4  pipx bootstrap on Linux when missing
#   AC-9  pipx ensurepath + ~/.local/bin verification (does NOT reload shell-rc)
#   AC-11 wheel hash verification handed off to pip via PyPI manifest (no manual sha256)
#
# Constraints:
#   - On macOS, prefer `brew install rafaelscosta/claude-i/claude-i` once the tap formula is
#     live. If the tap is not reachable (early dev pass), fall back to pipx so the script
#     still produces a working install.
#   - PEP 668 (Ubuntu 23.04+, Debian 12+, Fedora 38+): never run bare `pip install pipx`.
#     Cascade is: distro-packaged pipx → `python3 -m pip install --user pipx`.
#   - Never modify shell-rc mid-script; rely on `pipx ensurepath` and final verification
#     via the explicit `$HOME/.local/bin/claude-i` path (AC-9).
#
# Exit codes:
#   0   success
#   1   install failed or unsupported OS/distro
#   2   --check: claude-i not installed

set -euo pipefail

# --- parse flags ----------------------------------------------------------
DRY_RUN=0
CHECK_MODE=0
LOCAL_PATH=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --check)
            CHECK_MODE=1
            shift
            ;;
        --local)
            if [ "$#" -lt 2 ]; then
                echo "ERROR: --local requires a path argument" >&2
                exit 1
            fi
            LOCAL_PATH="$2"
            shift 2
            ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *)
            echo "ERROR: unknown flag: $1" >&2
            echo "Run '$0 --help' for usage." >&2
            exit 1
            ;;
    esac
done

# --- helpers --------------------------------------------------------------
log()  { printf '[install.sh] %s\n' "$*"; }
warn() { printf '[install.sh] WARN: %s\n' "$*" >&2; }
err()  { printf '[install.sh] ERROR: %s\n' "$*" >&2; }

# run() executes a command, or prints it in --dry-run mode. Always uses `bash -c`
# so quoting in the printed form is unambiguous.
run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] %s\n' "$*"
    else
        log "+ $*"
        bash -c "$*"
    fi
}

# verify_installed() checks whether claude-i is reachable. Tries the explicit
# ~/.local/bin path first (where pipx installs), then falls back to PATH lookup
# in case Homebrew put it under /opt/homebrew/bin or /usr/local/bin. Does NOT
# rely on shell-rc reload (per AC-9).
verify_installed() {
    if [ -x "$HOME/.local/bin/claude-i" ]; then
        "$HOME/.local/bin/claude-i" --version
        return 0
    fi
    if command -v claude-i >/dev/null 2>&1; then
        claude-i --version
        return 0
    fi
    return 1
}

# --- --check mode ---------------------------------------------------------
if [ "$CHECK_MODE" -eq 1 ]; then
    if verify_installed; then
        log "claude-i is installed and reachable."
        exit 0
    else
        err "claude-i is NOT installed (or not on PATH and not at ~/.local/bin/claude-i)."
        exit 2
    fi
fi

# --- OS detection ---------------------------------------------------------
OS="$(uname -s)"
DISTRO=""
DISTRO_LIKE=""

if [ "$OS" = "Linux" ]; then
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO="${ID:-}"
        DISTRO_LIKE="${ID_LIKE:-}"
    else
        warn "/etc/os-release not present; cannot identify Linux distro reliably."
    fi
fi

log "Detected OS: $OS  distro: ${DISTRO:-?}  id_like: ${DISTRO_LIKE:-?}"
if [ -n "$LOCAL_PATH" ]; then
    log "Local install path: $LOCAL_PATH"
fi

# --- platform guard: native Windows is unsupported in v0.2.0 -------------
# (Aligns with G9 platform guard in src/claude_i/deps.py — exit 3 for parity.)
case "$OS" in
    MINGW*|MSYS*|CYGWIN*)
        err "Native Windows is unsupported in v0.2.0. Use WSL2 instead."
        exit 1
        ;;
esac

# --- pipx bootstrap (Linux only) -----------------------------------------
# PEP 668-safe cascade. Never bare `pip install pipx`.
bootstrap_pipx_linux() {
    if command -v pipx >/dev/null 2>&1; then
        log "pipx already installed."
        return 0
    fi
    log "Installing pipx..."
    case "$DISTRO" in
        ubuntu|debian)
            # Ubuntu 23.04+ / Debian 12+ ship python3-pipx; older releases need pip --user
            if run "sudo apt-get update -q"; then
                if ! run "sudo apt-get install -y pipx"; then
                    warn "apt-get install pipx failed; falling back to pip --user."
                    run "python3 -m pip install --user pipx"
                fi
            fi
            ;;
        fedora|rhel|centos|rocky|almalinux)
            if ! run "sudo dnf install -y pipx"; then
                warn "dnf install pipx failed; falling back to pip --user."
                run "python3 -m pip install --user pipx"
            fi
            ;;
        *)
            # ID_LIKE may include 'debian' or 'fedora' for derivatives
            case "$DISTRO_LIKE" in
                *debian*|*ubuntu*)
                    run "sudo apt-get update -q && sudo apt-get install -y pipx || python3 -m pip install --user pipx"
                    ;;
                *fedora*|*rhel*)
                    run "sudo dnf install -y pipx || python3 -m pip install --user pipx"
                    ;;
                *)
                    warn "Unknown Linux distro '$DISTRO' (id_like='$DISTRO_LIKE'); attempting pip --user fallback."
                    run "python3 -m pip install --user pipx"
                    ;;
            esac
            ;;
    esac
}

# --- macOS install --------------------------------------------------------
install_macos() {
    log "Installing on macOS..."
    if ! command -v brew >/dev/null 2>&1; then
        err "Homebrew is required on macOS. Install from https://brew.sh and re-run."
        exit 1
    fi

    if [ -n "$LOCAL_PATH" ]; then
        # Local mode: build via pipx from the local artifact. The brew tap path
        # is reserved for the canonical (PyPI-backed) install.
        log "Local-path mode: installing via pipx from $LOCAL_PATH"
        if ! command -v pipx >/dev/null 2>&1; then
            log "pipx not found; installing via brew."
            run "brew install pipx"
        fi
        run "pipx install --force '$LOCAL_PATH'"
        run "pipx ensurepath"
    else
        # Try the tap first. If the tap formula is not yet published (during the
        # dev pass before STORY-001.4 closes), fall back to pipx + PyPI so the
        # script still produces a working install on a fresh macOS.
        if brew tap rafaelscosta/claude-i 2>/dev/null && \
           brew info rafaelscosta/claude-i/claude-i >/dev/null 2>&1; then
            log "Installing via Homebrew tap rafaelscosta/claude-i."
            run "brew install rafaelscosta/claude-i/claude-i"
        else
            warn "Homebrew tap not reachable yet; falling back to pipx + PyPI."
            if ! command -v pipx >/dev/null 2>&1; then
                run "brew install pipx"
            fi
            run "pipx install --force claude-i"
            run "pipx ensurepath"
        fi
    fi
}

# --- Linux install --------------------------------------------------------
install_linux() {
    log "Installing on Linux ($DISTRO)..."

    # Step 1: tmux (runtime dependency of claude-i).
    case "$DISTRO" in
        ubuntu|debian)
            run "sudo apt-get update -q"
            run "sudo apt-get install -y tmux"
            ;;
        fedora|rhel|centos|rocky|almalinux)
            run "sudo dnf install -y tmux"
            ;;
        *)
            case "$DISTRO_LIKE" in
                *debian*|*ubuntu*)
                    run "sudo apt-get update -q && sudo apt-get install -y tmux"
                    ;;
                *fedora*|*rhel*)
                    run "sudo dnf install -y tmux"
                    ;;
                *)
                    err "Unsupported Linux distro: '$DISTRO' (id_like='$DISTRO_LIKE'). Supported: Debian/Ubuntu, Fedora/RHEL."
                    exit 1
                    ;;
            esac
            ;;
    esac

    # Step 2: pipx (PEP 668-safe cascade).
    bootstrap_pipx_linux

    # Step 3: install claude-i via pipx. Local path takes precedence over PyPI.
    if [ -n "$LOCAL_PATH" ]; then
        run "pipx install --force '$LOCAL_PATH'"
    else
        run "pipx install --force claude-i"
    fi

    # Step 4: ensure ~/.local/bin is on PATH (writes to shell-rc but does not
    # reload the current shell — verification below uses the explicit path).
    run "pipx ensurepath"
}

# --- main dispatch --------------------------------------------------------
case "$OS" in
    Darwin)
        install_macos
        ;;
    Linux)
        install_linux
        ;;
    *)
        err "Unsupported OS: $OS. Supported: macOS (Darwin), Linux."
        exit 1
        ;;
esac

# --- final verification ---------------------------------------------------
# AC-9: verify via explicit ~/.local/bin path OR PATH lookup, no shell-rc reload.
log "Verifying installation..."
if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] would verify: \$HOME/.local/bin/claude-i --version || claude-i --version"
    log "[dry-run] Done (dry-run)."
    exit 0
fi

if verify_installed; then
    log "claude-i installed successfully."
    log "Note: if 'claude-i' is not found in new shells, run: source ~/.bashrc  (or restart your shell)."
    exit 0
else
    err "Installation completed but 'claude-i' is not reachable."
    err "Try: \$HOME/.local/bin/claude-i --version"
    err "Or open a new shell and run: claude-i --version"
    exit 1
fi
