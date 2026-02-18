"""Dedicated SRS API routes backed by user_data.srs_deck."""
import json
import time
from typing import Optional, Any, Dict, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from auth import extract_bearer_token, get_user_from_token, get_db

router = APIRouter()


class SRSItemPayload(BaseModel):
    sentence: str
    translation: str = ""
    lang: str
    pronunciation: str = ""
    addedAt: Optional[float] = None
    nextReview: Optional[float] = None
    interval: Optional[float] = None
    easeFactor: Optional[float] = None
    reviewCount: Optional[int] = None


class SRSReviewPayload(BaseModel):
    sentence: str
    lang: str
    interval: float
    easeFactor: float
    nextReview: float
    reviewCount: int


def _require_user(authorization: Optional[str]) -> Dict[str, Any]:
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")
    return user


def _load_srs_deck(conn, user_id: int) -> List[Dict[str, Any]]:
    row = conn.execute(
        "SELECT data_json FROM user_data WHERE user_id = ? AND data_key = 'srs_deck'",
        (user_id,),
    ).fetchone()
    if not row:
        return []
    try:
        parsed = json.loads(row["data_json"])
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _save_srs_deck(conn, user_id: int, deck: List[Dict[str, Any]]) -> None:
    data_json = json.dumps(deck, ensure_ascii=False)
    if len(data_json) > 1_000_000:
        raise HTTPException(400, "Data too large (max 1MB)")
    conn.execute(
        "INSERT INTO user_data (user_id, data_key, data_json, updated_at) VALUES (?, 'srs_deck', ?, ?) "
        "ON CONFLICT(user_id, data_key) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at",
        (user_id, data_json, time.time()),
    )


@router.get("/api/srs/deck", tags=["SRS"], summary="Get full SRS deck for current user")
async def get_srs_deck(authorization: Optional[str] = Header(default=None)):
    user = _require_user(authorization)
    conn = get_db()
    try:
        return _load_srs_deck(conn, user["id"])
    finally:
        conn.close()


@router.put("/api/srs/deck", tags=["SRS"], summary="Replace full SRS deck for current user")
async def put_srs_deck(deck: List[Dict[str, Any]], authorization: Optional[str] = Header(default=None)):
    if not all(isinstance(item, dict) for item in deck):
        raise HTTPException(400, "Deck must be an array of objects")
    user = _require_user(authorization)
    conn = get_db()
    try:
        _save_srs_deck(conn, user["id"], deck)
        conn.commit()
        return {"ok": True, "count": len(deck)}
    finally:
        conn.close()


@router.post("/api/srs/item", tags=["SRS"], summary="Add one item to the SRS deck")
async def add_srs_item(item: SRSItemPayload, authorization: Optional[str] = Header(default=None)):
    user = _require_user(authorization)
    item_data = item.dict(exclude_none=True)
    conn = get_db()
    try:
        deck = _load_srs_deck(conn, user["id"])
        item_key = (item_data.get("sentence"), item_data.get("lang"))
        updated = False
        for idx, existing in enumerate(deck):
            if (existing.get("sentence"), existing.get("lang")) == item_key:
                deck[idx] = {**existing, **item_data}
                updated = True
                break
        if not updated:
            deck.append(item_data)
        _save_srs_deck(conn, user["id"], deck)
        conn.commit()
        return {"ok": True, "added": not updated, "count": len(deck)}
    finally:
        conn.close()


@router.delete("/api/srs/item", tags=["SRS"], summary="Remove one SRS item by sentence+lang")
async def remove_srs_item(
    sentence: str,
    lang: str,
    authorization: Optional[str] = Header(default=None),
):
    user = _require_user(authorization)
    conn = get_db()
    try:
        deck = _load_srs_deck(conn, user["id"])
        filtered = [item for item in deck if not (item.get("sentence") == sentence and item.get("lang") == lang)]
        _save_srs_deck(conn, user["id"], filtered)
        conn.commit()
        return {"ok": True, "removed": len(filtered) != len(deck), "count": len(filtered)}
    finally:
        conn.close()


@router.post("/api/srs/review", tags=["SRS"], summary="Persist updated review fields for one item")
async def review_srs_item(req: SRSReviewPayload, authorization: Optional[str] = Header(default=None)):
    user = _require_user(authorization)
    conn = get_db()
    try:
        deck = _load_srs_deck(conn, user["id"])
        target = next((item for item in deck if item.get("sentence") == req.sentence and item.get("lang") == req.lang), None)
        if not target:
            raise HTTPException(404, "SRS item not found")

        target["interval"] = req.interval
        target["easeFactor"] = req.easeFactor
        target["nextReview"] = req.nextReview
        target["reviewCount"] = req.reviewCount

        _save_srs_deck(conn, user["id"], deck)
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
