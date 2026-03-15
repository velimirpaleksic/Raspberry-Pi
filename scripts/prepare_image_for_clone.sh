#!/usr/bin/env bash
set -euo pipefail

APP_ID="${POTVRDE_APP_ID:-uvjerenja-terminal}"
VAR_DIR="${POTVRDE_VAR_DIR:-/var/lib/${APP_ID}}"
SERVICE_NAME="${POTVRDE_SYSTEMD_SERVICE:-${APP_ID}.service}"

if [[ "${1:-}" != "--yes" ]]; then
  echo "Ova skripta priprema image za kloniranje: cleanup + čišćenje runtime podataka terminala."
  echo "Za izvršenje pokreni: $0 --yes"
  exit 2
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl stop "${SERVICE_NAME}" || true
fi

python -m project.core.maintenance_cli cleanup || true
rm -rf "${VAR_DIR}/jobs"/* 2>/dev/null || true
rm -rf "${VAR_DIR}/exports"/* 2>/dev/null || true
rm -rf "${VAR_DIR}/logs"/* 2>/dev/null || true
rm -rf "${VAR_DIR}/db"/* 2>/dev/null || true
mkdir -p "${VAR_DIR}/jobs" "${VAR_DIR}/exports" "${VAR_DIR}/logs" "${VAR_DIR}/db"

rm -f ~/.bash_history 2>/dev/null || true
history -c 2>/dev/null || true

echo "[prepare-image] app runtime je očišćen."
echo "Ručno još provjeri:"
echo "- da li želiš promijeniti hostname prije kloniranja"
echo "- da li želiš ponovo generisati machine-id na prvom bootu"
echo "- da li image nakon gašenja ide u read-only/clone workflow koji koristiš"
