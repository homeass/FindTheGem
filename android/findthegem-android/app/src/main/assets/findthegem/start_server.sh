#!/data/data/com.termux/files/usr/bin/bash
# Start Find the Gem Streamlit server

WORKDIR="/data/data/com.termux/files/home/findthegem"
PIDFILE="$WORKDIR/server.pid"
LOGFILE="$WORKDIR/server.log"

mkdir -p "$WORKDIR"

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[FindTheGem] Server already running (PID: $PID)"
        exit 0
    fi
fi

echo "[FindTheGem] Starting Streamlit server..."
cd "$WORKDIR"

# Start server in background
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
