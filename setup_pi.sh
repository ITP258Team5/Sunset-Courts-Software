#!/bin/bash
# Sunset Courts — Pi Setup Script
# Run once: sudo bash setup_pi.sh

set -e

# Auto-detect install directory and user
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OWNER="$(stat -c '%U' "$SCRIPT_DIR")"
GROUP="$(stat -c '%G' "$SCRIPT_DIR")"

# Verify required files exist
REQUIRED="app.py init_db.py db.py"
MISSING=""
for f in $REQUIRED; do
    [ ! -f "$SCRIPT_DIR/$f" ] && MISSING="$MISSING $f"
done

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required files in $SCRIPT_DIR:"
    echo " $MISSING"
    echo ""
    echo "Run this script from the sunset-courts project directory."
    exit 1
fi

echo "=== Sunset Courts Pi Setup ==="
echo "  Directory: $SCRIPT_DIR"
echo "  User: $OWNER"
echo ""

# Install Flask if needed
pip3 install flask --break-system-packages -q 2>/dev/null || pip3 install flask -q

# Initialize database if it doesn't exist
if [ ! -f "$SCRIPT_DIR/sunset_courts.db" ]; then
    echo "Initializing database..."
    cd "$SCRIPT_DIR" && python3 init_db.py
fi

# Set debug=False for production
sed -i 's/debug=True/debug=False/' "$SCRIPT_DIR/app.py"

# Allow the app user to set the system clock without a password
# (needed for the time verification screen)
echo "$OWNER ALL=(ALL) NOPASSWD: /usr/bin/date" > /etc/sudoers.d/sunset-courts-date
chmod 440 /etc/sudoers.d/sunset-courts-date

# Generate systemd service file
cat > /etc/systemd/system/sunset-courts.service << EOF
[Unit]
Description=Sunset Courts Management System
After=multi-user.target

[Service]
Type=simple
User=$OWNER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/app.py
Restart=on-failure
RestartSec=5
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sunset-courts
systemctl start sunset-courts

# Install browser autostart (labwc on Raspberry Pi OS Bookworm)
LABWC_DIR="/home/$OWNER/.config/labwc"
mkdir -p "$LABWC_DIR"
KIOSK_CMD='bash -c "while ! curl -s http://localhost:5000 > /dev/null 2>&1; do sleep 1; done; chromium --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:5000" &'
grep -qF "localhost:5000" "$LABWC_DIR/autostart" 2>/dev/null || echo "$KIOSK_CMD" >> "$LABWC_DIR/autostart"
chown -R "$OWNER:$GROUP" "$LABWC_DIR"

echo ""
echo "=== Setup Complete ==="
echo "  Flask service: enabled and running"
echo "  Browser kiosk: will open on next desktop login"
echo "  Time setting:  passwordless sudo enabled for date command"
echo "  URL: http://localhost:5000"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status sunset-courts   # check status"
echo "    sudo systemctl restart sunset-courts   # restart app"
echo "    sudo systemctl stop sunset-courts      # stop app"
echo ""
echo "  Reboot now to test full startup flow."
