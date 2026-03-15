# Raspberry Pi 3B+ Deployment Runbook

## Recommended OS
- Raspberry Pi OS (32-bit) with desktop
- Flash with Raspberry Pi Imager
- Use at least a 32 GB microSD card

## Before flashing
Prepare:
- Raspberry Pi 3B+
- 32 GB or larger microSD card
- Official PSU
- Touchscreen or temporary HDMI display
- USB keyboard/mouse for fallback
- Printer connected by USB or available on network
- Optional USB stick with DOCX template
- Network access if you want Telegram/remote alerts

## Imager settings
In Raspberry Pi Imager:
1. Choose Device: Raspberry Pi 3
2. Choose OS: Raspberry Pi OS (32-bit) with desktop
3. Choose Storage: your microSD card
4. Configure system settings:
   - Hostname: uvjerenja-terminal-01
   - Username/password: set a deployment password
   - Wireless LAN: prefill only if you already know the Wi-Fi
   - Locale / keyboard / timezone: set correctly
   - Enable SSH: yes (recommended)

## First boot
1. Insert SD card and boot the Pi
2. Connect network if not already configured
3. Open Terminal
4. Copy project to the Pi
5. Run install script:
   - `chmod +x install_uvjerenja_terminal.sh`
   - `./install_uvjerenja_terminal.sh`
6. Reboot if the installer asks or if desktop/session behaves oddly

## Services to verify
- Main kiosk service enabled
- Cleanup timer enabled
- Optional Telegram remote service enabled if you will use Telegram remote polling
- CUPS running
- NetworkManager running

## App first-run flow
After install / reboot:
1. Health screen appears
2. If setup is incomplete, open Setup Wizard
3. Complete in this order:
   - Admin PIN
   - Counter / year
   - Printer setup and per-printer test print
   - Template import/validation
   - General settings
   - Production readiness check

## Acceptance test
Verify:
- Health screen passes or only shows accepted warnings
- Production readiness is READY or READY_WITH_WARNINGS you understand
- Correct printer selected
- Test print succeeds on intended physical printer
- Active template validates successfully
- Form can be filled
- One real document prints end-to-end
- Attempt is visible in history
- Support bundle export works to USB
- Telegram test notification works (if enabled)
- Telegram remote `/status` works (if enabled)

## Optional Telegram remote
If using Telegram remote polling:
- Configure token/chat ID in Admin settings
- Test notifications
- Enable polling service example or run poll loop manually

## For cloning a golden image later
On a fully prepared reference Pi:
1. Run `scripts/deployment_acceptance_check.sh`
2. Run `sudo ./scripts/prepare_image_for_clone.sh --yes`
3. Power down cleanly
4. Clone the SD card / make your image

## For redeploying an existing device
Use UI factory mode or:
- `sudo ./scripts/factory_reset_for_redeploy.sh --yes`

This returns the terminal to first-boot style setup while allowing controlled cleanup.
