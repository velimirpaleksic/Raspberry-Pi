#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_ID="${POTVRDE_APP_ID:-uvjerenja-terminal}"
VAR_DIR="${POTVRDE_VAR_DIR:-/var/lib/$APP_ID}"
FIRSTBOOT_DIR="$VAR_DIR/firstboot"
HEALTH_JSON="$FIRSTBOOT_DIR/firstboot_health.json"
MANIFEST_JSON="$FIRSTBOOT_DIR/device_manifest.json"
COMPLETE_FLAG="$FIRSTBOOT_DIR/complete.flag"

mkdir -p "$FIRSTBOOT_DIR"

cd "$PROJECT_ROOT"

python -m project.core.maintenance_cli health --notify-on-failure > "$HEALTH_JSON" || true

python - <<'PY' "$MANIFEST_JSON" "$HEALTH_JSON"
from __future__ import annotations
import json, os, platform, socket, sys, time
from pathlib import Path
manifest_path = Path(sys.argv[1])
health_path = Path(sys.argv[2])
health = {}
if health_path.exists():
    try:
        health = json.loads(health_path.read_text(encoding='utf-8'))
    except Exception:
        health = {}
manifest = {
    'generated_at_epoch': int(time.time()),
    'hostname': socket.gethostname(),
    'platform': platform.platform(),
    'machine': platform.machine(),
    'python_version': platform.python_version(),
    'app_id': os.getenv('POTVRDE_APP_ID', 'uvjerenja-terminal'),
    'var_dir': os.getenv('POTVRDE_VAR_DIR', ''),
    'health_ok': bool(health.get('ok')),
    'health_summary': health.get('summary', ''),
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
PY

date -Is > "$COMPLETE_FLAG"

systemctl disable uvjerenja-firstboot-finalize.service >/dev/null 2>&1 || true
systemctl daemon-reload >/dev/null 2>&1 || true

echo "First boot finalize complete. Artifacts written to $FIRSTBOOT_DIR"
