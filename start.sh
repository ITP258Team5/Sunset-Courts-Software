#!/bin/bash
# Sunset Courts — Kiosk Launch (demo/VirtualBox)
# Mimics Pi startup experience
# Usage: bash start.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Initialize DB if needed
[ ! -f sunset_courts.db ] && python3 init_db.py

# Start Flask in background
python3 app.py &
FLASK_PID=$!

# Wait for Flask, then open Chromium in kiosk mode
(while ! curl -s http://localhost:5000 > /dev/null 2>&1; do sleep 0.5; done
chromium --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:5000 2>/dev/null ||
chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:5000 2>/dev/null ||
echo "Could not find Chromium. Open http://localhost:5000 manually."
) &

echo "Sunset Courts kiosk running — press Ctrl+C to stop"
wait $FLASK_PID
