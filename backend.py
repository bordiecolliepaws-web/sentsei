"""SentSay — Sentence-based language learning app. Entry point."""
import asyncio
import json
import os
from pathlib import Path

from log import get_logger

logger = get_logger("sentsei.app")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cache import (load_cache, save_cache, is_cache_dirty, load_grammar_patterns,
                   save_grammar_patterns, is_grammar_dirty, load_word_cache,
                   save_word_cache, _word_cache_dirty)
from auth import init_user_db, cleanup_expired_sessions, rate_limit_remaining, get_rate_limit_key, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW
from llm import check_ollama_connectivity
from routes import router
from stats_routes import router as stats_router
from surprise import load_surprise_bank, fill_surprise_bank_task, refill_surprise_bank_task, get_surprise_bank

app = FastAPI(
    title="SentSay API",
    description=(
        "Sentence-based language learning API. "
        "Type any sentence and get translations with pronunciation, "
        "grammar notes, and word-by-word breakdowns.\n\n"
        "**Core flow:** POST `/api/learn` with a sentence and target language.\n\n"
        "**Authentication:** Most endpoints require an `X-App-Password` header. "
        "User accounts (optional) use Bearer tokens via `/api/auth/*` endpoints."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — configurable via env vars, defaults to same-origin only
_cors_origins = [o.strip() for o in os.environ.get("SENTSEI_CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Window"],
    )

app.include_router(router)
app.include_router(stats_router)


import collections, bisect

# Rolling latency tracker — keeps last 500 API timings per endpoint
_latency_window = {}  # type: dict[str, collections.deque]
_LATENCY_MAX = 500

def record_latency(endpoint: str, ms: int):
    if endpoint not in _latency_window:
        _latency_window[endpoint] = collections.deque(maxlen=_LATENCY_MAX)
    _latency_window[endpoint].append(ms)

def get_latency_stats() -> dict:
    """Return p50/p95/p99 latency stats per endpoint + overall."""
    def _percentiles(values):
        s = sorted(values)
        n = len(s)
        if n == 0:
            return {"p50": 0, "p95": 0, "p99": 0, "count": 0}
        return {
            "p50": s[n * 50 // 100],
            "p95": s[min(n * 95 // 100, n - 1)],
            "p99": s[min(n * 99 // 100, n - 1)],
            "count": n,
        }
    result = {}
    all_values = []
    for ep, dq in _latency_window.items():
        vals = list(dq)
        result[ep] = _percentiles(vals)
        all_values.extend(vals)
    result["_overall"] = _percentiles(all_values)
    return result

@app.middleware("http")
async def log_requests(request, call_next):
    """Log all API requests with timing."""
    import time as _time
    start = _time.time()
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        duration_ms = round((_time.time() - start) * 1000)
        record_latency(request.url.path, duration_ms)
        # Inject rate limit headers
        rate_key = get_rate_limit_key(request)
        remaining = rate_limit_remaining(rate_key)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(RATE_LIMIT_WINDOW)
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code}",
            extra={
                "component": "http",
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "ip": request.client.host if request.client else None,
            },
        )
    return response


@app.on_event("startup")
async def _startup_cache():
    load_cache()
    load_grammar_patterns()
    load_word_cache()


@app.on_event("shutdown")
async def _shutdown_cache():
    if is_cache_dirty():
        save_cache()
        logger.info("Cache saved on shutdown", extra={"component": "cache"})
    if is_grammar_dirty():
        save_grammar_patterns()
        logger.info("Grammar patterns saved on shutdown", extra={"component": "grammar"})
    if _word_cache_dirty:
        save_word_cache()
        logger.info("Word cache saved on shutdown", extra={"component": "cache"})


@app.on_event("startup")
async def _startup_surprise():
    load_surprise_bank()
    ollama_ok = await check_ollama_connectivity()
    if ollama_ok:
        bank = get_surprise_bank()
        if not bank or sum(len(v) for v in bank.values()) < 5:
            logger.info("Surprise bank low/empty, starting background fill", extra={"component": "surprise-bank"})
            asyncio.create_task(fill_surprise_bank_task())
        asyncio.create_task(refill_surprise_bank_task())
    else:
        logger.warning("Ollama not available, skipping surprise bank fill", extra={"component": "surprise-bank"})


@app.on_event("startup")
async def _startup_user_db():
    init_user_db()


SESSION_CLEANUP_INTERVAL = 3600  # 1 hour


@app.on_event("startup")
async def _startup_session_cleanup():
    """Run session cleanup on startup, then every hour."""
    deleted = cleanup_expired_sessions()
    if deleted:
        logger.info("Cleaned up expired sessions on startup", extra={"component": "auth", "count": deleted})

    async def _periodic_cleanup():
        while True:
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
            try:
                deleted = cleanup_expired_sessions()
                if deleted:
                    logger.info("Cleaned up expired sessions", extra={"component": "auth", "count": deleted})
            except Exception:
                logger.exception("Session cleanup error", extra={"component": "auth"})

    asyncio.create_task(_periodic_cleanup())


app.mount("/", StaticFiles(directory="static", html=True), name="static")
