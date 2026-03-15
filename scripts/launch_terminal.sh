#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DISPLAY_VALUE="${DISPLAY:-:0}"
export DISPLAY="$DISPLAY_VALUE"

wait_for_x() {
  local tries=0
  while [[ $tries -lt 30 ]]; do
    if command -v xset >/dev/null 2>&1 && xset q >/dev/null 2>&1; then
      return 0
    fi
    tries=$((tries + 1))
    sleep 1
  done
  return 1
}

best_effort_x11_setup() {
  command -v xset >/dev/null 2>&1 && {
    xset s off || true
    xset -dpms || true
    xset s noblank || true
  }
  command -v unclutter >/dev/null 2>&1 && {
    pkill -f 'unclutter.*-root' >/dev/null 2>&1 || true
    nohup unclutter -idle 0.5 -root >/dev/null 2>&1 &
  }
}

wait_for_x || true
best_effort_x11_setup
cd "$APP_ROOT"
exec "$PYTHON_BIN" -B -m project.core.app
