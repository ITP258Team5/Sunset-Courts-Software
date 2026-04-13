#!/bin/bash
# Sunset Courts — Full Uninstall
# Removes all services, autostart, and optionally the application data.
# Run: sudo bash uninstall.sh

set -e

OWNER="$(logname 2>/dev/null || echo $SUDO_USER)"

echo "=== Sunset Courts — Uninstall ==="
echo ""

# Stop and remove systemd services
echo "[1/5] Removing services..."
systemctl stop sunset-courts 2>/dev/null || true
systemctl disable sunset-courts 2>/dev/null || true
systemctl stop sunset-courts-backup.timer 2>/dev/null || true
systemctl disable sunset-courts-backup.timer 2>/dev/null || true
rm -f /etc/systemd/system/sunset-courts.service
rm -f /etc/systemd/system/sunset-courts-backup.service
rm -f /etc/systemd/system/sunset-courts-backup.timer
systemctl daemon-reload
echo "  Done."

# Remove autostart entries
echo "[2/5] Removing autostart..."
rm -f "/home/$OWNER/.config/autostart/sunset-kiosk.desktop"
rm -f "/home/$OWNER/.config/labwc/autostart"
echo "  Done."

# Remove kiosk launcher
echo "[3/5] Removing kiosk launcher..."
rm -f "/home/$OWNER/launch-kiosk.sh"
echo "  Done."

# Remove sudoers entry
echo "[4/5] Removing sudoers entry..."
rm -f /etc/sudoers.d/sunset-courts-date
echo "  Done."

# Ask about application data
echo ""
echo "[5/5] Application data"
echo ""
echo "  The following will be PERMANENTLY deleted:"
echo "    - Database (all accounts, bookings, dues)"
echo "    - All local backups"
echo "    - All application code"
echo ""
read -p "  Delete the sunset-courts directory? (yes/no): " CONFIRM

if [ "$CONFIRM" = "yes" ]; then
    # Find the directory — check common locations
    for DIR in "/home/$OWNER/sunset-courts" "/home/$OWNER/Desktop/sunset-courts"; do
        if [ -d "$DIR" ]; then
            rm -rf "$DIR"
            echo "  Deleted: $DIR"
        fi
    done
    echo "  Done."
else
    echo "  Skipped. Application files preserved."
fi

echo ""
echo "=== Uninstall Complete ==="
echo ""
echo "  All Sunset Courts services and autostart removed."
echo "  Reboot to confirm clean state."
