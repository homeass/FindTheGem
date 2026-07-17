#!/data/data/com.termux/files/usr/bin/bash
# FindTheGem bootstrap script - first-time setup
# Now runs from: /sdcard/Documents/FindTheGem/ (set by TermuxManager via cd)

WORKDIR="$PWD"
LOG="$WORKDIR/setup.log"
PROPS_FILE="$HOME/.termux/termux.properties"

echo "=== Bootstrap started at $(date) ===" > "$LOG"

if ! grep -q "allow-external-apps=true" "$PROPS_FILE" 2>/dev/null; then
    mkdir -p "$HOME/.termux"
    echo "allow-external-apps=true" >> "$PROPS_FILE"
    echo "[FindTheGem] Enabled allow-external-apps" >> "$LOG"
fi

cd "$WORKDIR" || { echo "ERROR: Cannot cd to $WORKDIR" >> "$LOG"; exit 1; }

echo "PWD=$(pwd)" >> "$LOG"
echo "Files in $WORKDIR:" >> "$LOG"
ls -la "$WORKDIR" >> "$LOG" 2>&1

if ! command -v python3 &>/dev/null; then
    echo "[FindTheGem] Installing Python..." >> "$LOG"
    pkg update -y >> "$LOG" 2>&1 && pkg install -y python >> "$LOG" 2>&1
else
    echo "[FindTheGem] Python found: $(which python3)" >> "$LOG"
fi

if [ -f requirements.txt ]; then
    echo "[FindTheGem] Installing pip packages..." >> "$LOG"
    pip install --upgrade pip >> "$LOG" 2>&1 || true
    pip install -r requirements.txt >> "$LOG" 2>&1 || echo "[FindTheGem] pip install had warnings" >> "$LOG"
else
    echo "[FindTheGem] WARNING: requirements.txt not found" >> "$LOG"
fi

chmod +x "$WORKDIR"/*.sh 2>/dev/null || true

echo "=== Bootstrap complete at $(date) ===" >> "$LOG"
echo "[FindTheGem] Starting server..."
bash "$WORKDIR/start_server.sh"
echo "[FindTheGem] Server running on http://127.0.0.1:8501"
