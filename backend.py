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

from cache import load_cache, save_cache, is_cache_dirty, load_grammar_patterns, save_grammar_patterns, is_grammar_dirty
from auth import init_user_db, cleanup_expired_sessions
from llm import check_ollama_connectivity
from routes import router, load_surprise_bank, fill_surprise_bank_task, refill_surprise_bank_task, get_surprise_bank

app = FastAPI()

# CORS — configurable via env vars, defaults to same-origin only
_cors_origins = [o.strip() for o in os.environ.get("SENTSEI_CORS_ORIGINS", "").split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(router)


@app.middleware("http")
async def log_requests(request, call_next):
    """Log all API requests with timing."""
    import time as _time
    start = _time.time()
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        duration_ms = round((_time.time() - start) * 1000)
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


@app.on_event("shutdown")
async def _shutdown_cache():
    if is_cache_dirty():
        save_cache()
        logger.info("Cache saved on shutdown", extra={"component": "cache"})
    if is_grammar_dirty():
        save_grammar_patterns()
        logger.info("Grammar patterns saved on shutdown", extra={"component": "grammar"})


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
