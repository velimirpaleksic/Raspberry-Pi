#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_ROOT="$PROJECT_ROOT/dist/prebuilt-release-$TS"
BUNDLE_NAME="prebuilt-release-$TS.tar.gz"
mkdir -p "$OUT_ROOT"

GIT_COMMIT="$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo 'no-git')"
APP_ID="${POTVRDE_APP_ID:-uvjerenja-terminal}"

mkdir -p "$OUT_ROOT/deploy/systemd" "$OUT_ROOT/deploy/prebuilt" "$OUT_ROOT/scripts" "$OUT_ROOT/instructions"
cp "$PROJECT_ROOT"/deploy/systemd/* "$OUT_ROOT/deploy/systemd/" 2>/dev/null || true
cp "$PROJECT_ROOT"/deploy/prebuilt/* "$OUT_ROOT/deploy/prebuilt/" 2>/dev/null || true
cp "$PROJECT_ROOT"/scripts/first_boot_finalize.sh "$OUT_ROOT/scripts/"
cp "$PROJECT_ROOT"/scripts/prepare_image_for_clone.sh "$OUT_ROOT/scripts/"
cp "$PROJECT_ROOT"/scripts/factory_reset_for_redeploy.sh "$OUT_ROOT/scripts/"
cp "$PROJECT_ROOT"/scripts/deployment_acceptance_check.sh "$OUT_ROOT/scripts/"
cp "$PROJECT_ROOT"/instructions/prebuilt-image-runbook.md "$OUT_ROOT/instructions/" 2>/dev/null || true
cp "$PROJECT_ROOT"/instructions/prebuilt-image-workflow.md "$OUT_ROOT/instructions/" 2>/dev/null || true
cp "$PROJECT_ROOT"/instructions/prebuilt-image-factory-flow.md "$OUT_ROOT/instructions/" 2>/dev/null || true
cp "$PROJECT_ROOT"/README.md "$OUT_ROOT/README.md"

cat > "$OUT_ROOT/release_manifest.json" <<JSON
{
  "generated_at": "$(date -Is)",
  "app_id": "$APP_ID",
  "git_commit": "$GIT_COMMIT",
  "bundle": "$BUNDLE_NAME",
  "contents": [
    "deploy/systemd",
    "deploy/prebuilt",
    "scripts/first_boot_finalize.sh",
    "scripts/prepare_image_for_clone.sh",
    "scripts/factory_reset_for_redeploy.sh",
    "scripts/deployment_acceptance_check.sh",
    "instructions/prebuilt-image-runbook.md",
    "instructions/prebuilt-image-workflow.md",
    "instructions/prebuilt-image-factory-flow.md"
  ]
}
JSON

(
  cd "$PROJECT_ROOT/dist"
  tar -czf "$BUNDLE_NAME" "$(basename "$OUT_ROOT")"
)

echo "Release bundle created: $PROJECT_ROOT/dist/$BUNDLE_NAME"
