#!/bin/bash
# Sunset Courts — Clean Setup
# Wipes all previous configuration and installs fresh.
# Run once: sudo bash setup_clean.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OWNER="$(stat -c '%U' "$SCRIPT_DIR")"
GROUP="$(stat -c '%G' "$SCRIPT_DIR")"

# Verify required files
REQUIRED="app.py init_db.py db.py"
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
echo "[1/6] Removing old configuration..."

# Stop and remove old service
systemctl stop sunset-courts 2>/dev/null || true
systemctl disable sunset-courts 2>/dev/null || true
rm -f /etc/systemd/system/sunset-courts.service
systemctl daemon-reload

# Wipe old labwc autostart
rm -f "/home/$OWNER/.config/labwc/autostart"

# Remove old sudoers entry
rm -f /etc/sudoers.d/sunset-courts-date

echo "  Done."

# ── STEP 2: Install Flask ──────────────────────────────────────
echo "[2/6] Installing Flask..."
pip3 install flask --break-system-packages -q 2>/dev/null || pip3 install flask -q
echo "  Done."

# ── STEP 3: Initialize database if needed ──────────────────────
if [ ! -f "$SCRIPT_DIR/sunset_courts.db" ]; then
    echo "[3/6] Initializing database..."
    cd "$SCRIPT_DIR" && python3 init_db.py
else
    echo "[3/6] Database already exists, skipping."
fi

# ── STEP 4: Set production mode ────────────────────────────────
echo "[4/6] Setting production mode..."
sed -i 's/debug=True/debug=False/' "$SCRIPT_DIR/app.py"

# Allow time setting from the app
echo "$OWNER ALL=(ALL) NOPASSWD: /usr/bin/date" > /etc/sudoers.d/sunset-courts-date
chmod 440 /etc/sudoers.d/sunset-courts-date
echo "  Done."

# ── STEP 5: Create systemd service ────────────────────────────
echo "[5/6] Creating systemd service..."
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

# ── STEP 6: Create browser autostart ──────────────────────────
echo "[6/6] Creating browser autostart..."

# Detect which chromium binary exists
if command -v chromium &> /dev/null; then
    BROWSER="chromium"
elif command -v chromium-browser &> /dev/null; then
    BROWSER="chromium-browser"
else
    echo "  WARNING: Chromium not found. Browser will not auto-launch."
    BROWSER=""
fi

if [ -n "$BROWSER" ]; then
    LABWC_DIR="/home/$OWNER/.config/labwc"
    mkdir -p "$LABWC_DIR"

    cat > "$LABWC_DIR/autostart" << EOF
bash -c "while ! curl -s http://localhost:5000 > /dev/null 2>&1; do sleep 1; done; $BROWSER --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:5000" &
EOF

    chown -R "$OWNER:$GROUP" "$LABWC_DIR"
    echo "  Browser: $BROWSER"
    echo "  Done."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "  Flask service:  running (auto-starts on boot)"
echo "  Browser kiosk:  $BROWSER opens on login"
echo "  Time setting:   enabled"
echo "  URL:            http://localhost:5000"
echo ""
echo "  Commands:"
echo "    sudo systemctl status sunset-courts"
echo "    sudo systemctl restart sunset-courts"
echo "    sudo systemctl stop sunset-courts"
echo ""
echo "  Reboot now to test."
