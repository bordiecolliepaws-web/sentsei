"""Favorites/bookmarks API routes."""
import json
import time
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from auth import require_password, extract_bearer_token, get_user_from_token, get_db
from llm import sanitize_tsv_cell, anki_language_label

router = APIRouter()


class FavoriteEntry(BaseModel):
    sentence: str
    translation: str
    lang: str
    pronunciation: Optional[str] = ""
    ts: Optional[float] = None


@router.get("/api/favorites", tags=["Favorites"], summary="Get user favorites")
async def get_favorites(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")
    conn = get_db()
    row = conn.execute(
        "SELECT data_json FROM user_data WHERE user_id = ? AND data_key = 'favorites'",
        (user["id"],)
    ).fetchone()
    conn.close()
    if not row:
        return {"favorites": []}
    return {"favorites": json.loads(row["data_json"])}


@router.post("/api/favorites", tags=["Favorites"], summary="Add a favorite")
async def add_favorite(
    entry: FavoriteEntry,
    authorization: Optional[str] = Header(default=None),
    _pw=Depends(require_password),
):
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")

    fav = entry.dict()
    if not fav.get("ts"):
        fav["ts"] = time.time() * 1000  # ms like JS Date.now()

    conn = get_db()
    row = conn.execute(
        "SELECT data_json FROM user_data WHERE user_id = ? AND data_key = 'favorites'",
        (user["id"],)
    ).fetchone()
    favorites = json.loads(row["data_json"]) if row else []

    # Deduplicate by sentence+lang
    favorites = [f for f in favorites if not (f.get("sentence") == fav["sentence"] and f.get("lang") == fav["lang"])]
    favorites.insert(0, fav)

    conn.execute(
        "INSERT INTO user_data (user_id, data_key, data_json, updated_at) VALUES (?, 'favorites', ?, ?) "
        "ON CONFLICT(user_id, data_key) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at",
        (user["id"], json.dumps(favorites, ensure_ascii=False), time.time())
    )
    conn.commit()
    conn.close()
    return {"ok": True, "count": len(favorites)}


@router.delete("/api/favorites", tags=["Favorites"], summary="Remove a favorite by sentence+lang")
async def remove_favorite(
    sentence: str,
    lang: str,
    authorization: Optional[str] = Header(default=None),
    _pw=Depends(require_password),
):
    token = extract_bearer_token(authorization)
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(401, "Not logged in")

    conn = get_db()
    row = conn.execute(
        "SELECT data_json FROM user_data WHERE user_id = ? AND data_key = 'favorites'",
        (user["id"],)
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": True, "count": 0}

    favorites = json.loads(row["data_json"])
    favorites = [f for f in favorites if not (f.get("sentence") == sentence and f.get("lang") == lang)]

    conn.execute(
        "INSERT INTO user_data (user_id, data_key, data_json, updated_at) VALUES (?, 'favorites', ?, ?) "
        "ON CONFLICT(user_id, data_key) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at",
        (user["id"], json.dumps(favorites, ensure_ascii=False), time.time())
    )
    conn.commit()
    conn.close()
    return {"ok": True, "count": len(favorites)}


@router.post("/api/export-favorites", tags=["Favorites", "Export"], summary="Export favorites as Anki TSV")
async def export_favorites(
    entries: List[FavoriteEntry],
    _pw=Depends(require_password),
):
    rows = []
    for entry in entries:
        front = sanitize_tsv_cell(entry.sentence)
        if not front:
            continue
        translation = sanitize_tsv_cell(entry.translation)
        pronunciation = sanitize_tsv_cell(entry.pronunciation or "")
        lang_code = (entry.lang or "").strip()
        back_parts = []
        if translation:
            back_parts.append(translation)
        if pronunciation:
            back_parts.append(f"Pronunciation: {pronunciation}")
        if lang_code:
            back_parts.append(f"Language: {anki_language_label(lang_code)}")
        back = sanitize_tsv_cell("<br>".join(back_parts))
        rows.append(f"{front}\t{back}")

    content = "\n".join(rows)
    headers = {"Content-Disposition": 'attachment; filename="sentsei-favorites.txt"'}
    return Response(content=content, media_type="text/tab-separated-values", headers=headers)
