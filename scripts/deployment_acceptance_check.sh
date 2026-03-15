#!/usr/bin/env bash
set -euo pipefail

APP_ID="${POTVRDE_APP_ID:-uvjerenja-terminal}"
SERVICE_NAME="${POTVRDE_SYSTEMD_SERVICE:-${APP_ID}.service}"

pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*"; }
fail() { echo "[FAIL] $*"; }

rc=0

if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet "${SERVICE_NAME}"; then
    pass "systemd servis aktivan (${SERVICE_NAME})"
  else
    fail "systemd servis nije aktivan (${SERVICE_NAME})"
    rc=1
  fi
  if systemctl is-active --quiet cups; then
    pass "CUPS aktivan"
  else
    warn "CUPS nije aktivan"
  fi
  if systemctl is-active --quiet NetworkManager; then
    pass "NetworkManager aktivan"
  else
    warn "NetworkManager nije aktivan"
  fi
fi

if python -m project.core.maintenance_cli health; then
  pass "startup health check prošao"
else
  warn "startup health check prijavljuje problem"
fi

if command -v lpstat >/dev/null 2>&1; then
  lpstat -p || true
  lpstat -v || true
else
  warn "lpstat nije pronađen"
fi

echo "Acceptance check završen."
exit ${rc}
