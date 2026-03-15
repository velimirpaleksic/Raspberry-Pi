#!/usr/bin/env bash
set -euo pipefail
cat <<'EOF'
Recommended production hardening on Raspberry Pi:
- Enable automatic login only for the kiosk user.
- Use X11 session, not Wayland, if touchscreen calibration or xset/unclutter are required.
- Disable screen blanking and DPMS.
- Hide the cursor after inactivity.
- Keep Escape enabled only in debug mode.
- Remove or lock terminal shortcuts and desktop panels for the kiosk user session.
- Restrict SSH to your admin account only.
EOF
