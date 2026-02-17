"""API route handlers for Sentsei."""
import os
import json
import re as _re
import random
import hashlib
import time
import asyncio
from typing import Optional, List
from pathlib import Path
from collections import defaultdict

from log import get_logger

logger = get_logger("sentsei.routes")

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from fastapi.responses import StreamingResponse
import httpx

from models import (
    SUPPORTED_LANGUAGES, ALLOWED_DATA_KEYS,
    WordDetailRequest, ContextExamplesRequest, AnkiExportEntry,
    AuthRequest,
    STORIES,
)
from cache import (
    cache_key, cache_get, cache_put,
    get_grammar_patterns,
    word_cache_key, word_cache_get, word_cache_put, word_cache_stats,
)
from auth import (
    APP_PASSWORD, rate_limit_check, rate_limit_cleanup, get_rate_limit_key,
    get_db, init_user_db, hash_password, verify_password,
    create_session, get_user_from_token, extract_bearer_token,
    require_password,
)
from llm import (
    OLLAMA_URL, OLLAMA_MODEL,
    deterministic_pronunciation, deterministic_word_pronunciation,
    ensure_traditional_chinese, detect_sentence_difficulty,
    cedict_lookup, parse_json_object, split_sentences,
    sanitize_tsv_cell, anki_language_label,
    ollama_chat, check_ollama_connectivity,
)

from surprise import (
    router as surprise_router,
    _surprise_bank, _surprise_bank_filling,
    increment_user_request, decrement_user_request,
    load_surprise_bank, fill_surprise_bank_task, refill_surprise_bank_task,
    save_surprise_bank, get_surprise_bank,
)
from feedback import router as feedback_router
from quiz_routes import router as quiz_router
from learn_routes import router as learn_router
from compare_routes import router as compare_router

router = APIRouter()
router.include_router(surprise_router)
router.include_router(feedback_router)
router.include_router(quiz_router)
router.include_router(learn_router)
router.include_router(compare_router)

# Re-export for backward compatibility
from learn_routes import _learn_sentence_impl, _detect_input_language, MAX_INPUT_LEN, _check_injection


