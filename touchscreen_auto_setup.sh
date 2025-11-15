#!/bin/bash
set -e

echo "[INFO] Checking current session..."
if [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    echo "[WARN] Wayland detected — touchscreen will NOT work."
    echo "[INFO] Switching system to X11..."

    sudo sed -i 's/#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf || true
    sudo sed -i 's/WaylandEnable=true/WaylandEnable=false/' /etc/gdm3/custom.conf || true

    echo "[INFO] Restarting display manager..."
    sudo systemctl restart gdm3 || true
    echo "[INFO] Re-login and run this command again."
    exit 0
else
    echo "[SUCCESS] X11 is active — good."
fi

echo "[INFO] Installing touchscreen packages..."
sudo apt update
sudo apt install -y xserver-xorg-input-libinput xinput-calibrator

echo "[INFO] Detecting touchscreen..."
TOUCH_NAME=$(xinput list --name-only | grep -i "SMART" || true)

if [ -z "$TOUCH_NAME" ]; then
    echo "[ERROR] Touchscreen not detected. Make sure USB cable is connected."
    exit 1
fi

echo "[SUCCESS] Detected touchscreen: $TOUCH_NAME"

echo "[INFO] Running calibration..."
CALIB_OUTPUT=$(xinput_calibrator)

echo "[INFO] Saving calibration..."
sudo mkdir -p /etc/X11/xorg.conf.d
echo "$CALIB_OUTPUT" | sudo tee /etc/X11/xorg.conf.d/99-calibration.conf > /dev/null

echo "[SUCCESS] Calibration saved."

echo "[INFO] Rebooting system..."
sudo reboot