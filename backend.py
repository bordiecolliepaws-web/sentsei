"""SentSay — Sentence-based language learning app. Entry point."""
import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cache import load_cache, save_cache, is_cache_dirty, load_grammar_patterns, save_grammar_patterns, is_grammar_dirty
from auth import init_user_db
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


@app.on_event("startup")
async def _startup_cache():
    load_cache()
    load_grammar_patterns()


@app.on_event("shutdown")
async def _shutdown_cache():
    if is_cache_dirty():
        save_cache()
        print("[cache] Saved on shutdown")
    if is_grammar_dirty():
        save_grammar_patterns()
        print("[grammar] Saved on shutdown")


@app.on_event("startup")
async def _startup_surprise():
    load_surprise_bank()
    ollama_ok = await check_ollama_connectivity()
    if ollama_ok:
        bank = get_surprise_bank()
        if not bank or sum(len(v) for v in bank.values()) < 5:
            print("[surprise-bank] Bank is low/empty, starting background fill...")
            asyncio.create_task(fill_surprise_bank_task())
        asyncio.create_task(refill_surprise_bank_task())
    else:
        print("[surprise-bank] Ollama not available, skipping background fill")


@app.on_event("startup")
async def _startup_user_db():
    init_user_db()


app.mount("/", StaticFiles(directory="static", html=True), name="static")
