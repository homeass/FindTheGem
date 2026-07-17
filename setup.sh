#!/data/data/com.termux/files/usr/bin/bash
# FindTheGem setup script
# Now runs from: /sdcard/Documents/FindTheGem/ (set by TermuxManager via cd)

WORKDIR="$PWD"
LOG="$WORKDIR/setup.log"

echo "=== FindTheGem setup started at $(date) ===" > "$LOG"
echo "HOME=$HOME" >> "$LOG"
echo "WORKDIR=$WORKDIR" >> "$LOG"
echo "PWD=$(pwd)" >> "$LOG"
echo "Files in WORKDIR:" >> "$LOG"
ls -la "$WORKDIR" >> "$LOG" 2>&1

if [ ! -f findthegem_app.py ]; then
    echo "ERROR: findthegem_app.py not found in $WORKDIR" >> "$LOG"
    exit 1
fi

echo "Checking python3..." >> "$LOG"
if ! command -v python3 &> /dev/null; then
    echo "Installing Python..." >> "$LOG"
    pkg update -y >> "$LOG" 2>&1
    pkg install -y python >> "$LOG" 2>&1
else
    echo "Python found: $(which python3)" >> "$LOG"
fi

echo "Installing pip packages..." >> "$LOG"
if [ -f requirements.txt ]; then
    pip install --upgrade pip >> "$LOG" 2>&1 || echo "pip upgrade failed (non-fatal)" >> "$LOG"
    pip install --prefer-binary -r requirements.txt >> "$LOG" 2>&1 || echo "pip install failed (non-fatal)" >> "$LOG"
else
    echo "WARNING: requirements.txt not found in $WORKDIR" >> "$LOG"
fi

chmod +x "$WORKDIR"/*.sh 2>/dev/null || true

echo "=== Setup complete at $(date) ===" >> "$LOG"
