"""Feedback endpoints."""
import json
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header

from models import FeedbackRequest
from auth import APP_PASSWORD, require_password
from cache import mark_translation_bad

router = APIRouter()

FEEDBACK_FILE = Path(__file__).parent / "feedback.jsonl"


@router.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest, _pw=Depends(require_password)):
    if not req.message or not req.message.strip():
        raise HTTPException(400, "Feedback cannot be empty")
    if len(req.message) > 1000:
        raise HTTPException(400, "Feedback too long")

    msg = req.message.strip()
    msg_lower = msg.lower()

    # Heuristic: treat feedback as a "thumbs down" / low-quality flag when
    # the message clearly indicates the translation was wrong or unnatural.
    negative_markers = [
        "👎",
        "thumbs down",
        "translation is wrong",
        "translation was wrong",
        "wrong translation",
        "bad translation",
        "not natural",
        "unnatural",
        "sounds weird",
        "does not sound right",
    ]
    is_negative = any(tok in msg_lower for tok in negative_markers)

    # If user provided full context with negative feedback, mark the
    # corresponding cache entry as low quality so it won't be reused.
    if is_negative and req.sentence and req.translation and req.target_language:
        try:
            mark_translation_bad(req.sentence, req.translation, req.target_language)
        except Exception:
            # Feedback should never fail because cache invalidation did
            pass

    import datetime
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "message": msg,
        "sentence": req.sentence,
        "translation": req.translation,
        "target_language": req.target_language,
        "quality": "negative" if is_negative else "neutral",
    }
    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True}


@router.get("/api/feedback-list")
async def list_feedback(_pw=Depends(require_password), limit: int = 50, offset: int = 0):
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
async def delete_feedback(index: int, _pw=Depends(require_password)):
    if not FEEDBACK_FILE.exists():
        raise HTTPException(404, "No feedback file")
    lines = [l for l in FEEDBACK_FILE.read_text().strip().splitlines() if l.strip()]
    file_index = len(lines) - 1 - index
    if file_index < 0 or file_index >= len(lines):
        raise HTTPException(404, "Index out of range")
    lines.pop(file_index)
    FEEDBACK_FILE.write_text("\n".join(lines) + "\n" if lines else "")
    return {"ok": True}
