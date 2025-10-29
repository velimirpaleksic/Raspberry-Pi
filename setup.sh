#!/bin/bash
set -e  # Exit on first error

# === MARK ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DB_SCRIPT="$PROJECT_ROOT/db/db.py"
REQUIREMENTS_FILE="$(cd "$PROJECT_ROOT/../" && pwd)/requirements.txt"

# === Functions ===
install_requirements() {
    if [[ -f "$REQUIREMENTS_FILE" ]]; then
        echo "[REQUIREMENTS] Installing requirements..."
        python3 -m pip install --upgrade pip
        python3 -m pip install -r "$REQUIREMENTS_FILE"
        echo "[REQUIREMENTS] Requirements installed successfully."
    else
        echo "[REQUIREMENTS] No requirements.txt found, skipping installation."
    fi
}

create_database() {
    if [[ -f "$DB_SCRIPT" ]]; then
        echo "[DB] Creating database..."
        python3 "$DB_SCRIPT"
        echo "[DB] Database setup complete."
    else
        echo "[DB] Database script not found at: $DB_SCRIPT"
    fi
}

# === Main ===
echo "[SETUP] Starting setup..."
install_requirements
create_database
echo "[SETUP] Setup complete. You can add cron job with: crontab -e"