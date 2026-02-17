"""Surprise bank logic — pre-computation, save/load, endpoints."""
import json
import random
import asyncio
from typing import Optional
from pathlib import Path
from collections import defaultdict

from log import get_logger

logger = get_logger("sentsei.surprise")

from fastapi import APIRouter, HTTPException
import httpx

from models import SUPPORTED_LANGUAGES, SURPRISE_SENTENCES_EN, SURPRISE_SENTENCES_ZH
from auth import APP_PASSWORD

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


def increment_user_request():
    global _user_request_count
    _user_request_count += 1
    _get_user_event().clear()


def decrement_user_request():
    global _user_request_count
    _user_request_count -= 1
    if _user_request_count <= 0:
        _user_request_count = 0
        _get_user_event().set()


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


# --- Background Tasks ---

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
