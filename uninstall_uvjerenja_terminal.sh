#!/usr/bin/env bash
set -euo pipefail

APP_ID="${APP_ID:-uvjerenja-terminal}"
APP_TITLE="${APP_TITLE:-Uvjerenja Terminal}"
INSTALL_USER="${INSTALL_USER:-${SUDO_USER:-$USER}}"

PURGE=0
REMOVE_SOURCE=0
REMOVE_APT_DEPS=0
ASSUME_YES=0

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log_info() { echo -e "${YELLOW}[INFO]${NC} $1"; }
log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()  { echo -e "${RED}[ERROR]${NC} $1" >&2; }

usage() {
  cat <<USAGE
Uninstall $APP_TITLE

Usage:
  ./uninstall_uvjerenja_terminal.sh [options]

Options:
  -y, --yes              Do not ask for confirmation
  --purge                Also remove config and saved app data:
                         /etc/$APP_ID and /var/lib/$APP_ID
  --remove-source        Also remove the update source repo directory from
                         POTVRDE_UPDATE_SOURCE_DIR, if safe to remove
  --remove-apt-deps      Also remove APT packages installed by the installer
                         WARNING: this may remove printer/LibreOffice packages
                         used by other apps
  -h, --help             Show this help

Default uninstall removes only app install files, launchers, desktop/menu
shortcuts, old autostart entries, and old systemd service files. It keeps
saved PDFs, settings, logs, and the env file unless --purge is used.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) ASSUME_YES=1 ;;
    --purge) PURGE=1 ;;
    --remove-source) REMOVE_SOURCE=1 ;;
    --remove-apt-deps) REMOVE_APT_DEPS=1 ;;
    -h|--help) usage; exit 0 ;;
    *) log_err "Unknown option: $1"; usage; exit 1 ;;
  esac
  shift
done

if [[ "$INSTALL_USER" == "root" && -n "${SUDO_USER:-}" && "${SUDO_USER:-}" != "root" ]]; then
  INSTALL_USER="$SUDO_USER"
fi

if ! id "$INSTALL_USER" >/dev/null 2>&1; then
  log_err "Install user does not exist: $INSTALL_USER"
  echo "Run with: INSTALL_USER=pi ./uninstall_uvjerenja_terminal.sh"
  exit 1
fi

SUDO=()
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  if ! command -v sudo >/dev/null 2>&1; then
    log_err "sudo is required when not running as root."
    exit 1
  fi
  SUDO=(sudo)
fi

ETC_DIR="/etc/$APP_ID"
ENV_FILE="$ETC_DIR/$APP_ID.env"
INSTALL_ROOT="/opt/$APP_ID"
SRC_DST="$INSTALL_ROOT/src"
VENV_DIR="$INSTALL_ROOT/venv"
VAR_DIR="/var/lib/$APP_ID"
LAUNCHER="/usr/local/bin/${APP_ID}-run"
OLD_LAUNCHER="/usr/local/bin/${APP_ID}-launch"
DESKTOP_DIR="/home/$INSTALL_USER/Desktop"
DESKTOP_FILE="$DESKTOP_DIR/${APP_TITLE}.desktop"
OLD_DESKTOP_FILE="$DESKTOP_DIR/${APP_ID}.desktop"
MENU_FILE="/home/$INSTALL_USER/.local/share/applications/${APP_ID}.desktop"
USER_AUTOSTART_DIR="/home/$INSTALL_USER/.config/autostart"
USER_AUTOSTART_FILE="$USER_AUTOSTART_DIR/${APP_ID}.desktop"
LXDE_AUTOSTART_FILE="/home/$INSTALL_USER/.config/lxsession/LXDE-pi/autostart"
SYSTEM_LXDE_AUTOSTART_FILE="/etc/xdg/lxsession/LXDE-pi/autostart"
SERVICE_FILE="/etc/systemd/system/$APP_ID.service"
SOURCE_DIR="/home/$INSTALL_USER/Raspberry-Pi"

# Read the installed env after base paths are known. Do not print secrets.
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  APP_TITLE="${POTVRDE_APP_TITLE:-$APP_TITLE}"
  VAR_DIR="${POTVRDE_VAR_DIR:-$VAR_DIR}"
  SOURCE_DIR="${POTVRDE_UPDATE_SOURCE_DIR:-$SOURCE_DIR}"
  DESKTOP_FILE="$DESKTOP_DIR/${APP_TITLE}.desktop"
fi

APT_PACKAGES=(
  python3 python3-venv python3-pip python3-tk
  rsync cups cups-bsd hplip printer-driver-hpcups
  libreoffice-core libreoffice-writer fonts-dejavu fonts-noto-core
  libglib2.0-bin desktop-file-utils
  x11-xserver-utils xinput xserver-xorg-input-libinput xinput-calibrator
)

remove_path() {
  local path="$1"
  if [[ -e "$path" || -L "$path" ]]; then
    "${SUDO[@]}" rm -rf -- "$path"
    log_ok "Removed: $path"
  else
    log_info "Not found, skipped: $path"
  fi
}

clean_autostart_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    log_info "Not found, skipped: $file"
    return 0
  fi

  log_info "Cleaning autostart entries in: $file"
  "${SUDO[@]}" sed -i \
    -e "\\|/usr/local/bin/${APP_ID}-run|d" \
    -e "\\|/usr/local/bin/${APP_ID}-launch|d" \
    -e "\\|${APP_ID}|d" \
    -e "\\|${APP_TITLE}|d" \
    "$file" || true
  log_ok "Autostart cleaned: $file"
}

