#!/data/data/com.termux/files/usr/bin/bash
# Stop Find the Gem Streamlit server

WORKDIR="/data/data/com.termux/files/home/findthegem"
PIDFILE="$WORKDIR/server.pid"

if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[FindTheGem] Stopping server (PID: $PID)..."
        kill "$PID"
        sleep 1
        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID" 2>/dev/null || true
        fi
        echo "[FindTheGem] Server stopped"
    else
        echo "[FindTheGem] Server not running"
    fi
    rm -f "$PIDFILE"
else
    echo "[FindTheGem] No PID file found, server may not be running"
fi
