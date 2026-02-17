"""User authentication, session management, and rate limiting."""
import os
import re as _re
import time
import hashlib
import bcrypt
import secrets
import sqlite3
from typing import Optional
from pathlib import Path
from collections import defaultdict

from fastapi import Header, HTTPException

# --- Config ---
APP_PASSWORD = os.environ.get("SENTSEI_PASSWORD", "sentsei2026")
SESSION_TTL = 30 * 24 * 3600  # 30 days

# --- Rate Limiting ---
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60
_rate_buckets: dict = defaultdict(list)
_rate_check_counter = 0


def rate_limit_check(ip: str) -> bool:
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    _rate_buckets[ip] = [t for t in _rate_buckets[ip] if t > cutoff]
    if len(_rate_buckets[ip]) >= RATE_LIMIT_REQUESTS:
        return False
    _rate_buckets[ip].append(now)
    return True


def rate_limit_cleanup():
    global _rate_check_counter
    _rate_check_counter += 1
    if _rate_check_counter % 100 == 0:
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW
        stale = [ip for ip, ts in _rate_buckets.items() if not ts or ts[-1] < cutoff]
        for ip in stale:
            del _rate_buckets[ip]


# --- SQLite User DB ---
DB_PATH = Path(__file__).parent / "sentsei.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_user_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS user_data (
            user_id INTEGER NOT NULL,
            data_key TEXT NOT NULL,
            data_json TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (user_id, data_key),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith("$2b$") or stored.startswith("$2a$"):
            return bcrypt.checkpw(password.encode(), stored.encode())
        if ":" not in stored:
            return False
        salt, h = stored.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    now = time.time()
    conn = get_db()
    conn.execute("INSERT INTO sessions (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
                 (user_id, token, now, now + SESSION_TTL))
    conn.commit()
    conn.close()
    return token


def get_user_from_token(token: str) -> Optional[dict]:
    if not token:
        return None
    conn = get_db()
    row = conn.execute(
        "SELECT s.user_id, u.username FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ? AND s.expires_at > ?",
        (token, time.time())
    ).fetchone()
    conn.close()
    if row:
        return {"id": row["user_id"], "username": row["username"]}
    return None


def cleanup_expired_sessions() -> int:
    """Delete expired sessions from the database. Returns count of deleted rows."""
    conn = get_db()
    cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    if authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def require_password(x_app_password: Optional[str] = Header(default=None)):
    """FastAPI dependency that validates the X-App-Password header."""
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")
