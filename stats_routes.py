"""Aggregate usage stats endpoint."""
import sqlite3
import time
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends
from auth import require_password
from cache import _translation_cache, word_cache_stats

router = APIRouter(prefix="/api", tags=["stats"])

DB_PATH = Path(__file__).parent / "sentsei.db"


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/stats")
async def get_stats(_pw=Depends(require_password)):
    """Aggregate usage stats: cache, users, latency."""
    from backend import get_latency_stats

    # Translation cache stats
    now = time.time()
    lang_counter = Counter()
    valid = 0
    for _key, (ts, result) in list(_translation_cache.items()):
        if now - ts < 86400:  # within TTL
            valid += 1
            lang = result.get("target_language", "unknown") if isinstance(result, dict) else "unknown"
            lang_counter[lang] += 1

    cache_info = {
        "total_cached": len(_translation_cache),
        "valid_entries": valid,
        "by_language": dict(lang_counter.most_common()),
    }

    # User stats from SQLite
    user_info = {"total_users": 0, "active_sessions": 0}
    try:
        db = _db()
        user_info["total_users"] = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        user_info["active_sessions"] = db.execute(
            "SELECT COUNT(*) FROM sessions WHERE expires_at > datetime('now')"
        ).fetchone()[0]
        db.close()
    except Exception:
        pass

    # Word cache
    wcache = word_cache_stats()

    # Latency
    latency = get_latency_stats()

    return {
        "cache": cache_info,
        "users": user_info,
        "word_cache": wcache,
        "latency": latency,
    }
