#!/bin/bash
# Sunset Courts — Automatic Backup
# Called by systemd timer weekly. Keeps last 8 backups.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_PATH="$SCRIPT_DIR/sunset_courts.db"
BACKUP_DIR="$SCRIPT_DIR/backups"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)

if [ ! -f "$DB_PATH" ]; then
    echo "Database not found: $DB_PATH"
    exit 1
fi

mkdir -p "$BACKUP_DIR"
cp "$DB_PATH" "$BACKUP_DIR/sunset_courts_backup_${TIMESTAMP}.db"
echo "Backup created: sunset_courts_backup_${TIMESTAMP}.db"

# Keep only last 8 backups
cd "$BACKUP_DIR"
ls -t sunset_courts_backup_*.db 2>/dev/null | tail -n +9 | xargs -r rm
echo "Old backups cleaned up. $(ls sunset_courts_backup_*.db | wc -l) backup(s) retained."
