#!/data/data/com.termux/files/usr/bin/bash
# Start Find the Gem Streamlit server
# Now runs from: /sdcard/Documents/FindTheGem/ (set by TermuxManager via cd)

WORKDIR="$PWD"
PIDFILE="$WORKDIR/server.pid"
LOGFILE="$WORKDIR/server.log"

cd "$WORKDIR" || { echo "[FindTheGem] ERROR: Cannot cd to $WORKDIR"; exit 1; }

if [ ! -f findthegem_app.py ]; then
    echo "[FindTheGem] ERROR: findthegem_app.py not found in $WORKDIR"
    echo "[FindTheGem] Files in directory:"
    ls -la "$WORKDIR"
    exit 1
fi

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[FindTheGem] Server already running (PID: $PID)"
        exit 0
    fi
    rm -f "$PIDFILE"
fi

echo "[FindTheGem] Starting Streamlit server from $WORKDIR..."

nohup python3 -m streamlit run findthegem_app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 127.0.0.1 \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false \
    > "$LOGFILE" 2>&1 &

echo $! > "$PIDFILE"
echo "[FindTheGem] Server started with PID $(cat $PIDFILE)"
echo "[FindTheGem] Listening on http://127.0.0.1:8501"
