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

from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import StreamingResponse
import httpx

from models import (
    SUPPORTED_LANGUAGES, ALLOWED_DATA_KEYS,
    SentenceRequest, BreakdownRequest, MultiSentenceRequest,
    WordDetailRequest, ContextExamplesRequest, AnkiExportEntry,
    QuizCheckRequest, CompareRequest, FeedbackRequest, AuthRequest,
    CURATED_SENTENCES, STORIES, SURPRISE_SENTENCES_EN, SURPRISE_SENTENCES_ZH,
)
from cache import (
    cache_key, cache_get, cache_put,
    extract_and_store_grammar_patterns, get_grammar_patterns,
    get_quiz_answers, cleanup_quiz_answers,
)
from auth import (
    APP_PASSWORD, rate_limit_check, rate_limit_cleanup,
    get_db, init_user_db, hash_password, verify_password,
    create_session, get_user_from_token, extract_bearer_token,
)
from llm import (
    OLLAMA_URL, OLLAMA_MODEL,
    deterministic_pronunciation, deterministic_word_pronunciation,
    ensure_traditional_chinese, detect_sentence_difficulty,
    cedict_lookup, parse_json_object, split_sentences,
    new_quiz_id, translation_hint, sanitize_tsv_cell, anki_language_label,
    ollama_chat, check_ollama_connectivity,
)

router = APIRouter()

# --- Surprise Bank State ---
_surprise_bank: dict = defaultdict(list)
_surprise_bank_filling = False
_user_request_active: Optional[asyncio.Event] = None
_user_request_count = 0
SURPRISE_BANK_TARGET = 6


def _get_user_event() -> asyncio.Event:
    global _user_request_active
    if _user_request_active is None:
        _user_request_active = asyncio.Event()
        _user_request_active.set()
    return _user_request_active


# --- Feedback ---
FEEDBACK_FILE = Path(__file__).parent / "feedback.jsonl"


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