confirm() {
  if [[ "$ASSUME_YES" == "1" ]]; then
    return 0
  fi

  echo
  echo "This will uninstall: $APP_TITLE ($APP_ID)"
  echo
  echo "Will remove:"
  echo "  - $INSTALL_ROOT"
  echo "  - $LAUNCHER"
  echo "  - $OLD_LAUNCHER"
  echo "  - $DESKTOP_FILE"
  echo "  - $OLD_DESKTOP_FILE"
  echo "  - $MENU_FILE"
  echo "  - $USER_AUTOSTART_FILE"
  echo "  - $SERVICE_FILE"
  echo "  - matching old autostart lines"

  if [[ "$PURGE" == "1" ]]; then
    echo "  - $ETC_DIR"
    echo "  - $VAR_DIR"
  else
    echo
    echo "Will keep unless --purge is used:"
    echo "  - $ETC_DIR"
    echo "  - $VAR_DIR"
  fi

  if [[ "$REMOVE_SOURCE" == "1" ]]; then
    echo
    echo "Will also try to remove source repo:"
    echo "  - $SOURCE_DIR"
  fi

  if [[ "$REMOVE_APT_DEPS" == "1" ]]; then
    echo
    echo "Will also remove APT packages installed by the installer."
    echo "This can affect printers, LibreOffice, Python venv support, and X input tools."
  fi

  echo
  read -r -p "Continue? Type 'yes' to uninstall: " answer
  [[ "$answer" == "yes" ]] || { log_info "Cancelled."; exit 0; }
}

stop_running_app() {
  log_info "Stopping old service/processes if they exist..."

  if command -v systemctl >/dev/null 2>&1; then
    "${SUDO[@]}" systemctl disable --now "$APP_ID.service" >/dev/null 2>&1 || true
  fi

  # Only target the installed app paths. Avoid killing unrelated Python apps.
  "${SUDO[@]}" pkill -f "${VENV_DIR}/bin/python.*-m project\.core\.app" >/dev/null 2>&1 || true
  "${SUDO[@]}" pkill -f "cd ${SRC_DST}.*project\.core\.app" >/dev/null 2>&1 || true
  "${SUDO[@]}" pkill -f "${LAUNCHER}" >/dev/null 2>&1 || true

  log_ok "Stop step complete."
}

remove_systemd_service() {
  if command -v systemctl >/dev/null 2>&1; then
    "${SUDO[@]}" systemctl disable --now "$APP_ID.service" >/dev/null 2>&1 || true
  fi
  remove_path "$SERVICE_FILE"
  if command -v systemctl >/dev/null 2>&1; then
    "${SUDO[@]}" systemctl daemon-reload >/dev/null 2>&1 || true
    "${SUDO[@]}" systemctl reset-failed "$APP_ID.service" >/dev/null 2>&1 || true
  fi
}

remove_source_repo_if_requested() {
  if [[ "$REMOVE_SOURCE" != "1" ]]; then
    return 0
  fi

  if [[ -z "$SOURCE_DIR" || "$SOURCE_DIR" == "/" ]]; then
    log_warn "Unsafe source dir value, skipped: $SOURCE_DIR"
    return 0
  fi

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local source_real script_real
  source_real="$(realpath -m "$SOURCE_DIR")"
  script_real="$(realpath -m "$script_dir")"

  if [[ "$script_real" == "$source_real" || "$script_real" == "$source_real"/* ]]; then
    log_warn "Skipping source removal because this script is running inside it: $SOURCE_DIR"
    log_warn "After uninstall finishes, delete it manually if you still want: rm -rf '$SOURCE_DIR'"
    return 0
  fi

  remove_path "$SOURCE_DIR"
}

remove_apt_deps_if_requested() {
  if [[ "$REMOVE_APT_DEPS" != "1" ]]; then
    return 0
  fi

  log_warn "Removing APT packages. This may affect other printer/office/desktop workflows."
  "${SUDO[@]}" apt purge -y "${APT_PACKAGES[@]}" || true
  "${SUDO[@]}" apt autoremove -y || true
  log_ok "APT dependency removal step complete."
}

confirm
stop_running_app
remove_systemd_service

log_info "Removing launchers and shortcuts..."
remove_path "$LAUNCHER"
remove_path "$OLD_LAUNCHER"
remove_path "$DESKTOP_FILE"
remove_path "$OLD_DESKTOP_FILE"
remove_path "$MENU_FILE"
remove_path "$USER_AUTOSTART_FILE"

clean_autostart_file "$LXDE_AUTOSTART_FILE"
clean_autostart_file "$SYSTEM_LXDE_AUTOSTART_FILE"

log_info "Removing installed app files..."
remove_path "$INSTALL_ROOT"

if [[ "$PURGE" == "1" ]]; then
  log_info "Purging config and saved app data..."
  remove_path "$ETC_DIR"
  remove_path "$VAR_DIR"
else
  log_info "Keeping config/data. Use --purge to remove them too:"
  echo "  $ETC_DIR"
  echo "  $VAR_DIR"
fi

remove_source_repo_if_requested
remove_apt_deps_if_requested

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "/home/$INSTALL_USER/.local/share/applications" >/dev/null 2>&1 || true
fi

log_ok "Uninstall complete."
echo
if [[ "$PURGE" != "1" ]]; then
  echo "Saved PDFs/settings/logs were kept in: $VAR_DIR"
  echo "Env config was kept in: $ETC_DIR"
  echo "For full removal, run: ./uninstall_uvjerenja_terminal.sh --purge -y"
fi
