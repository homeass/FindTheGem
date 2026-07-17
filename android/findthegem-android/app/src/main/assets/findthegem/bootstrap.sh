#!/data/data/com.termux/files/usr/bin/bash

PROPS_FILE="$HOME/.termux/termux.properties"
LOG="/sdcard/Documents/FindTheGem/setup.log"

mkdir -p "$(dirname "$LOG")"
echo "=== Bootstrap started at $(date) ===" > "$LOG"

if ! grep -q "allow-external-apps=true" "$PROPS_FILE" 2>/dev/null; then
    mkdir -p "$HOME/.termux"
    echo "allow-external-apps=true" >> "$PROPS_FILE"
    echo "[FindTheGem] Enabled allow-external-apps" >> "$LOG"
fi

WORKDIR="$HOME/findthegem"
DOCS="/sdcard/Documents/FindTheGem"

mkdir -p "$WORKDIR"
if [ -d "$DOCS" ]; then
    cp -r "$DOCS"/* "$WORKDIR/" 2>> "$LOG" || true
    echo "[FindTheGem] Files copied" >> "$LOG"
else
    echo "[FindTheGem] DOCS not found: $DOCS" >> "$LOG"
fi

if ! command -v python3 &>/dev/null; then
    echo "[FindTheGem] Installing Python..." >> "$LOG"
    pkg update -y >> "$LOG" 2>&1 && pkg install -y python >> "$LOG" 2>&1
else
    echo "[FindTheGem] Python found: $(which python3)" >> "$LOG"
fi

cd "$WORKDIR"
if [ -f requirements.txt ]; then
    echo "[FindTheGem] Installing pip packages..." >> "$LOG"
    pip install --upgrade pip >> "$LOG" 2>&1 || true
    pip install -r requirements.txt >> "$LOG" 2>&1 || echo "[FindTheGem] pip install had warnings" >> "$LOG"
fi
chmod +x "$WORKDIR"/*.sh 2>/dev/null || true

echo "=== Bootstrap complete at $(date) ===" >> "$LOG"
echo "[FindTheGem] Starting server..."
bash "$WORKDIR/start_server.sh"
echo "[FindTheGem] Server running on http://127.0.0.1:8501"
