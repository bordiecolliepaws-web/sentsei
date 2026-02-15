#!/bin/bash
# Sentsei health check — ZERO tokens when healthy
# Runs via system crontab every 10 min
# On failure: writes flag file, then OpenClaw heartbeat picks it up

PORT=8847
APP_DIR="/home/opclaw/.openclaw/workspace-sora/sentsei"
FLAG="/tmp/sentsei-debug-needed"
LOG="/tmp/sentsei-health.log"

# Check if app is responding
if curl -sf --max-time 5 "http://localhost:$PORT/api/languages" > /dev/null 2>&1; then
    rm -f "$FLAG"
    exit 0
fi

echo "$(date -Iseconds) — Sentsei DOWN, attempting restart..." >> "$LOG"

# Kill old process and restart
pkill -f "uvicorn backend:app.*$PORT" 2>/dev/null
sleep 2
cd "$APP_DIR"
nohup uvicorn backend:app --host 0.0.0.0 --port $PORT >> /tmp/sentsei.log 2>&1 &
sleep 5

# Verify
if curl -sf --max-time 5 "http://localhost:$PORT/api/languages" > /dev/null 2>&1; then
    echo "$(date -Iseconds) — Auto-restart successful" >> "$LOG"
    rm -f "$FLAG"
    exit 0
fi

# Restart failed — create flag for LLM pickup
echo "$(date -Iseconds) — Auto-restart FAILED" >> "$LOG"
echo "restart_failed $(date -Iseconds)" > "$FLAG"
exit 1
