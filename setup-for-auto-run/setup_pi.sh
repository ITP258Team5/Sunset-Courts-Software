#!/bin/bash
# Sunset Courts — Pi Setup Script
# Run once: sudo bash setup_pi.sh

set -e

echo "=== Sunset Courts Pi Setup ==="

# Install Flask if needed
pip3 install flask --break-system-packages -q 2>/dev/null || pip3 install flask -q

# Initialize database if it doesn't exist
if [ ! -f /home/pi/sunset-courts/sunset_courts.db ]; then
    echo "Initializing database..."
    cd /home/pi/sunset-courts && python3 init_db.py
fi

# Set debug=False for production
sed -i 's/debug=True/debug=False/' /home/pi/sunset-courts/app.py

# Install systemd service (runs Flask on boot)
cp /home/pi/sunset-courts/sunset-courts.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable sunset-courts
systemctl start sunset-courts

# Install browser autostart (opens Chromium in kiosk mode)
AUTOSTART_DIR="/home/pi/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cp /home/pi/sunset-courts/sunset-courts-browser.desktop "$AUTOSTART_DIR/"
chown pi:pi "$AUTOSTART_DIR/sunset-courts-browser.desktop"

echo ""
echo "=== Setup Complete ==="
echo "  Flask service: enabled and running"
echo "  Browser kiosk: will open on next desktop login"
echo "  URL: http://localhost:5000"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status sunset-courts   # check status"
echo "    sudo systemctl restart sunset-courts   # restart app"
echo "    sudo systemctl stop sunset-courts      # stop app"
echo ""
echo "  Reboot now to test full startup flow."
