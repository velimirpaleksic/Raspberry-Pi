#!/bin/bash
set -euo pipefail

# === Paths ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
LINUX_REQ_FILE="$PROJECT_ROOT/linux_requirements.txt"
DB_SCRIPT="$PROJECT_ROOT/project/db/db.py"
TOUCHSCREEN_SCRIPT="$PROJECT_ROOT/touchscreen_auto_setup.sh"

# === Logging helpers ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info()    { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# === Install Linux requirements from file (skip installed) ===
install_linux_requirements() {
    if [[ ! -f "$LINUX_REQ_FILE" ]]; then
        log_error "linux_requirements.txt not found at: $LINUX_REQ_FILE"
        return 1
    fi

    log_info "Installing Linux system requirements from linux_requirements.txt..."
    sudo apt update

    while IFS= read -r package; do
        [[ -z "$package" || "$package" =~ ^# ]] && continue

        if dpkg -s "$package" >/dev/null 2>&1; then
            log_info "Already installed: $package (skipping)"
        else
            log_info "Installing: $package"
            sudo apt install -y "$package"
        fi
    done < "$LINUX_REQ_FILE"

    log_success "Linux system requirements installed."
}

# === Install Python requirements ===
install_python_requirements() {
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        log_info "Upgrading pip and installing Python requirements..."
        python3 -m pip install --upgrade pip setuptools wheel --break-system-packages
        python3 -m pip install -r "$REQUIREMENTS_FILE" --break-system-packages
        log_success "Python requirements installed successfully."
    else
        log_error "requirements.txt not found at: $REQUIREMENTS_FILE"
    fi
}

# === Run DB ===
create_database() {
    if [[ -f "$DB_SCRIPT" ]]; then
        log_info "Running database setup..."
        python3 "$DB_SCRIPT"
        log_success "Database setup complete."
    else
        log_error "Database script not found at: $DB_SCRIPT"
    fi
}

# === Run touchscreen setup ===
run_touchscreen_setup() {
    if [[ -f "$TOUCHSCREEN_SCRIPT" ]]; then
        log_info "Running touchscreen_auto_setup.sh..."
        chmod +x "$TOUCHSCREEN_SCRIPT"
        sudo "$TOUCHSCREEN_SCRIPT"
    else
        log_error "touchscreen_auto_setup.sh not found at: $TOUCHSCREEN_SCRIPT"
    fi
}

# === Main ===
log_info "Starting Raspberry Pi setup..."
install_linux_requirements
install_python_requirements
create_database
run_touchscreen_setup
log_success "Setup complete."