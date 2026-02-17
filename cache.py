"""LRU translation cache, grammar pattern library, and quiz answer storage."""
import json
import time
import hashlib
import re as _re
from typing import Optional
from pathlib import Path
from collections import OrderedDict

from log import get_logger

logger = get_logger("sentsei.cache")

# --- Translation Cache ---
CACHE_MAX = 500
CACHE_TTL = 3600 * 24  # 24h
CACHE_FILE = Path(__file__).parent / "translation_cache.json"
CACHE_SAVE_INTERVAL = 60

_translation_cache: OrderedDict = OrderedDict()
_cache_dirty = False
_cache_last_save = 0.0


def cache_key(sentence: str, target: str, gender: str, formality: str) -> str:
    raw = f"{sentence.strip().lower()}|{target}|{gender}|{formality}"
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_get(key: str):
    entry = _translation_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > CACHE_TTL:
        _translation_cache.pop(key, None)
        return None
    _translation_cache.move_to_end(key)
    return result


def cache_put(key: str, result: dict):
    global _cache_dirty
    _translation_cache[key] = (time.time(), result)
    if len(_translation_cache) > CACHE_MAX:
        _translation_cache.popitem(last=False)
    _cache_dirty = True
    _maybe_save_cache()


def load_cache():
    global _cache_last_save
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            now = time.time()
            loaded = 0
            for key, (ts, result) in data.items():
                if now - ts < CACHE_TTL:
                    _translation_cache[key] = (ts, result)
                    loaded += 1
                if loaded >= CACHE_MAX:
                    break
            logger.info("Loaded cache from disk", extra={"component": "cache", "count": loaded})
        except Exception:
            logger.exception("Failed to load cache file", extra={"component": "cache"})
    _cache_last_save = time.time()


def save_cache():
    global _cache_dirty, _cache_last_save
    try:
        CACHE_FILE.write_text(json.dumps(dict(_translation_cache), ensure_ascii=False))
        _cache_dirty = False
        _cache_last_save = time.time()
    except Exception:
        logger.exception("Failed to save cache", extra={"component": "cache"})


def _maybe_save_cache():
    if _cache_dirty and (time.time() - _cache_last_save) >= CACHE_SAVE_INTERVAL:
        save_cache()


# --- Word Detail Cache ---
WORD_CACHE_MAX = 300
WORD_CACHE_TTL = 3600 * 72  # 72h — word details change less often
WORD_CACHE_FILE = Path(__file__).parent / "word_detail_cache.json"

_word_cache: OrderedDict = OrderedDict()
_word_cache_dirty = False
_word_cache_last_save = 0.0


def word_cache_key(word: str, target: str, meaning: str = "") -> str:
    raw = f"{word.strip().lower()}|{target}|{meaning.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def word_cache_get(key: str):
    entry = _word_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > WORD_CACHE_TTL:
        _word_cache.pop(key, None)
        return None
    _word_cache.move_to_end(key)
    return result


def word_cache_put(key: str, result: dict):
    global _word_cache_dirty
    _word_cache[key] = (time.time(), result)
    if len(_word_cache) > WORD_CACHE_MAX:
        _word_cache.popitem(last=False)
    _word_cache_dirty = True
    _maybe_save_word_cache()


def load_word_cache():
    global _word_cache_last_save
    if WORD_CACHE_FILE.exists():
        try:
            data = json.loads(WORD_CACHE_FILE.read_text())
            now = time.time()
            loaded = 0
            for key, (ts, result) in data.items():
                if now - ts < WORD_CACHE_TTL:
                    _word_cache[key] = (ts, result)
                    loaded += 1
                if loaded >= WORD_CACHE_MAX:
                    break
            logger.info("Loaded word cache from disk", extra={"component": "cache", "count": loaded})
        except Exception:
            logger.exception("Failed to load word cache file", extra={"component": "cache"})
    _word_cache_last_save = time.time()


