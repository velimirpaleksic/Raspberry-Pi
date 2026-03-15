#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SLEEP_SECONDS="${SLEEP_SECONDS:-4}"

cd "$PROJECT_ROOT"
while true; do
  "$PYTHON_BIN" -m project.core.maintenance_cli telegram-poll-once --timeout-seconds 1 || true
  sleep "$SLEEP_SECONDS"
done
