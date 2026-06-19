#!/usr/bin/env bash
set -euo pipefail

APP_ID="${APP_ID:-uvjerenja-terminal}"
APP_TITLE="${APP_TITLE:-Uvjerenja Terminal}"
INSTALL_USER="${INSTALL_USER:-${SUDO_USER:-$USER}}"
DEFAULT_PRINTER_NAME="${DEFAULT_PRINTER_NAME:-}"
ENABLE_PRINTER_AUTODETECT="${ENABLE_PRINTER_AUTODETECT:-1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$SCRIPT_DIR"
LOCAL_ENV_FILE="$SRC_ROOT/.env"
if [[ -f "$LOCAL_ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$LOCAL_ENV_FILE"
  set +a
fi

AUTOSTART_MODE="${POTVRDE_AUTOSTART_ENABLED:-${AUTOSTART_MODE:-ask}}"
usage() {
  cat <<USAGE
Install Uvjerenja Terminal

Usage:
  ./install_uvjerenja_terminal.sh [options]

Options:
  --autostart       Start the kiosk automatically when the Raspberry Pi desktop opens
  --no-autostart    Disable the kiosk desktop autostart entry
  -h, --help        Show this help

Without an option, the installer asks on an interactive terminal. During non-interactive
updates it leaves the current autostart setting unchanged.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --autostart) AUTOSTART_MODE="1" ;;
    --no-autostart) AUTOSTART_MODE="0" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

INSTALL_ROOT="/opt/$APP_ID"
SRC_DST="$INSTALL_ROOT/src"
VENV_DIR="$INSTALL_ROOT/venv"
ETC_DIR="/etc/$APP_ID"
ENV_FILE="$ETC_DIR/$APP_ID.env"
VAR_DIR="/var/lib/$APP_ID"
JOBS_DIR="$VAR_DIR/jobs"
LAUNCHER="/usr/local/bin/${APP_ID}-run"
DESKTOP_FILE="/home/$INSTALL_USER/Desktop/${APP_TITLE}.desktop"
OLD_DESKTOP_FILE_SAFE="/home/$INSTALL_USER/Desktop/${APP_ID}.desktop"
MENU_FILE="/home/$INSTALL_USER/.local/share/applications/${APP_ID}.desktop"
USER_AUTOSTART_DIR="/home/$INSTALL_USER/.config/autostart"
USER_AUTOSTART_FILE="$USER_AUTOSTART_DIR/${APP_ID}.desktop"
AUTOSTART_FILE="/home/$INSTALL_USER/.config/lxsession/LXDE-pi/autostart"
SERVICE_FILE="/etc/systemd/system/$APP_ID.service"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1"; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || { log_err "Missing command: $1"; exit 1; }; }

if [[ ! -d "$SRC_ROOT/project" ]]; then
  log_err "Run this script from the project root (must contain ./project). Current: $SRC_ROOT"
  exit 1
fi

require_cmd sudo

APT_PACKAGES=(
  python3 python3-venv python3-pip python3-tk
  rsync cups cups-bsd hplip printer-driver-hpcups
  libreoffice-core libreoffice-writer fonts-dejavu fonts-noto-core
  libglib2.0-bin desktop-file-utils
  x11-xserver-utils xinput xserver-xorg-input-libinput xinput-calibrator
)

log_info "Installing system dependencies..."
sudo apt update
sudo apt install -y "${APT_PACKAGES[@]}"
log_ok "APT dependencies installed."

log_info "Enabling CUPS..."
sudo systemctl enable --now cups
sudo usermod -aG lpadmin "$INSTALL_USER" || true
log_ok "CUPS enabled."

log_info "Creating directories..."
sudo mkdir -p "$INSTALL_ROOT" "$ETC_DIR" "$JOBS_DIR" "/home/$INSTALL_USER/.local/share/applications" "/home/$INSTALL_USER/.config" "/home/$INSTALL_USER/Desktop"
sudo chown -R "$INSTALL_USER":"$INSTALL_USER" "$INSTALL_ROOT" "$VAR_DIR" "/home/$INSTALL_USER/.local" "/home/$INSTALL_USER/.config" "/home/$INSTALL_USER/Desktop"
log_ok "Directories ready."

log_info "Deploying code to $SRC_DST ..."
sudo mkdir -p "$SRC_DST"
sudo rsync -a --delete --exclude '.git' --exclude '.env' --exclude '__pycache__' --exclude '*.pyc' "$SRC_ROOT/" "$SRC_DST/"
sudo chown -R "$INSTALL_USER":"$INSTALL_USER" "$SRC_DST"
log_ok "Code deployed."

log_info "Creating venv at $VENV_DIR ..."
sudo -u "$INSTALL_USER" python3 -m venv "$VENV_DIR"
log_info "Installing Python requirements..."
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/pip" install -r "$SRC_DST/requirements.txt"
log_ok "Python deps installed in venv."

DETECTED_PRINTER=""
if [[ -z "$DEFAULT_PRINTER_NAME" && "$ENABLE_PRINTER_AUTODETECT" == "1" ]]; then
  DETECTED_PRINTER="$(lpstat -d 2>/dev/null | awk -F': ' '{print $2}' || true)"
fi
PRINTER_TO_WRITE="$DEFAULT_PRINTER_NAME"
if [[ -z "$PRINTER_TO_WRITE" && -n "$DETECTED_PRINTER" ]]; then
  PRINTER_TO_WRITE="$DETECTED_PRINTER"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  log_info "Creating env file: $ENV_FILE"
  sudo tee "$ENV_FILE" >/dev/null <<EOF
POTVRDE_APP_ID="$APP_ID"
POTVRDE_APP_TITLE="$APP_TITLE"
POTVRDE_PRINTER_NAME="$PRINTER_TO_WRITE"
POTVRDE_VAR_DIR="$VAR_DIR"
POTVRDE_DEBUG_MODE="0"
POTVRDE_PRINTER_CHECK_RETRY_ATTEMPTS="5"
POTVRDE_PRINTER_CHECK_RETRY_DELAY_SECONDS="3"
POTVRDE_PRINT_RETRY_ATTEMPTS="3"
POTVRDE_PRINT_RETRY_DELAY_SECONDS="3"
POTVRDE_TELEGRAM_ENABLED="1"
POTVRDE_TELEGRAM_BOT_TOKEN="${POTVRDE_TELEGRAM_BOT_TOKEN:-}"
POTVRDE_TELEGRAM_ALLOWED_USER_ID="${POTVRDE_TELEGRAM_ALLOWED_USER_ID:-6598155929}"
POTVRDE_TELEGRAM_ERROR_NOTIFICATIONS="1"
POTVRDE_TELEGRAM_STATUS_NOTIFICATIONS="1"
POTVRDE_TELEGRAM_NOTIFY_ONLINE="1"
POTVRDE_TELEGRAM_NOTIFY_PRINT_JOBS="1"
POTVRDE_TELEGRAM_NOTIFY_UPDATE_EVENTS="1"
POTVRDE_TELEGRAM_ERROR_COOLDOWN_SECONDS="60"
POTVRDE_TELEGRAM_POLL_TIMEOUT="25"
POTVRDE_TELEGRAM_POLL_BACKOFF_MAX_SECONDS="60"
POTVRDE_TELEGRAM_SEND_RETRY_ATTEMPTS="5"
POTVRDE_TELEGRAM_SEND_RETRY_DELAY_SECONDS="2"
POTVRDE_TELEGRAM_COMMAND_TIMEOUT="900"
POTVRDE_TELEGRAM_REMOTE_COMMANDS_ENABLED="1"
POTVRDE_REBOOT_COMMAND="sudo -n shutdown -r now"
POTVRDE_RELAUNCH_AFTER_UPDATE="1"
POTVRDE_RELAUNCH_COMMAND="$LAUNCHER"
POTVRDE_AUTOSTART_ENABLED="$AUTOSTART_MODE"
POTVRDE_NETWORK_CHECK_HOST="api.telegram.org"
POTVRDE_NETWORK_CHECK_PORT="443"
POTVRDE_NETWORK_CHECK_TIMEOUT="5"
POTVRDE_NETWORK_RECONNECT_COMMAND=""
POTVRDE_CUPS_RESTART_COMMAND="sudo -n systemctl restart cups"
POTVRDE_TELEGRAM_LOG_TAIL_LINES="80"
POTVRDE_UPDATE_REPO_URL="${POTVRDE_UPDATE_REPO_URL:-https://github.com/velimirpaleksic/Raspberry-Pi.git}"
POTVRDE_UPDATE_SOURCE_DIR="${POTVRDE_UPDATE_SOURCE_DIR:-/home/$INSTALL_USER/Raspberry-Pi}"
POTVRDE_UPDATE_BRANCH="${POTVRDE_UPDATE_BRANCH:-}"
POTVRDE_UPDATE_COMMAND="${POTVRDE_UPDATE_COMMAND:-bash ./update_uvjerenja_terminal.sh}"
EOF
  log_ok "Env file created."
else
  log_info "Env file already exists (keeping): $ENV_FILE"
fi
sudo chown "$INSTALL_USER":"$INSTALL_USER" "$ENV_FILE"
sudo chmod 0600 "$ENV_FILE"

log_info "Installing manual launcher: $LAUNCHER"
sudo tee "$LAUNCHER" >/dev/null <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ -f "$ENV_FILE" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi
export PYTHONUNBUFFERED=1
LOG_DIR="$VAR_DIR/logs"
mkdir -p "\$LOG_DIR"
cd "$SRC_DST"
if [[ -z "\${DISPLAY:-}" ]]; then
  echo "[ERROR] No GUI display detected. Start the Raspberry Pi desktop first, then open '$APP_TITLE' from the desktop icon/menu or run this script from a desktop terminal." | tee -a "\$LOG_DIR/manual-launch.log"
  exit 2
fi
exec "$VENV_DIR/bin/python" -B -m project.core.app >>"\$LOG_DIR/manual-launch.log" 2>&1
EOF
sudo chmod 0755 "$LAUNCHER"

log_info "Creating desktop shortcut and applications menu entry..."
sudo -u "$INSTALL_USER" tee "$DESKTOP_FILE" >/dev/null <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_TITLE
Comment=Ručno pokretanje terminala za uvjerenja
Exec=$LAUNCHER
Icon=utilities-terminal
Terminal=false
Categories=Office;Education;
EOF
sudo -u "$INSTALL_USER" chmod 0755 "$DESKTOP_FILE"
sudo rm -f "$OLD_DESKTOP_FILE_SAFE"
if command -v gio >/dev/null 2>&1; then
  sudo -u "$INSTALL_USER" gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
fi
sudo -u "$INSTALL_USER" tee "$MENU_FILE" >/dev/null <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_TITLE
Comment=Ručno pokretanje terminala za uvjerenja
Exec=$LAUNCHER
Icon=utilities-terminal
Terminal=false
Categories=Office;Education;
EOF

decide_autostart_mode() {
  local mode="${AUTOSTART_MODE,,}"
  case "$mode" in
    1|true|yes|y|on|enable|enabled)
      echo "enable"
      return 0
      ;;
    0|false|no|n|off|disable|disabled)
      echo "disable"
      return 0
      ;;
    ask|prompt|"")
      if [[ -t 0 ]]; then
        printf '\n' >&2
        read -r -p "Start '$APP_TITLE' automatically when the Raspberry Pi desktop opens? [y/N]: " answer
        case "${answer,,}" in
          y|yes) echo "enable" ;;
          *) echo "disable" ;;
        esac
      else
        echo "keep"
      fi
      return 0
      ;;
    *)
      echo "[INFO] Unknown AUTOSTART_MODE='$AUTOSTART_MODE'. Leaving autostart unchanged." >&2
      echo "keep"
      return 0
      ;;
  esac
}