def save_word_cache():
    global _word_cache_dirty, _word_cache_last_save
    try:
        WORD_CACHE_FILE.write_text(json.dumps(dict(_word_cache), ensure_ascii=False))
        _word_cache_dirty = False
        _word_cache_last_save = time.time()
    except Exception:
        logger.exception("Failed to save word cache", extra={"component": "cache"})


def _maybe_save_word_cache():
    if _word_cache_dirty and (time.time() - _word_cache_last_save) >= CACHE_SAVE_INTERVAL:
        save_word_cache()


def word_cache_stats() -> dict:
    return {"entries": len(_word_cache), "max": WORD_CACHE_MAX, "ttl_hours": WORD_CACHE_TTL / 3600}


def is_cache_dirty():
    return _cache_dirty


# --- Grammar Pattern Library ---
GRAMMAR_PATTERNS_FILE = Path(__file__).parent / "grammar_patterns.json"
_grammar_patterns: dict = {}
_grammar_dirty = False


def _gp_id(name: str, lang: str) -> str:
    raw = f"{name.strip()}|{lang}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_grammar_patterns():
    global _grammar_patterns
    if GRAMMAR_PATTERNS_FILE.exists():
        try:
            _grammar_patterns = json.loads(GRAMMAR_PATTERNS_FILE.read_text())
        except Exception:
            logger.exception("Failed to load grammar patterns", extra={"component": "grammar"})
            _grammar_patterns = {}


def save_grammar_patterns():
    global _grammar_dirty
    try:
        GRAMMAR_PATTERNS_FILE.write_text(json.dumps(_grammar_patterns, ensure_ascii=False, indent=2))
        _grammar_dirty = False
    except Exception:
        logger.exception("Failed to save grammar patterns", extra={"component": "grammar"})


def is_grammar_dirty():
    return _grammar_dirty


def get_grammar_patterns():
    return _grammar_patterns


def extract_and_store_grammar_patterns(result: dict, lang_code: str, source_sentence: str):
    global _grammar_dirty
    grammar_notes = result.get("grammar_notes", []) or []
    if not grammar_notes:
        return

    translation = result.get("translation", "")
    pattern_re = _re.compile(
        r'[〜~～][\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uac00-\ud7af()（）/\+\-…]+|'
        r'[\u3040-\u309f\u30a0-\u30ff]{2,}[\u3040-\u309f\u30a0-\u30ff/（）()]*|'
        r'[\uac00-\ud7af]{2,}[/\uac00-\ud7af()（）]*'
    )

    for note in grammar_notes:
        matches = pattern_re.findall(note)
        if not matches:
            if len(note) > 10:
                name = note[:50].strip().rstrip('.')
                matches = [name]
            else:
                continue

        for pattern_name in matches[:2]:
            pattern_name = pattern_name.strip()
            if len(pattern_name) < 2:
                continue
            pid = _gp_id(pattern_name, lang_code)
            if pid not in _grammar_patterns:
                _grammar_patterns[pid] = {
                    "id": pid,
                    "name": pattern_name,
                    "lang": lang_code,
                    "explanation": note,
                    "examples": [],
                    "count": 0,
                }

            entry = _grammar_patterns[pid]
            if len(note) > len(entry.get("explanation", "")):
                entry["explanation"] = note
            entry["count"] += 1

            existing_sources = {ex.get("source", "") for ex in entry["examples"]}
            if source_sentence not in existing_sources:
                entry["examples"].append({
                    "source": source_sentence,
                    "translation": translation,
                    "timestamp": time.time(),
                })
                if len(entry["examples"]) > 20:
                    entry["examples"] = entry["examples"][-20:]

            _grammar_dirty = True

    if _grammar_dirty:
        save_grammar_patterns()


# --- Quiz Answers ---
QUIZ_ANSWER_TTL = 3600
_quiz_answers: dict = {}


def get_quiz_answers():
    return _quiz_answers


def cleanup_quiz_answers():
    cutoff = time.time() - QUIZ_ANSWER_TTL
    stale_ids = [qid for qid, payload in _quiz_answers.items() if payload.get("created_at", 0) < cutoff]
    for qid in stale_ids:
        _quiz_answers.pop(qid, None)
