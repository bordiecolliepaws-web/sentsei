"""LLM interaction (Ollama), prompt building, pronunciation, and post-processing."""
import os
import json
import re as _re
import hashlib
import random
import time
from typing import Optional, List
from pathlib import Path

import httpx
import pykakasi
from pypinyin import pinyin, Style as PinyinStyle
from korean_romanizer.romanizer import Romanizer
from opencc import OpenCC

from models import SUPPORTED_LANGUAGES

# --- Config ---
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b-instruct-q3_K_M"
TAIDE_MODEL = "jcai/llama3-taide-lx-8b-chat-alpha1:Q4_K_M"

# --- Pronunciation ---
_kakasi = pykakasi.kakasi()
_s2twp = OpenCC('s2twp')


def deterministic_pronunciation(text: str, lang_code: str) -> Optional[str]:
    if lang_code == "ja":
        result = _kakasi.convert(text)
        return " ".join(item["hepburn"] for item in result if item["hepburn"].strip())
    elif lang_code == "zh":
        result = pinyin(text, style=PinyinStyle.TONE)
        return " ".join(p[0] for p in result)
    elif lang_code == "ko":
        r = Romanizer(text)
        return r.romanize()
    return None


def deterministic_word_pronunciation(word: str, lang_code: str) -> Optional[str]:
    return deterministic_pronunciation(word, lang_code)


def ensure_traditional_chinese(obj):
    if isinstance(obj, str):
        return _s2twp.convert(obj)
    elif isinstance(obj, list):
        return [ensure_traditional_chinese(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: ensure_traditional_chinese(v) for k, v in obj.items()}
    return obj


def detect_sentence_difficulty(sentence: str, breakdown: list = None) -> dict:
    factors = []
    score = 0
    text = sentence.strip()
    cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' or '\uac00' <= c <= '\ud7af')
    is_cjk = cjk_chars / max(len(text.replace(" ", "")), 1) > 0.3

    if is_cjk:
        meaningful = sum(1 for c in text if c.strip() and c not in '，。！？、「」『』（）…—·')
        if meaningful <= 5:
            score += 5; factors.append("Very short phrase")
        elif meaningful <= 12:
            score += 20; factors.append(f"Medium length ({meaningful} characters)")
        elif meaningful <= 25:
            score += 45; factors.append(f"Long sentence ({meaningful} characters)")
        else:
            score += 65; factors.append(f"Very long sentence ({meaningful} characters)")
        unique_chars = len(set(c for c in text if '\u4e00' <= c <= '\u9fff'))
        if unique_chars > 15:
            score += 15; factors.append(f"High character diversity ({unique_chars} unique)")
        elif unique_chars > 8:
            score += 8
    else:
        words = text.split()
        word_count = len(words)
        if word_count <= 4:
            score += 5; factors.append("Short phrase")
        elif word_count <= 10:
            score += 20; factors.append(f"Medium sentence ({word_count} words)")
        elif word_count <= 20:
            score += 40; factors.append(f"Long sentence ({word_count} words)")
        else:
            score += 60; factors.append(f"Very long sentence ({word_count} words)")
        avg_len = sum(len(w.strip('.,!?;:')) for w in words) / max(word_count, 1)
        if avg_len > 7:
            score += 15; factors.append("Complex vocabulary (long words)")
        elif avg_len > 5:
            score += 8
        complexity_markers = ['although', 'however', 'nevertheless', 'whereas', 'furthermore',
                            'consequently', 'notwithstanding', 'if', 'because', 'since', 'while',
                            'unless', 'whether', 'whom', 'whose', 'whereby']
        found = [m for m in complexity_markers if m in text.lower()]
        if found:
            score += min(len(found) * 8, 20)
            factors.append(f"Complex grammar ({', '.join(found[:3])})")

    if breakdown:
        hard_count = sum(1 for w in breakdown if w.get("difficulty") == "hard")
        medium_count = sum(1 for w in breakdown if w.get("difficulty") == "medium")
        total = len(breakdown)
        if total > 0:
            hard_ratio = hard_count / total
            if hard_ratio > 0.3:
                score += 20; factors.append(f"{hard_count}/{total} words marked hard")
            elif hard_ratio > 0.1:
                score += 10
            if medium_count / total > 0.5:
                score += 5

    score = min(score, 100)
    if score <= 25: level = "beginner"
    elif score <= 55: level = "intermediate"
    else: level = "advanced"
    return {"level": level, "score": score, "factors": factors}


# --- CC-CEDICT Dictionary ---
_cedict_data = {}
_cedict_path = Path(__file__).parent / "cedict_dict.json"
if _cedict_path.exists():
    _cedict_data = json.loads(_cedict_path.read_text())

_jieba_dict_path = Path(__file__).parent / "jieba_tw_dict.txt"
if _jieba_dict_path.exists():
    import jieba as _jieba_init
    with open(_jieba_dict_path) as _f:
        for _line in _f:
            _w = _line.strip()
            if _w:
                _jieba_init.add_word(_w)

_particle_overrides = {
    "的": "(possessive/descriptive particle)", "了": "(completion/change particle)",
    "是": "is; am; are", "在": "at; in; (progressive particle)", "把": "(object-marking particle)",
    "被": "(passive particle)", "得": "(complement particle)", "地": "(adverbial particle)",
    "著": "(continuous aspect particle)", "過": "(experiential particle)",
    "會": "will; can", "能": "can; able to", "要": "want; need; will",
}


def cedict_lookup(word: str) -> Optional[str]:
    if word in _particle_overrides:
        return _particle_overrides[word]
    return _cedict_data.get(word)


# --- Helpers ---

def parse_json_object(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _re.search(r'\{.*\}', text, _re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None


def split_sentences(text: str) -> List[str]:
    parts = _re.split(r'(?<=[.!?。！？])\s*', text.strip())
    return [s.strip() for s in parts if s.strip()]


def new_quiz_id(lang: str, sentence: str) -> str:
    raw = f"{lang}|{sentence}|{time.time_ns()}|{random.random()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def translation_hint(text: str) -> str:
    cleaned = (text or "").strip().strip("\"'""''")
    if not cleaned:
        return ""
    first = _re.split(r"\s+", cleaned)[0]
    first = _re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", first)
    if not first:
        first = cleaned[:2]
    if any('\u4e00' <= c <= '\u9fff' for c in first) and len(first) > 2:
        first = first[:2]
    return first


def sanitize_tsv_cell(value: Optional[str]) -> str:
    text = (value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ").replace("\n", " ")
    return text.strip()


def anki_language_label(code: str) -> str:
    name = SUPPORTED_LANGUAGES.get(code, code)
    return f"{name} ({code})" if name != code else code


async def ollama_chat(messages: list, model: str = None, temperature: float = 0.3,
                      num_predict: int = 2048, timeout: int = 120) -> str:
    """Call Ollama chat API and return the content string."""
    if model is None:
        model = OLLAMA_MODEL
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": num_predict},
            },
        )
    if resp.status_code != 200:
        return None
    return resp.json().get("message", {}).get("content", "")


async def check_ollama_connectivity() -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception as e:
        print(f"[startup] Ollama not reachable: {e}")
        return False
