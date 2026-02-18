"""Learn-related API route handlers for Sentsei."""
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

logger = get_logger("sentsei.learn_routes")

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from fastapi.responses import StreamingResponse
import httpx

from models import (
    SUPPORTED_LANGUAGES, ALLOWED_DATA_KEYS,
    SentenceRequest, BreakdownRequest, MultiSentenceRequest,
)
from cache import (
    cache_key, cache_get, cache_put,
    extract_and_store_grammar_patterns, get_grammar_patterns,
)
from auth import (
    APP_PASSWORD, rate_limit_check, rate_limit_cleanup, get_rate_limit_key,
    require_password,
)
from llm import (
    OLLAMA_URL, OLLAMA_MODEL, OLLAMA_MODEL_FAST, LANGUAGE_MODEL_OVERRIDES,
    deterministic_pronunciation, deterministic_word_pronunciation,
    ensure_traditional_chinese, detect_sentence_difficulty,
    cedict_lookup, parse_json_object, split_sentences,
    ollama_chat, check_ollama_connectivity,
    get_model_for_language,
)

from surprise import (
    increment_user_request, decrement_user_request,
)

router = APIRouter()


# --- Injection check ---
MAX_INPUT_LEN = 500
_injection_patterns = [
    "ignore previous", "ignore above", "disregard", "forget your instructions",
    "you are now", "new instructions", "system prompt", "override",
    "```", "---", "###", "SYSTEM:", "USER:", "ASSISTANT:",
]


def _check_injection(text: str):
    lower_input = text.lower()
    for pattern in _injection_patterns:
        if pattern.lower() in lower_input:
            raise HTTPException(400, "Invalid input")


def _detect_input_language(sentence: str, input_lang: str = "auto"):
    if input_lang == "zh":
        return True
    elif input_lang == "en":
        return False
    else:
        return any('\u4e00' <= c <= '\u9fff' for c in sentence)


@router.post("/api/learn", tags=["Learning"], summary="Translate and break down a sentence",
              description="Translates a sentence into the target language with pronunciation, grammar notes, and word-by-word breakdown.")
async def learn_sentence(
    request: Request,
    req: SentenceRequest,
    _pw=Depends(require_password),
):
    return await _learn_sentence_impl(request, req)