@router.post("/api/word-detail", tags=["Learning"], summary="Get detailed info about a word")
async def word_detail(
    request: Request,
    req: WordDetailRequest,
    _pw=Depends(require_password),
):

    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if len(req.word) > MAX_INPUT_LEN or len(req.meaning) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")
    if req.sentence_context and len(req.sentence_context) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    # Check word-detail cache first
    wc_key = word_cache_key(req.word, req.target_language, req.meaning)
    cached = word_cache_get(wc_key)
    if cached is not None:
        logger.info("word-detail cache hit", extra={"word": req.word, "lang": req.target_language})
        return cached

    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    meaning_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.meaning)
    explain_lang = "繁體中文" if meaning_is_chinese else "English"

    prompt = f"""Word: "{req.word}" ({lang_name}, meaning: {req.meaning}).
Return JSON only: {{"examples":[{{"sentence":"..","pronunciation":"..","meaning":".."}}],"conjugations":[{{"form":"..","label":".."}}],"related":[{{"word":"..","meaning":".."}}]}}
2 examples, 2-3 conjugations ([] if none), 2 related words. Explanations in {explain_lang}. Simple sentences."""

    text = await ollama_chat(
        [{"role": "system", "content": f"{lang_name} vocab teacher. JSON only."},
         {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.3, num_predict=512, timeout=45
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    result = parse_json_object(text)
    if not result:
        return {"examples": [], "conjugations": [], "related": []}

    result = ensure_traditional_chinese(result)
    word_cache_put(wc_key, result)
    return result


@router.post("/api/word-detail-stream", tags=["Learning"], summary="Stream word detail via SSE")
async def word_detail_stream(
    request: Request,
    req: WordDetailRequest,
    _pw=Depends(require_password),
):
    """SSE streaming version of word-detail — sends progress while LLM works."""

    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if len(req.word) > MAX_INPUT_LEN or len(req.meaning) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")
    if req.sentence_context and len(req.sentence_context) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    # Check word-detail cache first — return instant JSON if cached
    wc_key = word_cache_key(req.word, req.target_language, req.meaning)
    cached = word_cache_get(wc_key)
    if cached is not None:
        logger.info("word-detail-stream cache hit", extra={"word": req.word, "lang": req.target_language})
        async def _cached():
            yield f"data: {json.dumps({'type': 'result', 'data': cached}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_cached(), media_type="text/event-stream",
                                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def _generate():
        try:
            yield f"data: {json.dumps({'type': 'progress', 'status': 'Looking up word details...'})}\n\n"

            lang_name = SUPPORTED_LANGUAGES[req.target_language]
            meaning_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.meaning)
            explain_lang = "繁體中文" if meaning_is_chinese else "English"

            prompt = f"""Word: "{req.word}" ({lang_name}, meaning: {req.meaning}).
Return JSON only: {{"examples":[{{"sentence":"..","pronunciation":"..","meaning":".."}}],"conjugations":[{{"form":"..","label":".."}}],"related":[{{"word":"..","meaning":".."}}]}}
2 examples, 2-3 conjugations ([] if none), 2 related words. Explanations in {explain_lang}. Simple sentences."""

            # Run LLM call as a task so we can send progress heartbeats
            llm_task = asyncio.create_task(ollama_chat(
                [{"role": "system", "content": f"{lang_name} vocab teacher. JSON only."},
                 {"role": "user", "content": prompt}],
                model=OLLAMA_MODEL, temperature=0.3, num_predict=512, timeout=45
            ))

            elapsed = 0
            messages = [
                (3, "Generating examples..."),
                (8, "Building conjugations..."),
                (15, "Finding related words..."),
                (22, "Almost there..."),
            ]
            msg_idx = 0
            while not llm_task.done():
                await asyncio.sleep(1.5)
                elapsed += 1.5
                while msg_idx < len(messages) and elapsed >= messages[msg_idx][0]:
                    yield f"data: {json.dumps({'type': 'progress', 'status': messages[msg_idx][1]})}\n\n"
                    msg_idx += 1
                # Heartbeat to keep connection alive
                yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': round(elapsed, 1)})}\n\n"

            text = llm_task.result()
            if text is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Translation engine unavailable'})}\n\n"
                return

            result = parse_json_object(text)
            if not result:
                result = {"examples": [], "conjugations": [], "related": []}
            else:
                result = ensure_traditional_chinese(result)
                word_cache_put(wc_key, result)

            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("word-detail-stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/context-examples", tags=["Learning"], summary="Get example sentences using a word")
async def context_examples(
    request: Request,
    req: ContextExamplesRequest,
    _pw=Depends(require_password),
):

    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if len(req.translation) > MAX_INPUT_LEN or len(req.source_sentence) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    input_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.source_sentence)
    explain_lang = "繁體中文" if input_is_chinese else "English"

    ck = f"ctx:{hashlib.md5((req.translation + req.target_language).encode()).hexdigest()}"
    cached = cache_get(ck)
    if cached:
        return cached

    prompt = f"""Given this {lang_name} sentence: "{req.translation}"
(Original meaning: "{req.source_sentence}")

Generate 3 different example sentences in {lang_name} that use the SAME key grammar pattern or vocabulary from the sentence above, but in DIFFERENT everyday contexts.

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "examples": [
    {{
      "sentence": "example in {lang_name} script",
      "pronunciation": "romanized pronunciation",
      "meaning": "translation in {explain_lang}",
      "context": "brief label like 'At a restaurant' or 'Texting a friend' in {explain_lang}"
    }}
  ]
}}

Rules:
- Each example should show a DIFFERENT situation/context
- Keep sentences simple and practical (beginner-friendly)
- Use the same grammar structure but with different vocabulary
- All meanings/context labels in {explain_lang}"""

    system_msg = f"You are a {lang_name} teacher creating contextual examples. Respond with valid JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.5, num_predict=1024, timeout=120
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    result = parse_json_object(text)
    if not result:
        return {"examples": []}

    result = ensure_traditional_chinese(result)

    if "examples" in result:
        for ex in result["examples"]:
            if "sentence" in ex and req.target_language in ("ja", "zh", "ko"):
                det = deterministic_pronunciation(ex["sentence"], req.target_language)
                if det:
                    ex["pronunciation"] = det

    cache_put(ck, result)
    return result


@router.get("/api/languages", tags=["Reference"], summary="List supported languages")
async def get_languages():
    return SUPPORTED_LANGUAGES


@router.post("/api/export-anki", tags=["Export"], summary="Export history as Anki TSV")
async def export_anki(
    entries: List[AnkiExportEntry],
    _pw=Depends(require_password),
):

    rows: List[str] = []
    for entry in entries:
        front = sanitize_tsv_cell(entry.sentence)
        if not front:
            continue
        translation = sanitize_tsv_cell(entry.translation)
        pronunciation = sanitize_tsv_cell(entry.pronunciation)
        lang_code = (entry.target or entry.lang or "").strip()
        back_parts: List[str] = []
        if translation:
            back_parts.append(translation)
        if pronunciation:
            back_parts.append(f"Pronunciation: {pronunciation}")
        if lang_code:
            back_parts.append(f"Language: {anki_language_label(lang_code)}")
        back = sanitize_tsv_cell("<br>".join(back_parts))
        rows.append(f"{front}\t{back}")

    content = "\n".join(rows)
    headers = {"Content-Disposition": 'attachment; filename="sent-say-flashcards.txt"'}
    return Response(content=content, media_type="text/tab-separated-values", headers=headers)


@router.get("/api/health", tags=["System"], summary="Health check with stats")
async def health_check():
    from cache import _translation_cache, CACHE_MAX, CACHE_TTL
    ollama_ok = await check_ollama_connectivity()
    cache_size = len(_translation_cache)
    bank_total = sum(len(v) for v in _surprise_bank.values())
    bank_langs = len(_surprise_bank)

    from backend import get_latency_stats
    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": {"reachable": ollama_ok, "url": OLLAMA_URL, "model": OLLAMA_MODEL},
        "cache": {"entries": cache_size, "max": CACHE_MAX, "ttl_hours": CACHE_TTL / 3600},
        "word_cache": word_cache_stats(),
        "surprise_bank": {"total_entries": bank_total, "languages": bank_langs, "filling": _surprise_bank_filling},
        "latency": get_latency_stats(),
    }


