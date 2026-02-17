"""Segment and breakdown API route handlers for Sentsei."""
import re as _re

from log import get_logger

logger = get_logger("sentsei.segment_routes")

from fastapi import APIRouter, Depends, HTTPException, Request

from models import SUPPORTED_LANGUAGES, BreakdownRequest
from cache import cache_key, cache_get
from auth import rate_limit_check, rate_limit_cleanup, get_rate_limit_key, require_password
from llm import (
    OLLAMA_MODEL,
    deterministic_pronunciation, deterministic_word_pronunciation,
    ensure_traditional_chinese, cedict_lookup, parse_json_object,
    ollama_chat,
)
from learn_routes import MAX_INPUT_LEN, _detect_input_language

router = APIRouter()


@router.post("/api/segment", tags=["Learning"], summary="Segment text into sentences")
async def segment_sentence(
    request: Request,
    req: BreakdownRequest,
    _pw=Depends(require_password),
):
    """Fast word segmentation using jieba + cedict. No LLM needed."""

    if len(req.sentence) > MAX_INPUT_LEN or len(req.translation) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_code = req.target_language
    translation = req.translation or ""

    if lang_code == "zh" and translation:
        import jieba
        # Strip punctuation for segmentation
        clean = translation.replace("，", "").replace("。", "").replace("！", "").replace("？", "").replace("、", "").replace("「", "").replace("」", "").replace("…", "")
        words = [w.strip() for w in jieba.cut(clean) if w.strip()]
        breakdown = []
        for w in words:
            pron = deterministic_word_pronunciation(w, lang_code) or ""
            meaning = cedict_lookup(w)
            if not meaning:
                chars = [cedict_lookup(c) or "" for c in w]
                combined = " + ".join(c for c in chars if c)
                meaning = combined if combined else ""
            breakdown.append({
                "word": w,
                "pronunciation": pron,
                "meaning": meaning,
                "difficulty": "medium",
                "note": None
            })
        return {"breakdown": breakdown, "source": "jieba+cedict"}
    elif lang_code in ("ja", "ko") and translation:
        words = translation.split() if lang_code == "ko" else [translation]
        breakdown = []
        for w in words:
            pron = deterministic_word_pronunciation(w, lang_code) or ""
            breakdown.append({
                "word": w,
                "pronunciation": pron,
                "meaning": "",
                "difficulty": "medium",
                "note": None
            })
        return {"breakdown": breakdown, "source": "deterministic"}
    else:
        words = translation.split()
        breakdown = []
        for w in words:
            pron = deterministic_word_pronunciation(w, lang_code) or ""
            breakdown.append({"word": w, "pronunciation": pron, "meaning": "", "difficulty": "medium", "note": None})
        source = "deterministic" if lang_code in ("el", "it", "es", "en") else "whitespace"
        return {"breakdown": breakdown, "source": source}


@router.post("/api/breakdown", tags=["Learning"], summary="Word-by-word breakdown of a translation")
async def get_breakdown(
    request: Request,
    req: BreakdownRequest,
    _pw=Depends(require_password),
):

    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if len(req.sentence) > MAX_INPUT_LEN or len(req.translation) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    lang_code = req.target_language
    input_is_chinese = _detect_input_language(req.sentence, getattr(req, 'input_language', 'auto') or 'auto')
    source_lang_short = "繁體中文" if input_is_chinese else "English"

    prompt = f"""Break down this {lang_name} translation word by word.

Original: "{req.sentence}"
Translation: "{req.translation}"

Return ONLY valid JSON:
{{
  "breakdown": [
    {{"word": "each word from the translation", "pronunciation": "romanized", "meaning": "meaning in {source_lang_short}", "difficulty": "easy|medium|hard", "note": "brief grammar note in {source_lang_short} or null"}}
  ],
  "grammar_notes": ["1-3 key grammar patterns in {source_lang_short}"],
  "cultural_note": "optional cultural context in {source_lang_short}, or null",
  "alternative": "alternative phrasing with pronunciation. Format: 'sentence | PRONUNCIATION'. Null if none"
}}

Rules:
- Break down ONLY words that appear in the translation
- All explanations in {source_lang_short}"""

    system_msg = f"You are a {lang_name} grammar teacher. Return valid JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.3, num_predict=1024, timeout=60
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    result = parse_json_object(text)
    if not result:
        raise HTTPException(502, "Failed to parse breakdown response")

    for item in result.get("breakdown", []):
        word = item.get("word", "")
        word_pron = deterministic_word_pronunciation(word, lang_code)
        if word_pron:
            item["pronunciation"] = word_pron

    breakdown = result.get("breakdown", [])
    if lang_code == "zh" and breakdown and req.translation:
        avg_word_len = sum(len(item.get("word", "")) for item in breakdown) / max(len(breakdown), 1)
        if avg_word_len <= 1.2 and len(breakdown) > 3:
            import jieba
            words = list(jieba.cut(req.translation.replace("，", "").replace("。", "").replace("！", "").replace("？", "")))
            words = [w.strip() for w in words if w.strip()]
            new_breakdown = []
            for w in words:
                pron = deterministic_word_pronunciation(w, lang_code) or ""
                meaning = cedict_lookup(w) or w
                new_breakdown.append({"word": w, "pronunciation": pron, "meaning": meaning, "difficulty": "medium", "note": None})
            result["breakdown"] = new_breakdown
            breakdown = new_breakdown

    if breakdown and req.translation:
        clean_translation = req.translation.replace(" ", "").replace("，", "").replace(",", "").replace("。", "").replace(".", "").replace("！", "").replace("!", "").replace("？", "").replace("?", "")
        result["breakdown"] = [item for item in breakdown if item.get("word", "").replace(" ", "") in clean_translation]

    result = ensure_traditional_chinese(result)
    return result
