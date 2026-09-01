#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${DISPLAY:-}" ]]; then
  echo "[ERROR] No GUI display detected. Open the Raspberry Pi desktop first, then run this script from a desktop terminal."
  exit 2
fi
if [[ ! -d "$ROOT_DIR/.venv" ]]; then
  python3 -m venv "$ROOT_DIR/.venv"
  "$ROOT_DIR/.venv/bin/pip" install --upgrade pip setuptools wheel
  "$ROOT_DIR/.venv/bin/pip" install -r "$ROOT_DIR/requirements.txt"
fi
cd "$ROOT_DIR"
exec "$ROOT_DIR/.venv/bin/python" -B -m project.core.app