@router.post("/api/learn")
async def learn_sentence(
    request: Request,
    req: SentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence or not req.sentence.strip():
        raise HTTPException(400, "Sentence cannot be empty")

    global _user_request_count
    _user_request_count += 1
    _get_user_event().clear()

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
        _user_request_count -= 1
        if _user_request_count <= 0:
            _user_request_count = 0
            _get_user_event().set()
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

    prompt = f"""TASK: Translate this sentence into {lang_name} and break it down.

TARGET LANGUAGE: {lang_name} — {script_hint}
SOURCE LANGUAGE (what the user typed in): {source_lang}

INPUT: "{req.sentence}"

IMPORTANT: The input may contain mixed languages (e.g. Chinese + English words). Understand the MEANING of the entire sentence, then translate the WHOLE MEANING into {lang_name}. Do NOT keep any source language words in the translation.

You MUST translate into {lang_name}. For example, if target is Korean, write 한국어. If Japanese, write 日本語. If Hebrew, write עברית. Do NOT output Chinese unless the target language IS Chinese. Do NOT echo back the input sentence as the translation.

CRITICAL RULES:
1. The "translation" field MUST be written in {lang_name} using {script_hint}. NOT Chinese, NOT English (unless target IS English).
2. The "word" fields in breakdown MUST be {lang_name} words in {lang_name} script.
3. ALL "meaning" fields MUST be in {source_lang_short}. ALL "grammar_notes" MUST be in {source_lang_short}. ALL "cultural_note" and "note" fields MUST be in {source_lang_short}. The user reads {source_lang_short}, so write ALL explanations in {source_lang_short}. NEVER write explanations in Chinese if the source is English. NEVER write explanations in English if the source is Chinese.
4. When writing ANY Chinese text, use ONLY Traditional Chinese (繁體中文) with Taiwan usage. NEVER Simplified Chinese.
5. Do NOT mix languages. Explanations in one language only.

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "translation": "DIRECT translation — stay close to the structure and meaning of the input sentence. Translate faithfully in {lang_name} script (e.g. for Korean use 한글, for Japanese use 日本語, etc.)",
  "pronunciation": "FULL romanized pronunciation of the translation using standard systems: Japanese=Hepburn romaji (e.g. oshiete kudasai, NOT OLLOW-te), Chinese=pinyin with tones, Korean=Revised Romanization, Hebrew=standard transliteration, Greek=standard transliteration",
  "literal": "word-by-word literal translation back to the detected source language",
  "breakdown": [
    {{
      "word": "each word/particle EXACTLY as it appears in the translation above — do NOT invent words that aren't in the translation. Split naturally (e.g. for Chinese: 我/練得越多/越/覺得/自信, NOT 越自信 if the sentence says 越覺得自信). For grammar patterns like 越...越..., show each 越 with its attached word separately.",
      "pronunciation": "romanized pronunciation (Japanese: Hepburn romaji like 'kudasai', NOT made-up spellings)",
      "meaning": "meaning in {source_lang_short} ONLY",
      "difficulty": "easy|medium|hard",
      "note": "brief grammar/usage note in {source_lang_short} ONLY, otherwise null. NEVER write notes in {lang_name} when source is {source_lang_short}."
    }}
  ],
  "grammar_notes": [
    "Key grammar pattern or structure explanation (1-3 short notes). MUST be written in {source_lang_short}. NEVER in {lang_name} unless {lang_name} IS {source_lang_short}."
  ],
  "cultural_note": "optional cultural context or usage tip (in the detected source language), null if none",
  "formality": "casual|polite|formal — what register this translation uses",
  "alternative": "an alternative way to say this (different formality or phrasing), or null",
  "native_expression": "ALWAYS provide this. This is how a native {lang_name} speaker would NATURALLY rephrase this — more colloquial, idiomatic, or restructured compared to the direct translation above. Format: 'native sentence | FULL PRONUNCIATION | EXPLANATION IN {source_lang_short}'. Example for Chinese: '這咖啡也太好喝了吧 | zhè kāfēi yě tài hǎo hē le ba | Uses 也太...了吧 (yě tài...le ba), a common exclamation pattern meaning \"this is way too [good]\"'. When mentioning {lang_name} words in the explanation, always add pronunciation and meaning in parentheses. CRITICAL: The native expression must preserve the SAME MEANING as the input. Do NOT change key concepts (e.g. if the input says 'confident', the native expression must also be about confidence, NOT progress or something else). You can change structure, formality, and phrasing, but the core meaning must stay the same. If the native expression uses different vocabulary, explain WHY in the explanation. Only null if the direct translation is already exactly how a native would say it."
}}"""

    speaker_block = f"""
SPEAKER IDENTITY:
- Gender: {gender} — adjust pronouns, gendered words accordingly. For Japanese: use 僕/俺 for male, あたし for female, 私 for neutral. For Hebrew: adjust verb conjugation, adjectives, pronouns. For Spanish/Italian: adjust adjective agreement.
- Formality: {formality} — use appropriate register. For Korean: casual=반말, polite=존댓말, formal=격식체. For Japanese: casual=タメ口, polite=です/ます, formal=敬語. For Chinese: casual=street/口語 (e.g. 老闆買單, 我要吃拉麵), polite=standard (e.g. 請問可以結帳嗎), formal=written/公文. IMPORTANT: If casual, translate like how a young Taiwanese person would actually say it in daily life — short, direct, colloquial. Do NOT use 請問/可以...嗎 patterns for casual speech.
The "formality" field in the response MUST be "{formality}".
"""
    prompt = prompt + "\n" + speaker_block

    model = OLLAMA_MODEL

    taiwan_chinese_rules = """
TAIWAN CHINESE RULES (apply when target is Chinese or explanations are in Chinese):
- Use ONLY Traditional Chinese (繁體中文) with Taiwan usage (台灣用法)
- NEVER use mainland China phrasing. Use Taiwanese daily speech patterns.
- Examples of correct Taiwan vs incorrect mainland usage:
  - ✅ 跟我說一個笑話 / ❌ 給我講一個笑話
  - ✅ 講個笑話給我聽 / ❌ 給我講個笑話
  - ✅ 好棒 / ❌ 真棒
  - ✅ 沒問題 / ❌ 沒事兒
  - ✅ 很厲害 / ❌ 牛逼
  - ✅ 軟體 / ❌ 軟件
  - ✅ 資訊 / ❌ 信息
  - ✅ 影片 / ❌ 視頻
  - ✅ 計程車 / ❌ 出租車
  - ✅ 捷運 / ❌ 地鐵
  - ✅ 腳踏車 / ❌ 自行車
"""

    explanation_lang_instruction = f"CRITICAL: ALL explanations (meaning, grammar_notes, note, cultural_note) MUST be written in {source_lang_short}. Do NOT write explanations in any other language."

    if lang_code == "zh":
        casual_hint = ""
        if formality == "casual":
            casual_hint = "口語程度：口語/街頭用法。像台灣年輕人跟朋友或在小吃店講話一樣。例：'Can I get the bill?' → '老闆，買單！'，不要用'請問可以開帳單嗎'。簡短、直接、自然。"
        elif formality == "formal":
            casual_hint = "口語程度：正式/書面用法。使用敬語和完整句型。"
        else:
            casual_hint = "口語程度：禮貌/標準用法。"
        system_msg = f"你是一位台灣華語教師，專門教外國人學繁體中文（台灣用法）。翻譯必須完全使用繁體中文，絕對不可以使用簡體字或大陸用語。{casual_hint} 重要：翻譯中不可以夾雜任何英文單字（例如 menu 要翻成「菜單」，bill 要翻成「帳單」）。{explanation_lang_instruction} 請只回傳有效的 JSON 格式。\n{taiwan_chinese_rules}"
    elif input_is_chinese and lang_code == "en":
        system_msg = f"You are an English language teacher helping Chinese speakers learn English. The user writes in Chinese and you translate into ENGLISH. The 'translation' field MUST be in English. The 'pronunciation' field should be English pronunciation guide. The 'word' fields in breakdown MUST be English words. {explanation_lang_instruction} The 'native_expression' field should show how a native English speaker would naturally say it in English, with 繁體中文 explanation. Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    elif input_is_chinese:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. {explanation_lang_instruction} Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    else:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. {explanation_lang_instruction} Always respond with valid JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=model, temperature=0.3, num_predict=2048, timeout=120
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

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
    result = ensure_traditional_chinese(result)
    cache_put(ck, result)

    try:
        extract_and_store_grammar_patterns(result, lang_code, req.sentence)
    except Exception:
        logger.exception("Grammar extraction error", extra={"component": "grammar"})

    _user_request_count -= 1
    if _user_request_count <= 0:
        _user_request_count = 0
        _get_user_event().set()

    return result


@router.post("/api/learn-fast")
async def learn_fast(
    request: Request,
    req: SentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
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

    prompt = f"""Translate into {lang_name}: "{req.sentence}"
Speaker: {gender}, {formality}
Target script: {script_hint}

Return ONLY valid JSON (no markdown):
{{"translation": "the translation in {lang_name} script", "pronunciation": "full romanized pronunciation", "literal": "word-by-word literal translation in {source_lang_short}", "formality": "{formality}", "native_expression": "how a native speaker would naturally say this, or null if the direct translation is already natural. Format: native sentence | pronunciation | brief explanation in {source_lang_short}"}}"""

    system_msg = f"You are a {lang_name} language teacher. Translate accurately. Return valid JSON only."
    if lang_code == "zh":
        system_msg += " Use ONLY Traditional Chinese (繁體中文) with Taiwan usage."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.3, num_predict=256, timeout=30
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

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


@router.post("/api/segment")
async def segment_sentence(
    request: Request,
    req: BreakdownRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    """Fast word segmentation using jieba + cedict. No LLM needed."""
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

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
        # For Japanese/Korean, just return each character/word with pronunciation
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
        # For other languages, split by spaces
        words = translation.split()
        breakdown = [{"word": w, "pronunciation": "", "meaning": "", "difficulty": "medium", "note": None} for w in words]
        return {"breakdown": breakdown, "source": "whitespace"}


@router.post("/api/breakdown")
async def get_breakdown(
    request: Request,
    req: BreakdownRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
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
  "alternative": "alternative phrasing in {lang_name}, or null"
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


@router.post("/api/learn-stream")
async def learn_sentence_stream(
    request: Request,
    req: SentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
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
            global _user_request_count
            _user_request_count += 1
            _get_user_event().clear()

            yield f"data: {json.dumps({'type': 'progress', 'tokens': 0, 'status': 'generating'})}\n\n"

            learn_task = asyncio.create_task(
                learn_sentence(request, req, x_app_password)
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
            _user_request_count -= 1
            if _user_request_count <= 0:
                _user_request_count = 0
                _get_user_event().set()

    return StreamingResponse(_generate(), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/learn-multi")
async def learn_multi(
    request: Request,
    req: MultiSentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

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
        result = await learn_sentence(request, single_req, x_app_password)
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
            result = await learn_sentence(request, single_req, x_app_password)
            results.append({"sentence": sentence, "result": result})
        except HTTPException as e:
            results.append({"sentence": sentence, "error": e.detail})

    return {"mode": "multi", "results": results}


@router.post("/api/word-detail")
async def word_detail(
    request: Request,
    req: WordDetailRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if len(req.word) > MAX_INPUT_LEN or len(req.meaning) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")
    if req.sentence_context and len(req.sentence_context) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    meaning_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.meaning)
    explain_lang = "繁體中文 (Traditional Chinese, Taiwan usage)" if meaning_is_chinese else "English"

    context_line = f'\nThe word appeared in this sentence: "{req.sentence_context}"' if req.sentence_context else ""

    prompt = f"""Give details about the {lang_name} word "{req.word}" (meaning: {req.meaning}).{context_line}

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "examples": [
    {{"sentence": "example sentence using the word in {lang_name}", "pronunciation": "romanized", "meaning": "translation in {explain_lang}"}},
    {{"sentence": "another example", "pronunciation": "romanized", "meaning": "translation in {explain_lang}"}}
  ],
  "conjugations": [
    {{"form": "conjugated/inflected form in {lang_name}", "label": "tense/form name in {explain_lang}"}}
  ],
  "related": [
    {{"word": "related word in {lang_name}", "meaning": "meaning in {explain_lang}"}}
  ]
}}

Rules:
- Give 2-3 example sentences, 2-4 conjugations/forms (if applicable), 2-3 related words
- If the word doesn't conjugate (particles, nouns), return empty conjugations array
- All explanations in {explain_lang}
- Examples should be simple, practical sentences"""

    system_msg = f"You are a {lang_name} vocabulary teacher. Respond with valid JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.3, num_predict=1024, timeout=60
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    result = parse_json_object(text)
    if not result:
        return {"examples": [], "conjugations": [], "related": []}

    result = ensure_traditional_chinese(result)
    return result


@router.post("/api/context-examples")
async def context_examples(
    request: Request,
    req: ContextExamplesRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
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


@router.get("/api/languages")
async def get_languages():
    return SUPPORTED_LANGUAGES


@router.post("/api/export-anki")
async def export_anki(
    entries: List[AnkiExportEntry],
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

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


@router.get("/api/surprise")
async def get_surprise_sentence(lang: str, input_lang: str = "en"):
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    bank_key = f"{lang}_{input_lang}"
    if _surprise_bank[bank_key]:
        idx = random.randrange(len(_surprise_bank[bank_key]))
        entry = _surprise_bank[bank_key].pop(idx)
        return {
            "language": lang,
            "sentence": entry["sentence"],
            "difficulty": entry["difficulty"],
            "category": entry["category"],
            "precomputed": True,
            "result": entry["result"],
        }

    pool = SURPRISE_SENTENCES_ZH if input_lang == "zh" else SURPRISE_SENTENCES_EN
    picked = random.choice(pool)
    return {
        "language": lang,
        "sentence": picked["sentence"],
        "difficulty": picked["difficulty"],
        "category": picked["category"],
    }


@router.get("/api/surprise-bank-status")
async def surprise_bank_status():
    status = {}
    for key, items in _surprise_bank.items():
        status[key] = len(items)
    return {"filling": _surprise_bank_filling, "banks": status}


@router.get("/api/health")
async def health_check():
    from cache import _translation_cache, CACHE_MAX, CACHE_TTL
    ollama_ok = await check_ollama_connectivity()
    cache_size = len(_translation_cache)
    bank_total = sum(len(v) for v in _surprise_bank.values())
    bank_langs = len(_surprise_bank)

    return {
        "status": "ok" if ollama_ok else "degraded",
        "ollama": {"reachable": ollama_ok, "url": OLLAMA_URL, "model": OLLAMA_MODEL},
        "cache": {"entries": cache_size, "max": CACHE_MAX, "ttl_hours": CACHE_TTL / 3600},
        "surprise_bank": {"total_entries": bank_total, "languages": bank_langs, "filling": _surprise_bank_filling},
    }


@router.api_route("/api/quiz", methods=["GET", "POST"])
async def get_quiz(
    request: Request,
    lang: str,
    gender: str = "neutral",
    formality: str = "polite",
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[lang]
    quiz_answers = get_quiz_answers()

    history_items = []
    if request.method == "POST":
        try:
            body = await request.json()
            history_items = body.get("history", [])
        except Exception:
            pass

    if history_items:
        picked = random.choice(history_items)
        sentence = picked["translation"]
        source_sentence = picked["sentence"]
        pronunciation = picked.get("pronunciation", "")
        quiz_id = new_quiz_id(lang, sentence)
        cleanup_quiz_answers()
        quiz_answers[quiz_id] = {
            "answer_en": source_sentence,
            "answer_zh": source_sentence,
            "sentence": sentence,
            "created_at": time.time(),
        }
        return {
            "quiz_id": quiz_id,
            "sentence": sentence,
            "pronunciation": pronunciation,
            "source": "Your history",
            "hint": source_sentence[:3] + "..." if len(source_sentence) > 3 else source_sentence,
            "language": lang,
        }

    sentence_pool = CURATED_SENTENCES.get(lang, [])
    if not sentence_pool:
        raise HTTPException(404, "No curated sentences found for this language")

    picked = random.choice(sentence_pool)
    sentence = picked["sentence"]

    prompt = f"""Translate this {lang_name} sentence into both English and Traditional Chinese (Taiwan usage).

Sentence: "{sentence}"
Context:
- Speaker gender: {gender}
- Formality: {formality}

Return ONLY valid JSON:
{{
  "translation_en": "Natural English meaning",
  "translation_zh": "Natural Traditional Chinese meaning (Taiwan usage)"
}}"""

    system_msg = "You are a translation assistant. Return valid JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.2, num_predict=256, timeout=60
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    parsed = parse_json_object(text) or {}
    translation_en = (parsed.get("translation_en") or "").strip()
    translation_zh = (parsed.get("translation_zh") or "").strip()

    if not translation_en and not translation_zh:
        raise HTTPException(502, "Failed to generate quiz answer")
    if not translation_en:
        translation_en = translation_zh
    if not translation_zh:
        translation_zh = translation_en

    quiz_id = new_quiz_id(lang, sentence)
    cleanup_quiz_answers()
    quiz_answers[quiz_id] = {
        "created_at": time.time(),
        "sentence": sentence,
        "language": lang,
        "source": picked.get("source", ""),
        "answer_en": translation_en,
        "answer_zh": translation_zh,
    }

    return {
        "quiz_id": quiz_id,
        "sentence": sentence,
        "source": picked.get("source", ""),
        "language": lang,
        "hint": translation_hint(translation_en),
        "pronunciation": deterministic_pronunciation(sentence, lang),
    }


@router.post("/api/quiz-check")
async def quiz_check(
    request: Request,
    req: QuizCheckRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    answer = req.answer.strip()
    if not answer:
        raise HTTPException(400, "Answer is required")

    cleanup_quiz_answers()
    quiz_answers = get_quiz_answers()
    quiz = quiz_answers.get(req.quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found or expired")

    if req.target_language != quiz.get("language"):
        raise HTTPException(400, "Quiz language mismatch")

    lang_name = SUPPORTED_LANGUAGES.get(quiz["language"], quiz["language"])

    prompt = f"""Evaluate whether the learner answer captures the MEANING of the target sentence.
Do not require exact wording.

Target sentence ({lang_name}): "{quiz['sentence']}"
Reference English meaning: "{quiz['answer_en']}"
Reference Traditional Chinese meaning: "{quiz['answer_zh']}"
Learner answer: "{answer}"

Scoring rubric:
- perfect: meaning is fully accurate and complete
- good: meaning is correct with minor wording differences
- partial: some meaning is correct but key details are missing or off
- wrong: meaning is mostly incorrect

Return JSON only in this format:
{{"score": "perfect|good|partial|wrong", "feedback": "brief explanation"}}"""

    system_msg = "You are a translation quiz grader. Grade semantic equivalence only. Return strict JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=OLLAMA_MODEL, temperature=0.1, num_predict=196, timeout=60
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    parsed = parse_json_object(text) or {}
    score = str(parsed.get("score", "")).strip().lower()
    if score not in {"perfect", "good", "partial", "wrong"}:
        score = "wrong"
    feedback = str(parsed.get("feedback", "")).strip() or "Meaning does not match closely enough."

    answer_en = quiz.get("answer_en", "").strip()
    answer_zh = quiz.get("answer_zh", "").strip()
    if answer_en and answer_zh and answer_zh != answer_en:
        correct_answer = f"{answer_en} / {answer_zh}"
    else:
        correct_answer = answer_en or answer_zh

    return {
        "correct": score in {"perfect", "good"},
        "score": score,
        "correct_answer": correct_answer,
        "feedback": feedback,
    }


@router.post("/api/compare")
async def compare_sentence(
    request: Request,
    req: CompareRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence.strip():
        raise HTTPException(400, "Sentence is required")

    if len(req.sentence) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    input_is_chinese = _detect_input_language(req.sentence, req.input_language or "auto")
    skip_langs = {"zh"} if input_is_chinese else {"en"}
    target_langs = [code for code in SUPPORTED_LANGUAGES if code not in skip_langs]

    results = []
    for lang_code in target_langs:
        single_req = SentenceRequest(
            sentence=req.sentence,
            target_language=lang_code,
            input_language=req.input_language,
            speaker_gender=req.speaker_gender,
            speaker_formality=req.speaker_formality,
        )
        try:
            result = await learn_sentence(request, single_req, x_app_password)
            if hasattr(result, 'body'):
                result = json.loads(result.body)
            results.append({
                "language": lang_code,
                "language_name": SUPPORTED_LANGUAGES[lang_code],
                "translation": result.get("translation", ""),
                "pronunciation": result.get("pronunciation", ""),
                "formality": result.get("formality", ""),
                "literal": result.get("literal", ""),
                "difficulty": result.get("difficulty"),
            })
        except HTTPException as e:
            if e.status_code == 429:
                break
            results.append({"language": lang_code, "language_name": SUPPORTED_LANGUAGES[lang_code], "error": str(e.detail)})
        except Exception as e:
            results.append({"language": lang_code, "language_name": SUPPORTED_LANGUAGES[lang_code], "error": str(e)})

    return {"sentence": req.sentence, "results": results}


@router.get("/api/stories")
async def list_stories():
    return [
        {"id": s["id"], "title": s["title"], "source": s["source"], "language": s["language"], "sentence_count": len(s["sentences"])}
        for s in STORIES.values()
    ]


@router.get("/api/story/{story_id}")
async def get_story(story_id: str):
    story = STORIES.get(story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    return story


@router.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest, x_app_password: Optional[str] = Header(default=None)):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")
    if not req.message or not req.message.strip():
        raise HTTPException(400, "Feedback cannot be empty")
    if len(req.message) > 1000:
        raise HTTPException(400, "Feedback too long")

    import datetime
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "message": req.message.strip(),
        "sentence": req.sentence,
        "translation": req.translation,
        "target_language": req.target_language,
    }
    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True}


@router.get("/api/feedback-list")
async def list_feedback(x_app_password: Optional[str] = Header(default=None), limit: int = 50, offset: int = 0):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")
    entries = []
    if FEEDBACK_FILE.exists():
        for line in FEEDBACK_FILE.read_text().strip().splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    entries.reverse()
    return {"total": len(entries), "entries": entries[offset:offset + limit]}


@router.delete("/api/feedback/{index}")
async def delete_feedback(index: int, x_app_password: Optional[str] = Header(default=None)):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")
    if not FEEDBACK_FILE.exists():
        raise HTTPException(404, "No feedback file")
    lines = [l for l in FEEDBACK_FILE.read_text().strip().splitlines() if l.strip()]
    file_index = len(lines) - 1 - index
    if file_index < 0 or file_index >= len(lines):
        raise HTTPException(404, "Index out of range")
    lines.pop(file_index)
    FEEDBACK_FILE.write_text("\n".join(lines) + "\n" if lines else "")
    return {"ok": True}


@router.get("/api/grammar-patterns")
async def list_grammar_patterns(lang: Optional[str] = None, x_app_password: Optional[str] = Header(default=None)):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")
    patterns = list(get_grammar_patterns().values())
    if lang:
        patterns = [p for p in patterns if p.get("lang") == lang]
    patterns.sort(key=lambda p: -p.get("count", 0))
    return [
        {"id": p["id"], "name": p["name"], "lang": p["lang"], "explanation": p["explanation"], "count": p["count"], "example_count": len(p.get("examples", []))}
        for p in patterns
    ]


@router.get("/api/grammar-patterns/{pattern_id}")
async def get_grammar_pattern(pattern_id: str, x_app_password: Optional[str] = Header(default=None)):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")
    pattern = get_grammar_patterns().get(pattern_id)
    if not pattern:
        raise HTTPException(404, "Pattern not found")
    return pattern


# --- Auth Routes ---

@router.post("/api/auth/register")
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


@router.post("/api/auth/login")
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


@router.post("/api/auth/logout")
async def auth_logout(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    if token:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    return {"ok": True}


@router.get("/api/auth/me")
async def auth_me(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")
    return {"username": user["username"]}


@router.get("/api/user-data/{key}")
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

async def _precompute_one(sentence: str, lang: str, input_lang: str):
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                "http://127.0.0.1:8847/api/learn",
                json={
                    "sentence": sentence,
                    "target_language": lang,
                    "input_language": input_lang,
                    "speaker_gender": "neutral",
                    "speaker_formality": "polite",
                },
                headers={"X-App-Password": APP_PASSWORD},
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        logger.exception("Surprise bank precompute error", extra={"component": "surprise-bank"})
    return None


async def fill_surprise_bank_task():
    global _surprise_bank_filling
    await asyncio.sleep(10)
    _surprise_bank_filling = True
    logger.info("Starting surprise bank pre-computation", extra={"component": "surprise-bank"})
    count = 0
    for lang in SUPPORTED_LANGUAGES:
        for input_lang, pool in [("en", SURPRISE_SENTENCES_EN), ("zh", SURPRISE_SENTENCES_ZH)]:
            if lang == "en" and input_lang == "en": continue
            if lang == "zh" and input_lang == "zh": continue
            bank_key = f"{lang}_{input_lang}"
            samples = random.sample(pool, min(SURPRISE_BANK_TARGET, len(pool)))
            for s in samples:
                if len(_surprise_bank[bank_key]) >= SURPRISE_BANK_TARGET: break
                await _get_user_event().wait()
                result = await _precompute_one(s["sentence"], lang, input_lang)
                if result:
                    _surprise_bank[bank_key].append({
                        "sentence": s["sentence"],
                        "difficulty": s.get("difficulty", "medium"),
                        "category": s.get("category", "general"),
                        "result": result,
                    })
                    count += 1
                    if count % 10 == 0:
                        save_surprise_bank()
                await asyncio.sleep(0.5)
    _surprise_bank_filling = False
    logger.info("Surprise bank pre-computation complete", extra={"component": "surprise-bank", "count": count})
    save_surprise_bank()


async def refill_surprise_bank_task():
    while True:
        await asyncio.sleep(600)
        for lang in SUPPORTED_LANGUAGES:
            for input_lang, pool in [("en", SURPRISE_SENTENCES_EN), ("zh", SURPRISE_SENTENCES_ZH)]:
                if lang == "en" and input_lang == "en": continue
                if lang == "zh" and input_lang == "zh": continue
                bank_key = f"{lang}_{input_lang}"
                if len(_surprise_bank[bank_key]) < 2:
                    samples = random.sample(pool, min(4, len(pool)))
                    for s in samples:
                        await _get_user_event().wait()
                        result = await _precompute_one(s["sentence"], lang, input_lang)
                        if result:
                            _surprise_bank[bank_key].append({
                                "sentence": s["sentence"],
                                "difficulty": s.get("difficulty", "medium"),
                                "category": s.get("category", "general"),
                                "result": result,
                            })
                        await asyncio.sleep(1)
        save_surprise_bank()


def save_surprise_bank():
    try:
        bank_file = Path(__file__).parent / "surprise_bank.json"
        data = {k: v for k, v in _surprise_bank.items() if v}
        bank_file.write_text(json.dumps(data, ensure_ascii=False))
        logger.info("Surprise bank saved to disk", extra={"component": "surprise-bank", "count": sum(len(v) for v in data.values())})
    except Exception:
        logger.exception("Failed to save surprise bank", extra={"component": "surprise-bank"})


def load_surprise_bank():
    bank_file = Path(__file__).parent / "surprise_bank.json"
    if bank_file.exists():
        try:
            data = json.loads(bank_file.read_text())
            for key, items in data.items():
                _surprise_bank[key] = items
            logger.info("Loaded surprise bank from disk", extra={"component": "surprise-bank", "count": sum(len(v) for v in data.values())})
        except Exception:
            logger.exception("Failed to load surprise bank", extra={"component": "surprise-bank"})


def get_surprise_bank():
    return _surprise_bank
