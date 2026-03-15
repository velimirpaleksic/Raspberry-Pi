#!/usr/bin/env bash
set -euo pipefail

APP_ID="${POTVRDE_APP_ID:-uvjerenja-terminal}"
VAR_DIR="${POTVRDE_VAR_DIR:-/var/lib/${APP_ID}}"
SERVICE_NAME="${POTVRDE_SYSTEMD_SERVICE:-${APP_ID}.service}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="/var/tmp/${APP_ID}_factory_reset_${STAMP}"

if [[ "${1:-}" != "--yes" ]]; then
  echo "Ova skripta briše lokalnu runtime bazu/settings/jobs iz: ${VAR_DIR}"
  echo "Za izvršenje pokreni: $0 --yes"
  exit 2
fi

mkdir -p "${BACKUP_DIR}"
if [[ -d "${VAR_DIR}" ]]; then
  echo "[factory-reset] pravim sigurnosnu kopiju u ${BACKUP_DIR}"
  cp -a "${VAR_DIR}"/. "${BACKUP_DIR}"/ || true
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl stop "${SERVICE_NAME}" || true
fi

rm -rf "${VAR_DIR}/jobs"/* 2>/dev/null || true
rm -rf "${VAR_DIR}/exports"/* 2>/dev/null || true
rm -rf "${VAR_DIR}/logs"/* 2>/dev/null || true
rm -rf "${VAR_DIR}/db"/* 2>/dev/null || true
mkdir -p "${VAR_DIR}/jobs" "${VAR_DIR}/exports" "${VAR_DIR}/logs" "${VAR_DIR}/db"

if command -v systemctl >/dev/null 2>&1; then
  systemctl start "${SERVICE_NAME}" || true
fi

echo "[factory-reset] gotovo"
echo "- backup: ${BACKUP_DIR}"
echo "- aplikacija će na sljedećem startu ponovo kreirati bazu i otvoriti setup wizard"
