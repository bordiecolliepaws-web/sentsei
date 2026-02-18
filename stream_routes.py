"""Streaming-related API route handlers for Sentsei."""
import json
import asyncio

from log import get_logger

logger = get_logger("sentsei.stream_routes")

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from models import SentenceRequest, MultiSentenceRequest, WordDetailRequest, SUPPORTED_LANGUAGES
from cache import cache_key, cache_get, word_cache_key, word_cache_get, word_cache_put
from auth import rate_limit_check, rate_limit_cleanup, get_rate_limit_key, require_password
from llm import (
    split_sentences,
    build_dictionary_word_detail,
    normalize_word_detail_payload,
    llm_word_detail,
)
from surprise import increment_user_request, decrement_user_request
from learn_routes import _learn_sentence_impl, MAX_INPUT_LEN

router = APIRouter()


@router.post("/api/learn-stream", tags=["Learning"], summary="Stream a translation via SSE")
async def learn_sentence_stream(
    request: Request,
    req: SentenceRequest,
    _pw=Depends(require_password),
):

    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence or not req.sentence.strip():
        raise HTTPException(400, "Sentence cannot be empty")

    if len(req.sentence) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    gender = req.speaker_gender or "neutral"
    formality = req.speaker_formality or "polite"
    ck = cache_key(req.sentence, req.target_language, gender, formality)
    cached = cache_get(ck)
    if cached:
        async def _cached_stream():
            yield f"data: {json.dumps({'type': 'result', 'data': cached}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_cached_stream(), media_type="text/event-stream")

    async def _generate():
        try:
            increment_user_request()

            yield f"data: {json.dumps({'type': 'progress', 'tokens': 0, 'status': 'generating'})}\n\n"

            learn_task = asyncio.create_task(
                _learn_sentence_impl(request, req)
            )

            tokens_est = 0
            while not learn_task.done():
                await asyncio.sleep(1.5)
                tokens_est += 30
                if not learn_task.done():
                    yield f"data: {json.dumps({'type': 'progress', 'tokens': tokens_est, 'status': 'generating'})}\n\n"

            result = learn_task.result()
            if hasattr(result, 'body'):
                result = json.loads(result.body)

            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            decrement_user_request()

    return StreamingResponse(_generate(), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/word-detail-stream", tags=["Learning"], summary="Stream word detail via SSE")
async def word_detail_stream(
    request: Request,
    req: WordDetailRequest,
    _pw=Depends(require_password),
):
    """SSE word-detail endpoint with dictionary-first fast path."""

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

    wc_key = word_cache_key(req.word, req.target_language, req.meaning)
    cached = word_cache_get(wc_key)
    if cached is not None:
        logger.info("word-detail-stream cache hit", extra={"word": req.word, "lang": req.target_language})

        async def _cached():
            yield f"data: {json.dumps({'type': 'result', 'data': cached}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            _cached(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    dict_result = build_dictionary_word_detail(
        word=req.word,
        meaning=req.meaning,
        target_language=req.target_language,
        sentence_context=req.sentence_context,
    )
    if dict_result is not None:
        result = normalize_word_detail_payload(dict_result)
        word_cache_put(wc_key, result)

        async def _from_dict():
            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            _from_dict(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _generate():
        try:
            yield f"data: {json.dumps({'type': 'progress', 'status': 'Looking up word details...'})}\n\n"
            llm_task = asyncio.create_task(llm_word_detail(req.word, req.meaning, req.target_language))

            elapsed = 0.0
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
                yield f"data: {json.dumps({'type': 'heartbeat', 'elapsed': round(elapsed, 1)})}\n\n"

            result = llm_task.result()
            if result is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Translation engine unavailable'})}\n\n"
                return

            result = normalize_word_detail_payload(result)
            word_cache_put(wc_key, result)
            yield f"data: {json.dumps({'type': 'result', 'data': result}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("word-detail-stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/learn-multi", tags=["Learning"], summary="Translate multiple sentences at once")
async def learn_multi(
    request: Request,
    req: MultiSentenceRequest,
    _pw=Depends(require_password),
):

    if len(req.sentences) > MAX_INPUT_LEN * 5:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN * 5} characters)")

    parts = split_sentences(req.sentences)
    if not parts:
        raise HTTPException(400, "No sentences detected")

    if len(parts) == 1:
        single_req = SentenceRequest(
            sentence=parts[0],
            target_language=req.target_language,
            speaker_gender=req.speaker_gender,
            speaker_formality=req.speaker_formality,
        )
        result = await _learn_sentence_impl(request, single_req)
        return {"mode": "single", "results": [{"sentence": parts[0], "result": result}]}

    results = []
    for sentence in parts[:10]:
        single_req = SentenceRequest(
            sentence=sentence,
            target_language=req.target_language,
            speaker_gender=req.speaker_gender,
            speaker_formality=req.speaker_formality,
        )
        try:
            result = await _learn_sentence_impl(request, single_req)
            results.append({"sentence": sentence, "result": result})
        except HTTPException as e:
            results.append({"sentence": sentence, "error": e.detail})

    return {"mode": "multi", "results": results}
