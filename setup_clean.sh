#!/bin/bash
# Sunset Courts — Clean Setup
# Wipes all previous configuration and installs fresh.
# Run once: sudo bash setup_clean.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OWNER="$(stat -c '%U' "$SCRIPT_DIR")"
GROUP="$(stat -c '%G' "$SCRIPT_DIR")"

REQUIRED="app.py init_db.py db.py backup.sh"
for f in $REQUIRED; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "ERROR: $f not found in $SCRIPT_DIR"
        exit 1
    fi
done

echo "=== Sunset Courts — Clean Setup ==="
echo "  Directory: $SCRIPT_DIR"
echo "  User: $OWNER"
echo ""

# ── STEP 1: Remove everything old ──────────────────────────────
echo "[1/7] Removing old configuration..."
systemctl stop sunset-courts 2>/dev/null || true
systemctl disable sunset-courts 2>/dev/null || true
systemctl stop sunset-courts-backup.timer 2>/dev/null || true
systemctl disable sunset-courts-backup.timer 2>/dev/null || true
rm -f /etc/systemd/system/sunset-courts.service
rm -f /etc/systemd/system/sunset-courts-backup.service
rm -f /etc/systemd/system/sunset-courts-backup.timer
systemctl daemon-reload
rm -f "/home/$OWNER/.config/labwc/autostart"
rm -f "/home/$OWNER/.config/autostart/sunset-kiosk.desktop"
rm -f /etc/sudoers.d/sunset-courts-date
echo "  Done."

# ── STEP 2: Install Flask ──────────────────────────────────────
echo "[2/7] Installing Flask..."
pip3 install flask --break-system-packages -q 2>/dev/null || pip3 install flask -q
echo "  Done."

# ── STEP 3: Initialize database if needed ──────────────────────
if [ ! -f "$SCRIPT_DIR/sunset_courts.db" ]; then
    echo "[3/7] Initializing database..."
    cd "$SCRIPT_DIR" && python3 init_db.py
else
    echo "[3/7] Database exists, skipping."
fi

# ── STEP 4: Production settings ────────────────────────────────
echo "[4/7] Configuring production mode..."
sed -i 's/debug=True/debug=False/' "$SCRIPT_DIR/app.py"
chmod +x "$SCRIPT_DIR/backup.sh"
echo "$OWNER ALL=(ALL) NOPASSWD: /usr/bin/date" > /etc/sudoers.d/sunset-courts-date
chmod 440 /etc/sudoers.d/sunset-courts-date
echo "  Done."

# ── STEP 5: Create systemd service ────────────────────────────
echo "[5/7] Creating Flask service..."
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
echo "  Done."

# ── STEP 6: Create weekly backup timer ────────────────────────
echo "[6/7] Creating weekly backup timer..."

cat > /etc/systemd/system/sunset-courts-backup.service << EOF
[Unit]
Description=Sunset Courts Weekly Backup

[Service]
Type=oneshot
User=$OWNER
ExecStart=/bin/bash $SCRIPT_DIR/backup.sh
EOF

cat > /etc/systemd/system/sunset-courts-backup.timer << EOF
[Unit]
Description=Sunset Courts Weekly Backup Timer

[Timer]
OnCalendar=Sun *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable sunset-courts-backup.timer
systemctl start sunset-courts-backup.timer
echo "  Done. Backups run every Sunday at 3:00 AM."

# ── STEP 7: Create browser autostart ──────────────────────────
echo "[7/7] Creating browser autostart..."

if command -v chromium &> /dev/null; then
    BROWSER="chromium"
elif command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
else
    echo "  WARNING: Chromium not found."
    BROWSER=""
fi

if [ -n "$BROWSER" ]; then
    # Create kiosk launch script
    cat > "/home/$OWNER/launch-kiosk.sh" << EOF
#!/bin/bash
while ! curl -s http://localhost:5000 > /dev/null 2>&1; do
    sleep 1
done
$BROWSER --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:5000
EOF
    chmod +x "/home/$OWNER/launch-kiosk.sh"
    chown "$OWNER:$GROUP" "/home/$OWNER/launch-kiosk.sh"

    # XDG autostart (works with RPD/labwc on Bookworm)
    mkdir -p "/home/$OWNER/.config/autostart"
    cat > "/home/$OWNER/.config/autostart/sunset-kiosk.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Sunset Courts Kiosk
Exec=/home/$OWNER/launch-kiosk.sh
X-GNOME-Autostart-enabled=true
EOF
    chown -R "$OWNER:$GROUP" "/home/$OWNER/.config/autostart"

    echo "  Browser: $BROWSER (XDG autostart)"
    echo "  Done."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Flask service:   running (auto-starts on boot)"
echo "  Browser kiosk:   opens on login"
echo "  Weekly backup:   Sundays at 3:00 AM (keeps last 8)"
echo "  Time setting:    enabled"
echo "  URL:             http://localhost:5000"
echo ""
echo "  Commands:"
echo "    sudo systemctl status sunset-courts"
echo "    sudo systemctl restart sunset-courts"
echo "    sudo systemctl list-timers         # verify backup timer"
echo ""
echo "  Reboot now to test."
