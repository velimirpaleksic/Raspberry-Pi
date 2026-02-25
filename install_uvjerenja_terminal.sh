#!/usr/bin/env bash
set -euo pipefail

# =========================
# Uvjerenja Terminal - Zero-touch installer (Raspberry Pi OS / Debian)
# =========================
#
# What this does:
# - Installs OS dependencies (Python/Tk, CUPS, LibreOffice headless, HP drivers, touchscreen calib tools)
# - Deploys the app into /opt/<app_id>/src and creates a venv in /opt/<app_id>/venv
# - Creates /etc/<app_id>/<app_id>.env for runtime config (printer, djelovodni broj, etc.)
# - Creates /var/lib/<app_id>/jobs for job queue/output (persists across reboots)
# - Installs and enables a systemd service that autostarts + restarts on failure
# - Optionally runs interactive touchscreen calibration (X11)

# ---- Adjustable settings (override via env when running the script) ----
APP_ID="${APP_ID:-uvjerenja-terminal}"                 # internal slug (no spaces)
APP_TITLE="${APP_TITLE:-Uvjerenja Terminal}"           # UI name
INSTALL_USER="${INSTALL_USER:-${SUDO_USER:-$USER}}"    # user that will run the GUI

# Touchscreen behavior
ENABLE_TOUCHSCREEN_SETUP="${ENABLE_TOUCHSCREEN_SETUP:-1}"       # 1=install + try calibrate now
AUTO_REBOOT_AFTER_TOUCH="${AUTO_REBOOT_AFTER_TOUCH:-1}"         # 1=reboot after calibration
TOUCH_CALIB_CONF="${TOUCH_CALIB_CONF:-/etc/X11/xorg.conf.d/99-calibration.conf}"

# Optional: set now, or change later in /etc/<app_id>/<app_id>.env
DEFAULT_DJELOVODNI_BROJ="${DEFAULT_DJELOVODNI_BROJ:-01-743/25}"
DEFAULT_PRINTER_NAME="${DEFAULT_PRINTER_NAME:-}"        # empty = autodetect default CUPS printer if possible
ENABLE_PRINTER_AUTODETECT="${ENABLE_PRINTER_AUTODETECT:-1}"

# ---- Paths ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$SCRIPT_DIR"

INSTALL_ROOT="/opt/$APP_ID"
SRC_DST="$INSTALL_ROOT/src"
VENV_DIR="$INSTALL_ROOT/venv"

ETC_DIR="/etc/$APP_ID"
ENV_FILE="$ETC_DIR/$APP_ID.env"

VAR_DIR="/var/lib/$APP_ID"
JOBS_DIR="$VAR_DIR/jobs"

SERVICE_FILE="/etc/systemd/system/$APP_ID.service"
TOUCH_HELPER="/usr/local/bin/${APP_ID}-touch-calibrate"

# ---- Logging ----
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { log_err "Missing command: $1"; exit 1; }
}

# ---- Sanity ----
if [[ ! -d "$SRC_ROOT/project" ]]; then
  log_err "Run this script from the project root (must contain ./project). Current: $SRC_ROOT"
  exit 1
fi

require_cmd sudo

log_info "Installing: $APP_TITLE ($APP_ID)"
log_info "Install user: $INSTALL_USER"

# ---- APT packages (includes touchscreen deps) ----
APT_PACKAGES=(
  python3 python3-venv python3-pip python3-tk
  rsync
  cups cups-bsd
  hplip printer-driver-hpcups
  libreoffice-core libreoffice-writer
  fonts-dejavu fonts-noto-core
  x11-xserver-utils xinput xserver-xorg-input-libinput xinput-calibrator
  unclutter-xfixes
)

log_info "Updating APT + installing system dependencies..."
sudo apt update
sudo apt install -y "${APT_PACKAGES[@]}"
log_ok "APT dependencies installed."

# ---- Enable CUPS ----
log_info "Enabling CUPS..."
sudo systemctl enable --now cups
sudo usermod -aG lpadmin "$INSTALL_USER" || true
log_ok "CUPS enabled; $INSTALL_USER added to lpadmin (may require logout/login)."

