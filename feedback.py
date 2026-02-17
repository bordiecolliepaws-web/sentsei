"""Feedback endpoints."""
import json
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Header

from models import FeedbackRequest
from auth import APP_PASSWORD

router = APIRouter()

FEEDBACK_FILE = Path(__file__).parent / "feedback.jsonl"


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
