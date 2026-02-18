"""Tests for dedicated SRS API routes."""
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import auth
from srs_routes import router as srs_router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sentsei-test.db"
    monkeypatch.setattr(auth, "DB_PATH", db_path)
    auth.init_user_db()

    app = FastAPI()
    app.include_router(srs_router)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client):
    conn = auth.get_db()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        ("alice", "test-hash", time.time()),
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    token = auth.create_session(user_id)
    return {"Authorization": f"Bearer {token}"}


def test_srs_endpoints_require_auth(client):
    sample_item = {
        "sentence": "こんにちは",
        "translation": "hello",
        "lang": "ja",
        "addedAt": 1000,
        "nextReview": 2000,
        "interval": 1000,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    sample_review = {
        "sentence": "こんにちは",
        "lang": "ja",
        "interval": 2000,
        "easeFactor": 2.6,
        "nextReview": 4000,
        "reviewCount": 1,
    }

    assert client.get("/api/srs/deck").status_code == 401
    assert client.put("/api/srs/deck", json=[]).status_code == 401
    assert client.post("/api/srs/item", json=sample_item).status_code == 401
    assert client.delete("/api/srs/item", params={"sentence": "こんにちは", "lang": "ja"}).status_code == 401
    assert client.post("/api/srs/review", json=sample_review).status_code == 401


def test_put_and_get_srs_deck(client, auth_headers):
    deck = [
        {
            "sentence": "你好",
            "translation": "hello",
            "lang": "zh",
            "addedAt": 100,
            "nextReview": 200,
            "interval": 100,
            "easeFactor": 2.5,
            "reviewCount": 0,
        }
    ]
    put_resp = client.put("/api/srs/deck", headers=auth_headers, json=deck)
    assert put_resp.status_code == 200
    assert put_resp.json()["ok"] is True

    get_resp = client.get("/api/srs/deck", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json() == deck


def test_add_and_get_roundtrip(client, auth_headers):
    item = {
        "sentence": "안녕하세요",
        "translation": "hello",
        "lang": "ko",
        "pronunciation": "annyeonghaseyo",
        "addedAt": 1000,
        "nextReview": 2000,
        "interval": 1000,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    add_resp = client.post("/api/srs/item", headers=auth_headers, json=item)
    assert add_resp.status_code == 200
    assert add_resp.json()["added"] is True

    deck_resp = client.get("/api/srs/deck", headers=auth_headers)
    assert deck_resp.status_code == 200
    deck = deck_resp.json()
    assert len(deck) == 1
    assert deck[0]["sentence"] == item["sentence"]
    assert deck[0]["lang"] == item["lang"]


def test_delete_srs_item(client, auth_headers):
    deck = [
        {
            "sentence": "一",
            "translation": "one",
            "lang": "zh",
            "addedAt": 1,
            "nextReview": 2,
            "interval": 1,
            "easeFactor": 2.5,
            "reviewCount": 0,
        },
        {
            "sentence": "二",
            "translation": "two",
            "lang": "zh",
            "addedAt": 3,
            "nextReview": 4,
            "interval": 1,
            "easeFactor": 2.5,
            "reviewCount": 0,
        },
    ]
    client.put("/api/srs/deck", headers=auth_headers, json=deck)

    del_resp = client.delete(
        "/api/srs/item",
        headers=auth_headers,
        params={"sentence": "一", "lang": "zh"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["removed"] is True

    deck_resp = client.get("/api/srs/deck", headers=auth_headers)
    assert deck_resp.status_code == 200
    result = deck_resp.json()
    assert len(result) == 1
    assert result[0]["sentence"] == "二"


def test_review_updates_srs_fields(client, auth_headers):
    base_item = {
        "sentence": "食べる",
        "translation": "to eat",
        "lang": "ja",
        "addedAt": 1000,
        "nextReview": 2000,
        "interval": 1000,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    client.put("/api/srs/deck", headers=auth_headers, json=[base_item])

    review_payload = {
        "sentence": "食べる",
        "lang": "ja",
        "interval": 3 * 86400000,
        "easeFactor": 2.6,
        "nextReview": 999999999,
        "reviewCount": 1,
    }
    review_resp = client.post("/api/srs/review", headers=auth_headers, json=review_payload)
    assert review_resp.status_code == 200
    assert review_resp.json()["ok"] is True

    deck_resp = client.get("/api/srs/deck", headers=auth_headers)
    assert deck_resp.status_code == 200
    updated = deck_resp.json()[0]
    assert updated["interval"] == review_payload["interval"]
    assert updated["easeFactor"] == review_payload["easeFactor"]
    assert updated["nextReview"] == review_payload["nextReview"]
    assert updated["reviewCount"] == review_payload["reviewCount"]