# ---- Create directories ----
log_info "Creating directories..."
sudo mkdir -p "$INSTALL_ROOT" "$ETC_DIR" "$JOBS_DIR"
sudo chown -R "$INSTALL_USER":"$INSTALL_USER" "$INSTALL_ROOT" "$VAR_DIR"
log_ok "Directories ready."

# ---- Deploy code (idempotent) ----
log_info "Deploying code to $SRC_DST ..."
sudo mkdir -p "$SRC_DST"
sudo rsync -a --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  "$SRC_ROOT/" "$SRC_DST/"
sudo chown -R "$INSTALL_USER":"$INSTALL_USER" "$SRC_DST"
log_ok "Code deployed."

# ---- Python venv + pip install ----
log_info "Creating venv at $VENV_DIR ..."
sudo -u "$INSTALL_USER" python3 -m venv "$VENV_DIR"
log_info "Installing Python requirements..."
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/pip" install -r "$SRC_DST/requirements.txt"
log_ok "Python deps installed in venv."

# ---- Printer autodetect (optional) ----
DETECTED_PRINTER=""
if [[ -z "$DEFAULT_PRINTER_NAME" && "$ENABLE_PRINTER_AUTODETECT" == "1" ]]; then
  DETECTED_PRINTER="$(lpstat -d 2>/dev/null | awk -F': ' '{print $2}' || true)"
fi

PRINTER_TO_WRITE="$DEFAULT_PRINTER_NAME"
if [[ -z "$PRINTER_TO_WRITE" && -n "$DETECTED_PRINTER" ]]; then
  PRINTER_TO_WRITE="$DETECTED_PRINTER"
fi
if [[ -z "$PRINTER_TO_WRITE" ]]; then
  PRINTER_TO_WRITE="Printer_Name"
fi

# ---- Write env file (create if missing) ----
if [[ ! -f "$ENV_FILE" ]]; then
  log_info "Creating env file: $ENV_FILE"
  sudo tee "$ENV_FILE" >/dev/null <<EOF
# $APP_TITLE runtime configuration
POTVRDE_APP_ID="$APP_ID"
POTVRDE_APP_TITLE="$APP_TITLE"

# Printer (CUPS queue name)
POTVRDE_PRINTER_NAME="$PRINTER_TO_WRITE"

# Djelovodni broj
POTVRDE_DJELOVODNI_BROJ="$DEFAULT_DJELOVODNI_BROJ"

# Base directories (persisted data)
POTVRDE_VAR_DIR="$VAR_DIR"

# Debug
POTVRDE_DEBUG_MODE="0"

# Display (X11 / XWayland)
DISPLAY=":0"
EOF
  sudo chmod 0644 "$ENV_FILE"
  log_ok "Env file created."
else
  log_info "Env file already exists (keeping): $ENV_FILE"
fi

# ---- systemd unit ----
log_info "Installing systemd service: $SERVICE_FILE"
sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=$APP_TITLE
After=graphical.target cups.service
Wants=cups.service

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_USER
WorkingDirectory=$SRC_DST
EnvironmentFile=$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=XAUTHORITY=/home/$INSTALL_USER/.Xauthority

# Prevent screen blanking (X11)
ExecStartPre=/usr/bin/xset s off
ExecStartPre=/usr/bin/xset -dpms
ExecStartPre=/usr/bin/xset s noblank

# Hide mouse cursor after inactivity (X11)
ExecStartPre=/usr/bin/unclutter -idle 0.5 -root &

ExecStart=$VENV_DIR/bin/python -B -m project.core.app
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$APP_ID.service"
log_ok "Service enabled + started: $APP_ID.service"

# =========================
# Touchscreen setup helpers
# =========================

detect_touch_name() {
  xinput list --name-only 2>/dev/null | grep -Eai \
    'touchscreen|touch screen|touch panel|touch|hid.*touch|egalax|ilitek|goodix|elan|ft5x|ads7846|atmel' \
    | head -n 1 || true
}