async def _learn_sentence_impl(request: Request, req: SentenceRequest):
    """Core learn logic — no auth check, used by endpoint and internal callers."""
    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence or not req.sentence.strip():
        raise HTTPException(400, "Sentence cannot be empty")

    increment_user_request()

    if len(req.sentence) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")
    _check_injection(req.sentence)

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    gender = req.speaker_gender or "neutral"
    formality = req.speaker_formality or "polite"
    ck = cache_key(req.sentence, req.target_language, gender, formality)
    cached = cache_get(ck)
    if cached:
        decrement_user_request()
        if "difficulty" not in cached or cached.get("difficulty") is None:
            sd = detect_sentence_difficulty(req.sentence, cached.get("breakdown", []))
            cached["sentence_difficulty"] = sd
            cached["difficulty"] = sd.get("level")
        return cached

    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    lang_code = req.target_language

    script_examples = {
        "ko": "Korean script (한국어). Example: 커피 한 잔 주문하고 싶어요",
        "ja": "Japanese script (日本語). Example: コーヒーを一杯注文したいです. IMPORTANT: For Japanese, always note gender implications of pronouns (e.g. 私/watashi vs 僕/boku vs 俺/ore) and formality levels in your notes.",
        "he": "Hebrew script (עברית). Example: אני רוצה להזמין כוס קפה",
        "el": "Greek script (Ελληνικά). Example: Θέλω να παραγγείλω έναν καφέ",
        "zh": "Traditional Chinese (繁體中文). Example: 我想點一杯咖啡",
        "en": "English. Example: I want to order a coffee",
        "it": "Italian. Example: Vorrei ordinare un caffè",
        "es": "Spanish. Example: Quiero pedir un café",
    }
    script_hint = script_examples.get(lang_code, f"{lang_name} script")

    input_is_chinese = _detect_input_language(req.sentence, getattr(req, 'input_language', 'auto') or 'auto')
    source_lang = "Traditional Chinese (繁體中文, 台灣用法)" if input_is_chinese else "English"
    source_lang_short = "繁體中文" if input_is_chinese else "English"

    formality_hints = {
        "ko": {"casual": "반말", "polite": "존댓말", "formal": "격식체"},
        "ja": {"casual": "タメ口", "polite": "です/ます", "formal": "敬語"},
        "zh": {"casual": "口語", "polite": "standard", "formal": "書面"},
    }
    form_hint = ""
    if lang_code in formality_hints:
        form_hint = f" ({formality_hints[lang_code].get(formality, formality)})"

    prompt = f"""Translate into {lang_name} ({script_hint}): "{req.sentence}"
Speaker: {gender}, {formality}{form_hint}. Explanations in {source_lang_short}.

Return JSON only:
{{"translation":"{lang_name} text","pronunciation":"romanized","literal":"word-by-word in {source_lang_short}",
"breakdown":[{{"word":"..","pronunciation":"..","meaning":"in {source_lang_short}","difficulty":"easy|medium|hard","note":"grammar note in {source_lang_short} or null"}}],
"grammar_notes":["1-3 key patterns in {source_lang_short}"],"cultural_note":"or null",
"formality":"{formality}","alternative":"alt sentence | PRONUNCIATION or null",
"native_expression":"native way | pronunciation | explanation in {source_lang_short}, or null if direct translation is already natural"}}

Rules: translation MUST be in {lang_name} script. All meanings/notes in {source_lang_short} only. Break down only words from the translation.{' 繁體中文 Taiwan usage only, no 簡體.' if lang_code == 'zh' or input_is_chinese else ''}"""

    model = get_model_for_language(lang_code)

    if lang_code == "zh":
        system_msg = f"台灣華語教師。繁體中文台灣用法，禁簡體/大陸用語。所有解釋用{source_lang_short}。JSON only."
    elif input_is_chinese:
        system_msg = f"{lang_name} teacher. Translate into {lang_name} only. Explanations in {source_lang_short}. 繁體中文 for Chinese text. JSON only."
    else:
        system_msg = f"{lang_name} teacher. Translate into {lang_name} only. Explanations in {source_lang_short}. JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=model, temperature=0.3, num_predict=1024, timeout=60
    )

    if text is None:
        # Ollama is down — check if we have ANY cached result for this sentence (ignoring gender/formality)
        from cache import cache_scan_prefix
        fallback = cache_scan_prefix(req.sentence, req.target_language)
        if fallback:
            decrement_user_request()
            fallback["from_cache"] = True
            fallback["ollama_offline"] = True
            return fallback
        raise HTTPException(502, "Translation engine offline and no cached results available")

    result = parse_json_object(text)
    if not result:
        raise HTTPException(502, f"Failed to parse LLM response: {text[:300]}")

    # Validation: check if translation is just echoing back the input
    translation_text = result.get("translation", "")
    input_clean = req.sentence.strip().replace(" ", "")
    trans_clean = translation_text.strip().replace(" ", "")
    if lang_code not in ("zh", "en") and input_is_chinese and trans_clean and input_clean:
        cjk_ratio = sum(1 for c in trans_clean if '\u4e00' <= c <= '\u9fff') / max(len(trans_clean), 1)
        if cjk_ratio > 0.5 and lang_code in ("ja",):
            if trans_clean == input_clean or input_clean in trans_clean:
                result["_warning"] = "Translation may be echoing input. Model struggled with this input."
        elif cjk_ratio > 0.5 and lang_code not in ("ja", "zh"):
            result["_warning"] = "Translation may be in the wrong language."

    # Post-process: detect English words leaking into Chinese translations
    if lang_code == "zh" and translation_text:
        english_words = _re.findall(r'[a-zA-Z]{2,}', translation_text)
        if english_words:
            en_to_zh = {
                'menu': '菜單', 'bill': '帳單', 'coffee': '咖啡', 'beer': '啤酒',
                'ok': '好', 'sorry': '抱歉', 'thanks': '謝謝', 'thank': '謝',
                'taxi': '計程車', 'bus': '公車', 'hotel': '旅館', 'wifi': '無線網路',
                'email': '電子郵件', 'phone': '手機', 'app': '應用程式',
                'restaurant': '餐廳', 'bar': '酒吧', 'shop': '商店',
            }
            fixed = translation_text
            for word in english_words:
                replacement = en_to_zh.get(word.lower())
                if replacement:
                    fixed = fixed.replace(word, replacement)
            if fixed != translation_text:
                result["translation"] = fixed
                translation_text = fixed

    # Override pronunciation with deterministic libraries
    det_pron = deterministic_pronunciation(translation_text, lang_code)
    if det_pron:
        result["pronunciation"] = det_pron

    breakdown = result.get("breakdown", [])
    for item in breakdown:
        word = item.get("word", "")
        word_pron = deterministic_word_pronunciation(word, lang_code)
        if word_pron:
            item["pronunciation"] = word_pron

    # Re-segment Chinese breakdowns if character-by-character
    if lang_code == "zh" and breakdown and translation_text:
        avg_word_len = sum(len(item.get("word", "")) for item in breakdown) / max(len(breakdown), 1)
        if avg_word_len <= 1.2 and len(breakdown) > 3:
            import jieba
            words = list(jieba.cut(translation_text.replace("，", "").replace("。", "").replace("！", "").replace("？", "")))
            words = [w.strip() for w in words if w.strip()]
            new_breakdown = []
            for w in words:
                pron = deterministic_word_pronunciation(w, lang_code) or ""
                meaning = cedict_lookup(w)
                if not meaning:
                    chars = [cedict_lookup(c) or "" for c in w]
                    combined = " + ".join(c for c in chars if c)
                    meaning = combined if combined else w
                new_breakdown.append({"word": w, "pronunciation": pron, "meaning": meaning, "difficulty": "medium", "note": None})
            breakdown = new_breakdown
            result["breakdown"] = breakdown

    # Filter hallucinated breakdown words
    if breakdown and translation_text:
        clean_translation = translation_text.replace(" ", "").replace("，", "").replace(",", "").replace("。", "").replace(".", "").replace("！", "").replace("!", "").replace("？", "").replace("?", "")
        result["breakdown"] = [item for item in breakdown if item.get("word", "").replace(" ", "") in clean_translation]

    # Japanese gender/pronoun warnings
    if lang_code == "ja" and translation_text:
        gender_markers = {
            "私": ("watashi", "neutral/formal, used by all genders"),
            "僕": ("boku", "masculine, casual — used by boys/men"),
            "俺": ("ore", "masculine, very casual/rough — used by men"),
            "あたし": ("atashi", "feminine, casual — used by women/girls"),
            "わたくし": ("watakushi", "very formal, gender-neutral"),
        }
        detected = []
        for marker, (reading, desc) in gender_markers.items():
            if marker in translation_text:
                detected.append(f"⚠️ '{marker}' ({reading}): {desc}")
        if detected:
            gender_note = " | ".join(detected)
            existing_notes = result.get("grammar_notes", []) or []
            existing_notes.insert(0, f"Gender/formality note: {gender_note}")
            result["grammar_notes"] = existing_notes

    # Fix native_expression
    native = result.get("native_expression")
    translation = result.get("translation", "")
    if native:
        if "|" in native:
            parts = native.split("|", 2)
            native_sentence = parts[0].strip()
            native_explanation = parts[2].strip() if len(parts) >= 3 else ""
        else:
            native_sentence = native.strip()
            native_explanation = ""

        if native_sentence.replace("。", "").replace("！", "").replace("？", "").strip() == translation.replace("。", "").replace("！", "").replace("？", "").strip():
            result["native_expression"] = None
        elif native_sentence:
            native_pron = deterministic_pronunciation(native_sentence, lang_code) or ""
            if native_explanation:
                cjk_count = sum(1 for c in native_explanation if '\u4e00' <= c <= '\u9fff')
                cjk_ratio = cjk_count / max(len(native_explanation), 1)
                if not input_is_chinese and cjk_ratio > 0.3:
                    native_explanation = ""
                elif input_is_chinese and cjk_ratio < 0.1 and len(native_explanation) > 10:
                    native_explanation = ""
            result["native_expression"] = f"{native_sentence} | {native_pron} | {native_explanation}".rstrip(" |")

    # Taiwanese native phrases
    if lang_code == "zh":
        try:
            phrases_file = Path(__file__).parent / "taiwanese_phrases.json"
            if phrases_file.exists():
                tw_data = json.loads(phrases_file.read_text())
                input_lower = req.sentence.lower()
                trans_text = translation_text or ""
                matches = []
                for p in tw_data.get("phrases", []):
                    score = sum(1 for kw in p["keywords"] if kw.lower() in input_lower or kw in trans_text)
                    if score > 0:
                        matches.append((score, p))
                matches.sort(key=lambda x: -x[0])
                if matches:
                    top = matches[:2]
                    result["tw_native_phrases"] = [
                        {"phrase": m[1]["phrase"], "pinyin": m[1]["pinyin"], "meaning": m[1]["meaning"], "context": m[1].get("context", "")}
                        for m in top
                    ]
        except Exception:
            pass

    # Enforce explanations in source language for English input
    if not input_is_chinese:
        def _mostly_cjk(s):
            if not s: return False
            cjk = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
            return cjk / max(len(s.replace(" ", "")), 1) > 0.3

        notes = result.get("grammar_notes", []) or []
        cleaned_notes = []
        for note in notes:
            if not _mostly_cjk(note):
                cleaned_notes.append(note)
            else:
                salvaged = _re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]+', '', note).strip()
                salvaged = _re.sub(r'\s+', ' ', salvaged).strip(' ()-:,.')
                if len(salvaged) > 15:
                    cleaned_notes.append(salvaged)
        result["grammar_notes"] = cleaned_notes

        if not cleaned_notes and notes:
            target = result.get("translation", "")
            if target:
                result["grammar_notes"] = ["Note: The original grammar notes were in the target language. Review the breakdown for word-by-word details."]

        for item in result.get("breakdown", []):
            meaning = item.get("meaning", "")
            if any('\u4e00' <= c <= '\u9fff' for c in meaning):
                cleaned = _re.sub(r'[\u4e00-\u9fff]+', '', meaning).strip()
                cleaned = _re.sub(r'^\(?\s*', '', cleaned)
                cleaned = _re.sub(r'\s*\)?\s*$', '', cleaned)
                if cleaned:
                    item["meaning"] = cleaned

    result["sentence_difficulty"] = detect_sentence_difficulty(req.sentence, result.get("breakdown", []))
    result["difficulty"] = result.get("sentence_difficulty", {}).get("level")
    # Attach minimal context so feedback-based cache invalidation can work
    result.setdefault("original_sentence", req.sentence)
    result.setdefault("target_language", req.target_language)
    result = ensure_traditional_chinese(result)
    cache_put(ck, result)

    try:
        extract_and_store_grammar_patterns(result, lang_code, req.sentence)
    except Exception:
        logger.exception("Grammar extraction error", extra={"component": "grammar"})

    decrement_user_request()

    return result


