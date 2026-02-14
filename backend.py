"""Sentsei — Sentence-based language learning app."""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

app = FastAPI()

APP_PASSWORD = "sentsei2026"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
TAIDE_MODEL = "jcai/llama3-taide-lx-8b-chat-alpha1:Q4_K_M"

SUPPORTED_LANGUAGES = {
    "he": "Hebrew",
    "ja": "Japanese",
    "ko": "Korean",
    "en": "English",
    "zh": "Chinese",
    "el": "Greek",
    "it": "Italian",
    "es": "Spanish",
}

class SentenceRequest(BaseModel):
    sentence: str
    target_language: str

@app.post("/api/learn")
async def learn_sentence(
    req: SentenceRequest,
    x_app_password: str | None = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[req.target_language]

    lang_code = req.target_language

    # Build script examples for the target language
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

    # Detect source language
    source_lang = "Traditional Chinese (繁體中文, 台灣用法)" if input_is_chinese else "English"
    source_lang_short = "繁體中文" if input_is_chinese else "English"

    prompt = f"""TASK: Translate this sentence into {lang_name} and break it down.

TARGET LANGUAGE: {lang_name} — {script_hint}
SOURCE LANGUAGE (what the user typed in): {source_lang}

INPUT: "{req.sentence}"

You MUST translate into {lang_name}. For example, if target is Korean, write 한국어. If Japanese, write 日本語. If Hebrew, write עברית. Do NOT output Chinese unless the target language IS Chinese.

CRITICAL RULES:
1. The "translation" field MUST be written in {lang_name} using {script_hint}. NOT Chinese, NOT English (unless target IS English).
2. The "word" fields in breakdown MUST be {lang_name} words in {lang_name} script.
3. ALL "meaning" fields MUST be in {source_lang_short}. ALL "grammar_notes" MUST be in {source_lang_short}. ALL "cultural_note" and "note" fields MUST be in {source_lang_short}. The user reads {source_lang_short}, so write ALL explanations in {source_lang_short}. NEVER write explanations in Chinese if the source is English. NEVER write explanations in English if the source is Chinese.
4. When writing ANY Chinese text, use ONLY Traditional Chinese (繁體中文) with Taiwan usage. NEVER Simplified Chinese.
5. Do NOT mix languages. Explanations in one language only.

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "translation": "the full sentence in {lang_name} script (e.g. for Korean use 한글, for Japanese use 日本語, etc.)",
  "pronunciation": "romanized pronunciation guide (e.g. pinyin, romaji, romanization)",
  "literal": "word-by-word literal translation back to the detected source language",
  "breakdown": [
    {{
      "word": "each word/particle written in {lang_name} script",
      "pronunciation": "romanized pronunciation",
      "meaning": "meaning in the detected source language",
      "difficulty": "easy|medium|hard",
      "note": "brief grammar/usage note if helpful, otherwise null"
    }}
  ],
  "grammar_notes": [
    "Key grammar pattern or structure explanation (1-3 short notes, in the detected source language)"
  ],
  "cultural_note": "optional cultural context or usage tip (in the detected source language), null if none",
  "formality": "casual|polite|formal — what register this translation uses",
  "alternative": "an alternative way to say this (different formality or phrasing), or null",
  "native_expression": "How a native {lang_name} speaker would naturally express this same idea (may differ significantly from direct translation). Include pronunciation and a brief explanation of why a native would say it this way. null if the translation is already how a native would say it."
}}"""

    # Detect if input looks Chinese (contains CJK unified ideographs)
    input_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.sentence)

    # Always use qwen2.5 for structured JSON (TAIDE can't reliably produce JSON)
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

    if lang_code == "zh":
        system_msg = f"You are a Taiwanese Chinese (繁體中文/台灣用法) language teacher. You translate into Traditional Chinese as spoken in Taiwan. NEVER use mainland Chinese phrasing or simplified characters. Think like a native Taiwanese speaker. Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    elif input_is_chinese:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. All Chinese explanations must use Traditional Chinese (繁體中文) with Taiwan usage (台灣用法). Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    else:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. Always respond with valid JSON only."

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")

    data = resp.json()
    text = data.get("message", {}).get("content", "")

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                raise HTTPException(502, f"Failed to parse LLM response: {text[:300]}")
        else:
            raise HTTPException(502, f"Failed to parse LLM response: {text[:300]}")

    return result

@app.get("/api/languages")
async def get_languages():
    return SUPPORTED_LANGUAGES

app.mount("/", StaticFiles(directory="static", html=True), name="static")
