#!/bin/bash
# Raspberry Pi System Update Script
# Optimized for Debian-based Raspberry Pi OS

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No color

log_info()    { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# Ensure sudo privileges early
if ! sudo -v &>/dev/null; then
    log_error "This script requires sudo privileges."
    exit 1
fi

# Optional: reduce disk writes (Pi SD cards wear faster)
APT_FLAGS="-o Dpkg::Use-Pty=0 -o Acquire::Languages=none"

log_info "Refreshing package lists..."
sudo apt update $APT_FLAGS -y || { log_error "Failed to update package lists."; exit 1; }

log_info "Upgrading installed packages (minimal download output)..."
sudo apt full-upgrade $APT_FLAGS -y || { log_error "Failed to upgrade packages."; exit 1; }

log_info "Cleaning up old packages and cache..."
sudo apt autoremove $APT_FLAGS -y
sudo apt autoclean $APT_FLAGS -y

# Optional: cleanup logs older than 7 days (for SD longevity)
log_info "Trimming old logs to reduce SD card wear..."
sudo find /var/log -type f -mtime +7 -exec truncate -s 0 {} \; 2>/dev/null || true

log_success "System updated successfully."
log_info "Reboot the Raspberry Pi if the kernel or firmware was updated."