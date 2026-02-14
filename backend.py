"""Sentsei — Sentence-based language learning app."""
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx

app = FastAPI()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SUPPORTED_LANGUAGES = {
    "ko": "Korean",
    "ja": "Japanese", 
    "zh": "Chinese (Mandarin)",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "vi": "Vietnamese",
    "th": "Thai",
    "ar": "Arabic",
    "hi": "Hindi",
    "ru": "Russian",
}

class SentenceRequest(BaseModel):
    sentence: str
    target_language: str  # language code

@app.post("/api/learn")
async def learn_sentence(req: SentenceRequest):
    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")
    
    lang_name = SUPPORTED_LANGUAGES[req.target_language]
    
    prompt = f"""You are a language learning assistant. The user wants to learn how to say something in {lang_name}.

Input sentence (English): "{req.sentence}"

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "translation": "the full sentence in {lang_name}",
  "pronunciation": "romanized pronunciation guide (e.g. pinyin, romaji, romanization)",
  "literal": "word-by-word literal translation back to English",
  "breakdown": [
    {{
      "word": "each word/particle in {lang_name}",
      "pronunciation": "romanized pronunciation",
      "meaning": "English meaning",
      "difficulty": "easy|medium|hard",
      "note": "brief grammar/usage note if helpful, otherwise null"
    }}
  ],
  "grammar_notes": [
    "Key grammar pattern or structure explanation (1-3 short notes)"
  ],
  "cultural_note": "optional cultural context or usage tip, null if none",
  "formality": "casual|polite|formal — what register this translation uses",
  "alternative": "an alternative way to say this (different formality or phrasing), or null"
}}"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    
    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")
    
    data = resp.json()
    text = data["content"][0]["text"]
    
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            raise HTTPException(502, "Failed to parse LLM response")
    
    return result

@app.get("/api/languages")
async def get_languages():
    return SUPPORTED_LANGUAGES

app.mount("/", StaticFiles(directory="static", html=True), name="static")
