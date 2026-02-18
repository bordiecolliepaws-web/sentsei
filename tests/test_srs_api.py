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


# --- Edge case tests ---


def test_review_nonexistent_item_returns_404(client, auth_headers):
    """Reviewing an item not in the deck should return 404."""
    review_payload = {
        "sentence": "ghost",
        "lang": "en",
        "interval": 1000,
        "easeFactor": 2.5,
        "nextReview": 9999,
        "reviewCount": 1,
    }
    resp = client.post("/api/srs/review", headers=auth_headers, json=review_payload)
    assert resp.status_code == 404


def test_delete_nonexistent_item(client, auth_headers):
    """Deleting a missing item should succeed but report removed=False."""
    resp = client.delete(
        "/api/srs/item",
        headers=auth_headers,
        params={"sentence": "nope", "lang": "xx"},
    )
    assert resp.status_code == 200
    assert resp.json()["removed"] is False


def test_add_duplicate_item_updates(client, auth_headers):
    """Adding an item with same sentence+lang should update, not duplicate."""
    item_v1 = {
        "sentence": "猫",
        "translation": "cat",
        "lang": "ja",
        "addedAt": 100,
        "nextReview": 200,
        "interval": 100,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    resp1 = client.post("/api/srs/item", headers=auth_headers, json=item_v1)
    assert resp1.json()["added"] is True

    item_v2 = {**item_v1, "translation": "kitty", "easeFactor": 2.8}
    resp2 = client.post("/api/srs/item", headers=auth_headers, json=item_v2)
    assert resp2.json()["added"] is False  # updated, not added

    deck = client.get("/api/srs/deck", headers=auth_headers).json()
    assert len(deck) == 1
    assert deck[0]["translation"] == "kitty"
    assert deck[0]["easeFactor"] == 2.8


def test_review_ef_boundary_low(client, auth_headers):
    """EF can go below 1.3 (the backend stores whatever the client sends)."""
    item = {
        "sentence": "test",
        "translation": "test",
        "lang": "en",
        "addedAt": 1,
        "nextReview": 2,
        "interval": 1,
        "easeFactor": 1.3,
        "reviewCount": 0,
    }
    client.put("/api/srs/deck", headers=auth_headers, json=[item])
    review = {
        "sentence": "test",
        "lang": "en",
        "interval": 500,
        "easeFactor": 0.5,
        "nextReview": 1000,
        "reviewCount": 1,
    }
    resp = client.post("/api/srs/review", headers=auth_headers, json=review)
    assert resp.status_code == 200
    deck = client.get("/api/srs/deck", headers=auth_headers).json()
    assert deck[0]["easeFactor"] == 0.5


def test_review_ef_boundary_high(client, auth_headers):
    """High EF values should be stored correctly."""
    item = {
        "sentence": "easy",
        "translation": "easy",
        "lang": "en",
        "addedAt": 1,
        "nextReview": 2,
        "interval": 1,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    client.put("/api/srs/deck", headers=auth_headers, json=[item])
    review = {
        "sentence": "easy",
        "lang": "en",
        "interval": 86400000,
        "easeFactor": 5.0,
        "nextReview": 99999999,
        "reviewCount": 10,
    }
    resp = client.post("/api/srs/review", headers=auth_headers, json=review)
    assert resp.status_code == 200
    deck = client.get("/api/srs/deck", headers=auth_headers).json()
    assert deck[0]["easeFactor"] == 5.0
    assert deck[0]["reviewCount"] == 10


def test_add_item_missing_optional_fields(client, auth_headers):
    """Adding an item with only required fields should work."""
    item = {"sentence": "minimal", "lang": "en"}
    resp = client.post("/api/srs/item", headers=auth_headers, json=item)
    assert resp.status_code == 200
    deck = client.get("/api/srs/deck", headers=auth_headers).json()
    assert len(deck) == 1
    assert deck[0]["sentence"] == "minimal"


def test_add_item_missing_required_fields(client, auth_headers):
    """Missing required fields (sentence, lang) should fail validation."""
    resp = client.post("/api/srs/item", headers=auth_headers, json={"translation": "hi"})
    assert resp.status_code == 422  # Pydantic validation error


def test_review_missing_required_fields(client, auth_headers):
    """Review payload missing required fields should fail."""
    resp = client.post("/api/srs/review", headers=auth_headers, json={"sentence": "x"})
    assert resp.status_code == 422


def test_put_empty_deck(client, auth_headers):
    """Replacing deck with empty list should clear it."""
    item = {
        "sentence": "temp",
        "translation": "temp",
        "lang": "en",
        "addedAt": 1,
        "nextReview": 2,
        "interval": 1,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    client.put("/api/srs/deck", headers=auth_headers, json=[item])
    assert len(client.get("/api/srs/deck", headers=auth_headers).json()) == 1

    resp = client.put("/api/srs/deck", headers=auth_headers, json=[])
    assert resp.status_code == 200
    assert resp.json()["count"] == 0
    assert client.get("/api/srs/deck", headers=auth_headers).json() == []


def test_get_deck_empty_by_default(client, auth_headers):
    """New user should have an empty deck."""
    deck = client.get("/api/srs/deck", headers=auth_headers).json()
    assert deck == []


def test_same_sentence_different_lang(client, auth_headers):
    """Same sentence in different languages should be separate items."""
    item_ja = {
        "sentence": "hello",
        "translation": "こんにちは",
        "lang": "ja",
        "addedAt": 1,
        "nextReview": 2,
        "interval": 1,
        "easeFactor": 2.5,
        "reviewCount": 0,
    }
    item_ko = {**item_ja, "translation": "안녕하세요", "lang": "ko"}
    client.post("/api/srs/item", headers=auth_headers, json=item_ja)
    client.post("/api/srs/item", headers=auth_headers, json=item_ko)
    deck = client.get("/api/srs/deck", headers=auth_headers).json()
    assert len(deck) == 2
