#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
cd "$APP_ROOT"
exec "$PYTHON_BIN" -B -m project.core.maintenance_cli cleanup