@router.get("/api/stories", tags=["Stories"], summary="List available stories")
async def list_stories():
    return [
        {"id": s["id"], "title": s["title"], "source": s["source"], "language": s["language"], "sentence_count": len(s["sentences"])}
        for s in STORIES.values()
    ]


@router.get("/api/story/{story_id}", tags=["Stories"], summary="Get a specific story")
async def get_story(story_id: str):
    story = STORIES.get(story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@router.get("/api/grammar-patterns", tags=["Reference"], summary="Browse grammar patterns")
async def list_grammar_patterns(lang: Optional[str] = None, _pw=Depends(require_password)):
    patterns = list(get_grammar_patterns().values())
    if lang:
        patterns = [p for p in patterns if p.get("lang") == lang]
    patterns.sort(key=lambda p: -p.get("count", 0))
    return [
        {"id": p["id"], "name": p["name"], "lang": p["lang"], "explanation": p["explanation"], "count": p["count"], "example_count": len(p.get("examples", []))}
        for p in patterns
    ]


@router.get("/api/grammar-patterns/{pattern_id}", tags=["Reference"], summary="Get grammar pattern details")
async def get_grammar_pattern(pattern_id: str, _pw=Depends(require_password)):
    pattern = get_grammar_patterns().get(pattern_id)
    if not pattern:
        raise HTTPException(404, "Pattern not found")
    return pattern


# --- Auth Routes ---

@router.post("/api/auth/register", tags=["Auth"], summary="Register a new user")
async def auth_register(req: AuthRequest):
    import re as _re
    username = req.username.strip()
    password = req.password
    if not username or len(username) < 2 or len(username) > 30:
        raise HTTPException(400, "Username must be 2-30 characters")
    if not _re.match(r'^[a-zA-Z0-9_-]+$', username):
        raise HTTPException(400, "Username can only contain letters, numbers, hyphens, underscores")
    if not password or len(password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")

    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(409, "Username already taken")

    pw_hash = hash_password(password)
    now = time.time()
    cursor = conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                          (username, pw_hash, now))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    token = create_session(user_id)
    return {"token": token, "username": username}


@router.post("/api/auth/login", tags=["Auth"], summary="Log in and get a session token")
async def auth_login(req: AuthRequest):
    username = req.username.strip()
    conn = get_db()
    row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "Invalid username or password")

    if not row["password_hash"].startswith("$2b$"):
        new_hash = hash_password(req.password)
        conn2 = get_db()
        conn2.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row["id"]))
        conn2.commit()
        conn2.close()

    token = create_session(row["id"])
    return {"token": token, "username": username}


@router.post("/api/auth/logout", tags=["Auth"], summary="Log out and invalidate token")
async def auth_logout(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    if token:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"ok": True}


@router.get("/api/auth/me", tags=["Auth"], summary="Get current user info")
async def auth_me(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")
    return {"username": user["username"]}


@router.get("/api/user-data/{key}", tags=["Auth"], summary="Get user data by key")
async def get_user_data(key: str, authorization: Optional[str] = Header(default=None)):
    if key not in ALLOWED_DATA_KEYS:
        raise HTTPException(400, f"Invalid data key. Allowed: {', '.join(ALLOWED_DATA_KEYS)}")
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")

    conn = get_db()
    row = conn.execute("SELECT data_json FROM user_data WHERE user_id = ? AND data_key = ?",
                       (user["id"], key)).fetchone()
    conn.close()
    if not row:
        return {"key": key, "data": None}
    return {"key": key, "data": json.loads(row["data_json"])}


@router.put("/api/user-data/{key}")
async def put_user_data(key: str, request: Request, authorization: Optional[str] = Header(default=None)):
    if key not in ALLOWED_DATA_KEYS:
        raise HTTPException(400, f"Invalid data key. Allowed: {', '.join(ALLOWED_DATA_KEYS)}")
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")

    body = await request.json()
    data = body.get("data")
    data_json = json.dumps(data, ensure_ascii=False)

    if len(data_json) > 1_000_000:
        raise HTTPException(400, "Data too large (max 1MB)")

    conn = get_db()
    conn.execute(
        "INSERT INTO user_data (user_id, data_key, data_json, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, data_key) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at",
        (user["id"], key, data_json, time.time())
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# --- Surprise Bank Background Tasks ---
