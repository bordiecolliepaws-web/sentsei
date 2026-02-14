#!/bin/bash
# Sentsei watchdog — runs via system crontab every minute
if ! curl -sf --max-time 5 http://localhost:8847/api/languages > /dev/null 2>&1; then
    echo "$(date) — Server down, restarting..."
    pkill -f "uvicorn backend" 2>/dev/null
    sleep 1
    cd /home/opclaw/.openclaw/workspace-sora/sentsei
    nohup /home/opclaw/.local/bin/uvicorn backend:app --host 0.0.0.0 --port 8847 >> /tmp/sentsei.log 2>&1 &
    echo "$(date) — Restarted (pid $!)"
else
    echo "$(date) — OK"
fi
