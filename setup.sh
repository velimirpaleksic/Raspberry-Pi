#!/bin/bash
set -euo pipefail  # strict error handling

# === Paths ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
DB_SCRIPT="$PROJECT_ROOT/project/db/db.py"

# === Logging helpers ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No color

log_info()    { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# === Functions ===
install_requirements() {
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        log_info "Upgrading pip and installing requirements..."
        python3 -m pip install --upgrade pip setuptools wheel
        python3 -m pip install -r "$REQUIREMENTS_FILE"
        log_success "Requirements installed successfully."
    else
        log_error "requirements.txt not found at: $REQUIREMENTS_FILE"
    fi
}

create_database() {
    if [[ -f "$DB_SCRIPT" ]]; then
        log_info "Running database setup..."
        python3 "$DB_SCRIPT"
        log_success "Database setup complete."
    else
        log_error "Database script not found at: $DB_SCRIPT"
    fi
}

# === Main ===
log_info "Starting setup..."
install_requirements
create_database
log_success "Setup complete. You can add a cron job with: crontab -e"