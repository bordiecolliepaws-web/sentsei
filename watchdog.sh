#!/bin/bash
# Sentsei server watchdog — checks every 30s, restarts if down
while true; do
    if ! curl -sf http://localhost:8847/api/languages > /dev/null 2>&1; then
        echo "$(date) — Server down, restarting..."
        pkill -f "uvicorn backend" 2>/dev/null
        sleep 1
        cd /home/opclaw/.openclaw/workspace-sora/sentsei
        nohup uvicorn backend:app --host 0.0.0.0 --port 8847 >> /tmp/sentsei.log 2>&1 &
        echo "$(date) — Restarted (pid $!)"
    fi
    sleep 30
done