@router.post("/api/learn-fast", tags=["Learning"], summary="Fast translation (no breakdown)")
async def learn_fast(
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

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    gender = req.speaker_gender or "neutral"
    formality = req.speaker_formality or "polite"
    ck = cache_key(req.sentence, req.target_language, gender, formality)
    cached = cache_get(ck)
    if cached:
        if "difficulty" not in cached or cached.get("difficulty") is None:
            sd = detect_sentence_difficulty(req.sentence, cached.get("breakdown", []))
            cached["sentence_difficulty"] = sd
            cached["difficulty"] = sd.get("level")
        return {**cached, "complete": True}

    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    lang_code = req.target_language
    input_is_chinese = _detect_input_language(req.sentence, getattr(req, 'input_language', 'auto') or 'auto')
    source_lang_short = "繁體中文" if input_is_chinese else "English"

    script_examples = {
        "ko": "Korean script (한국어)", "ja": "Japanese script (日本語)",
        "he": "Hebrew script (עברית)", "el": "Greek script (Ελληνικά)",
        "zh": "Traditional Chinese (繁體中文)", "en": "English",
        "it": "Italian", "es": "Spanish",
    }
    script_hint = script_examples.get(lang_code, f"{lang_name} script")

    prompt = f"""Translate into {lang_name} ({script_hint}): "{req.sentence}"
Speaker: {gender}, {formality}. Explain in {source_lang_short}.
JSON only: {{"translation":"...","pronunciation":"romanized","literal":"word-by-word in {source_lang_short}","formality":"{formality}","native_expression":"native way | pronunciation | explanation in {source_lang_short}, or null"}}"""

    system_msg = f"{lang_name} translator. JSON only."
    if lang_code == "zh":
        system_msg += " 繁體中文 Taiwan usage only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=get_model_for_language(lang_code), temperature=0.3, num_predict=192, timeout=25
    )

    if text is None:
        # Ollama down — try any cached result for this sentence
        from cache import cache_scan_prefix
        fallback = cache_scan_prefix(req.sentence, req.target_language)
        if fallback:
            return {**fallback, "complete": True, "from_cache": True, "ollama_offline": True}
        raise HTTPException(502, "Translation engine offline and no cached results available")

    result = parse_json_object(text)
    if not result:
        raise HTTPException(502, "Failed to parse LLM response")

    translation_text = result.get("translation", "")

    det_pron = deterministic_pronunciation(translation_text, lang_code)
    if det_pron:
        result["pronunciation"] = det_pron

    result = ensure_traditional_chinese(result)

    native = result.get("native_expression")
    if native and "|" in str(native):
        parts = str(native).split("|", 2)
        native_sentence = parts[0].strip()
        native_explanation = parts[2].strip() if len(parts) >= 3 else ""
        native_pron = deterministic_pronunciation(native_sentence, lang_code) or ""
        result["native_expression"] = f"{native_sentence} | {native_pron} | {native_explanation}".rstrip(" |")

    result["complete"] = False
    return result


