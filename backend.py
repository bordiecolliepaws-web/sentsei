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

    prompt = f"""You are a language learning assistant. The user wants to learn how to say something in {lang_name}.

The input sentence is either English or Chinese. Detect which one it is automatically.

Input sentence: "{req.sentence}"

Use the detected source language for explanations:
- If source is English, write literal/meanings/grammar notes in English.
- If source is Chinese, write literal/meanings/grammar notes in Chinese.

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "translation": "the full sentence in {lang_name}",
  "pronunciation": "romanized pronunciation guide (e.g. pinyin, romaji, romanization)",
  "literal": "word-by-word literal translation back to the detected source language",
  "breakdown": [
    {{
      "word": "each word/particle in {lang_name}",
      "pronunciation": "romanized pronunciation",
      "meaning": "meaning in the detected source language",
      "difficulty": "easy|medium|hard",
      "note": "brief grammar/usage note if helpful, otherwise null"
    }}
  ],
  "grammar_notes": [
    "Key grammar pattern or structure explanation (1-3 short notes, in the detected source language)"
  ],
  "cultural_note": "optional cultural context or usage tip, null if none",
  "formality": "casual|polite|formal — what register this translation uses",
  "alternative": "an alternative way to say this (different formality or phrasing), or null"
}}"""

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")

    data = resp.json()
    text = data.get("response", "")

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