install_autostart_entry() {
  local mode
  mode="$(decide_autostart_mode)"

  case "$mode" in
    enable)
      log_info "Enabling desktop autostart..."
      sudo mkdir -p "$USER_AUTOSTART_DIR"
      sudo chown "$INSTALL_USER":"$INSTALL_USER" "$USER_AUTOSTART_DIR"
      sudo -u "$INSTALL_USER" tee "$USER_AUTOSTART_FILE" >/dev/null <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$APP_TITLE
Comment=Automatsko pokretanje terminala za uvjerenja
Exec=$LAUNCHER
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
      sudo -u "$INSTALL_USER" chmod 0644 "$USER_AUTOSTART_FILE"
      log_ok "Autostart enabled: $USER_AUTOSTART_FILE"
      ;;
    disable)
      log_info "Disabling desktop autostart..."
      sudo rm -f "$USER_AUTOSTART_FILE"
      log_ok "Autostart disabled."
      ;;
    keep)
      log_info "Autostart unchanged. Use --autostart or --no-autostart to change it."
      ;;
  esac
}

install_autostart_entry

if [[ -f "$AUTOSTART_FILE" ]]; then
  log_info "Removing old autostart launcher entries..."
  sudo -u "$INSTALL_USER" sed -i '\|/usr/local/bin/uvjerenja-terminal-launch|d;\|/usr/local/bin/uvjerenja-terminal-run|d;\|uvjerenja-terminal|d' "$AUTOSTART_FILE" || true
fi
if [[ -f "$SERVICE_FILE" ]]; then
  log_info "Disabling old systemd GUI service..."
  sudo systemctl disable --now "$APP_ID.service" || true
  sudo rm -f "$SERVICE_FILE"
  sudo systemctl daemon-reload
fi

log_ok "Install complete."
echo
if [[ -n "$PRINTER_TO_WRITE" ]]; then
  echo "Printer: koristi se '$PRINTER_TO_WRITE'."
else
  echo "Printer: koristi se CUPS default printer."
fi
echo "Use the desktop shortcut '$APP_TITLE' or run: $LAUNCHER"
echo "Autostart option: run installer with --autostart or --no-autostart to change boot behavior."
echo "Do NOT launch from SSH/TTY unless you are forwarding a desktop DISPLAY."
echo "Printer logs and launcher logs: $VAR_DIR/logs"
