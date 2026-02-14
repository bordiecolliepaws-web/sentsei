#!/bin/bash
# Sentsei watchdog — runs via system crontab every minute
PIDFILE="/tmp/sentsei.pid"
LOCKFILE="/tmp/sentsei-test.lock"

# Skip restart if tests are running (lock file exists and is < 5 min old)
if [ -f "$LOCKFILE" ]; then
    lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$lock_age" -lt 300 ]; then
        echo "$(date) — Tests running (lock age ${lock_age}s), skipping"
        exit 0
    else
        echo "$(date) — Stale lock file (${lock_age}s), removing"
        rm -f "$LOCKFILE"
    fi
fi

if ! curl -sf --max-time 5 http://localhost:8847/api/languages > /dev/null 2>&1; then
    echo "$(date) — Server down, restarting..."
    # Kill by PID file first, fallback to pkill
    if [ -f "$PIDFILE" ]; then
        kill "$(cat "$PIDFILE")" 2>/dev/null
    fi
    pkill -f "uvicorn backend" 2>/dev/null
    sleep 1
    cd /home/opclaw/.openclaw/workspace-sora/sentsei
    nohup /home/opclaw/.local/bin/uvicorn backend:app --host 0.0.0.0 --port 8847 >> /tmp/sentsei.log 2>&1 &
    echo "$!" > "$PIDFILE"
    echo "$(date) — Restarted (pid $!)"
else
    echo "$(date) — OK"
fi
