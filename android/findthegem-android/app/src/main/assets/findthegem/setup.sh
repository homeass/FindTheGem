#!/data/data/com.termux/files/usr/bin/bash

WORKDIR="/data/data/com.termux/files/home/findthegem"
DOCUMENTS_DIR="/sdcard/Documents/FindTheGem"
LOG="/sdcard/Documents/FindTheGem/setup.log"

mkdir -p "$WORKDIR"
mkdir -p "$(dirname "$LOG")"

echo "=== FindTheGem setup started at $(date) ===" > "$LOG"
echo "HOME=$HOME" >> "$LOG"
echo "WORKDIR=$WORKDIR" >> "$LOG"
echo "DOCUMENTS_DIR=$DOCUMENTS_DIR" >> "$LOG"

echo "Checking /sdcard access..." >> "$LOG"
if [ -d "$DOCUMENTS_DIR" ]; then
    echo "DOCUMENTS_DIR exists, listing:" >> "$LOG"
    ls -la "$DOCUMENTS_DIR" >> "$LOG" 2>&1
    cp -r "$DOCUMENTS_DIR"/* "$WORKDIR/" 2>> "$LOG" || echo "cp failed (non-fatal)" >> "$LOG"
    echo "Files copied" >> "$LOG"
else
    echo "DOCUMENTS_DIR NOT FOUND" >> "$LOG"
fi

if ! command -v python3 &> /dev/null; then
    echo "Installing Python..." >> "$LOG"
    pkg update -y >> "$LOG" 2>&1
    pkg install -y python >> "$LOG" 2>&1
else
    echo "Python found: $(which python3)" >> "$LOG"
fi

cd "$WORKDIR"
echo "Installing pip packages..." >> "$LOG"
if [ -f requirements.txt ]; then
    pip install --upgrade pip >> "$LOG" 2>&1 || echo "pip upgrade failed (non-fatal)" >> "$LOG"
    pip install --prefer-binary -r requirements.txt >> "$LOG" 2>&1 || echo "pip install failed (non-fatal)" >> "$LOG"
fi

chmod +x "$WORKDIR"/*.sh 2>/dev/null || true

echo "=== Setup complete at $(date) ===" >> "$LOG"
