# Production hardening

This version includes appliance-oriented deployment helpers:

- `scripts/launch_terminal.sh` waits for X11 on best effort, disables blanking, hides cursor, then starts the app.
- `scripts/maintenance_daily.sh` runs the built-in cleanup task.
- `project.core.maintenance_cli` exposes maintenance commands for systemd timers or manual SSH use.
- `install_uvjerenja_terminal.sh` now installs a more robust main service and a daily cleanup timer.

## Useful commands

```bash
sudo journalctl -u uvjerenja-terminal.service -f
systemctl status uvjerenja-terminal.service
systemctl status uvjerenja-terminal-cleanup.timer
/opt/uvjerenja-terminal/venv/bin/python -B -m project.core.maintenance_cli health --notify-on-failure
/opt/uvjerenja-terminal/venv/bin/python -B -m project.core.maintenance_cli cleanup
```

## Recommended Raspberry Pi setup

- X11 session for kiosk user
- automatic login for kiosk user only
- SSH restricted to your admin account
- desktop panels and terminal shortcuts removed for kiosk session
- `POTVRDE_DEBUG_MODE=0` in production