write_touch_helper_script() {
  sudo tee "$TOUCH_HELPER" >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

CONF_PATH="${1:-/etc/X11/xorg.conf.d/99-calibration.conf}"

echo "[INFO] Touch calibration helper"
echo "[INFO] DISPLAY=${DISPLAY:-<unset>}  XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-<unset>}"

if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
  echo "[WARN] Wayland session detected. xinput_calibrator requires X11."
  echo "[INFO] Switch desktop session to X11, then rerun:"
  echo "       sudo '"$(basename "$0")"'"
  exit 2
fi

if [[ -z "${DISPLAY:-}" ]]; then
  echo "[ERROR] DISPLAY is not set. Run this from the Pi desktop session (not plain SSH)."
  exit 3
fi

if ! command -v xinput_calibrator >/dev/null 2>&1; then
  echo "[ERROR] xinput_calibrator not installed."
  exit 4
fi

TOUCH_NAME="$(xinput list --name-only 2>/dev/null | grep -Eai 'touchscreen|touch screen|touch panel|touch|hid.*touch|egalax|ilitek|goodix|elan|ft5x|ads7846|atmel' | head -n 1 || true)"
if [[ -z "$TOUCH_NAME" ]]; then
  echo "[ERROR] No touchscreen device detected by xinput."
  echo "[INFO] Check cable/USB and run: xinput list"
  exit 5
fi

echo "[OK] Detected touchscreen: $TOUCH_NAME"
echo "[INFO] Running interactive calibration now..."
CALIB_OUTPUT="$(xinput_calibrator 2>&1 || true)"

if ! echo "$CALIB_OUTPUT" | grep -q "Section \"InputClass\""; then
  echo "[ERROR] Calibration did not produce xorg.conf snippet."
  echo "$CALIB_OUTPUT"
  exit 6
fi

echo "[INFO] Writing calibration to: $CONF_PATH"
sudo mkdir -p "$(dirname "$CONF_PATH")"
echo "$CALIB_OUTPUT" | sudo tee "$CONF_PATH" >/dev/null

echo "[OK] Calibration saved."
echo "[INFO] Reboot recommended to apply calibration."
EOF
  sudo chmod 0755 "$TOUCH_HELPER"
  log_ok "Touch helper installed: $TOUCH_HELPER"
}

touchscreen_setup_now() {
  if [[ "$ENABLE_TOUCHSCREEN_SETUP" != "1" ]]; then
    log_info "Touchscreen setup disabled (ENABLE_TOUCHSCREEN_SETUP=0)."
    return 0
  fi

  write_touch_helper_script

  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]]; then
    log_err "Wayland session detected. Calibration requires X11."
    log_info "Switch session to X11, then run:"
    log_info "  sudo $TOUCH_HELPER $TOUCH_CALIB_CONF"
    return 0
  fi

  if [[ -z "${DISPLAY:-}" ]]; then
    log_info "No DISPLAY detected (probably SSH). Touchscreen calibration is interactive."
    log_info "When you are on the Pi desktop, run:"
    log_info "  sudo $TOUCH_HELPER $TOUCH_CALIB_CONF"
    return 0
  fi

  local tn
  tn="$(detect_touch_name)"
  if [[ -z "$tn" ]]; then
    log_info "No touchscreen device detected by xinput right now."
    log_info "If touchscreen is connected, run later from desktop:"
    log_info "  sudo $TOUCH_HELPER $TOUCH_CALIB_CONF"
    return 0
  fi

  log_info "Detected touchscreen: $tn"
  log_info "Starting interactive calibration..."
  if sudo "$TOUCH_HELPER" "$TOUCH_CALIB_CONF"; then
    log_ok "Touchscreen calibration complete."
    if [[ "$AUTO_REBOOT_AFTER_TOUCH" == "1" ]]; then
      log_info "Rebooting in 10 seconds to apply calibration..."
      sleep 10
      sudo reboot
    else
      log_info "AUTO_REBOOT_AFTER_TOUCH=0 -> skipping reboot."
    fi
  else
    log_err "Touchscreen calibration failed. You can retry later:"
    log_info "  sudo $TOUCH_HELPER $TOUCH_CALIB_CONF"
  fi
}

touchscreen_setup_now

log_ok "Done."
log_info "Logs: sudo journalctl -u $APP_ID.service -f"
log_info "Config: sudo nano $ENV_FILE"
