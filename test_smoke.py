"""E2E smoke test — hits the main user flow and checks responses."""
import os
import json
import pytest
import requests

BASE = os.getenv("SENTSEI_URL", "http://localhost:8847")
PW = os.getenv("SENTSEI_PASSWORD", "sentsei2026")
HEADERS = {"Content-Type": "application/json", "X-App-Password": PW}


def test_health():
    r = requests.get(f"{BASE}/api/health", headers=HEADERS)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["ollama"]["reachable"] is True


def test_languages():
    r = requests.get(f"{BASE}/api/languages")
    assert r.status_code == 200
    langs = r.json()
    assert "ja" in langs and "ko" in langs and "zh" in langs


def test_learn_basic():
    r = requests.post(f"{BASE}/api/learn", headers=HEADERS, json={
        "sentence": "I want to eat ramen",
        "target_language": "ja"
    })
    assert r.status_code == 200
    d = r.json()
    assert "translation" in d
    assert "breakdown" in d
    assert len(d["breakdown"]) > 0
    # Should have pronunciation
    assert any(w.get("pronunciation") for w in d["breakdown"])


def test_learn_stream():
    r = requests.post(f"{BASE}/api/learn-stream", headers=HEADERS, json={
        "sentence": "Hello world",
        "target_language": "ko"
    }, stream=True)
    assert r.status_code == 200
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    assert any(e["type"] == "result" for e in events)
    result_evt = next(e for e in events if e["type"] == "result")
    assert "translation" in result_evt["data"]


def test_surprise():
    r = requests.get(f"{BASE}/api/surprise", headers=HEADERS, params={
        "lang": "ja"
    })
    assert r.status_code == 200
    d = r.json()
    assert "sentence" in d or "translation" in d


def test_word_detail_stream():
    r = requests.post(f"{BASE}/api/word-detail-stream", headers=HEADERS, json={
        "word": "食べる",
        "meaning": "to eat",
        "target_language": "ja",
        "sentence_context": "ラーメンを食べたい"
    }, stream=True)
    assert r.status_code == 200
    events = []
    for line in r.iter_lines(decode_unicode=True):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    # Should have at least one progress + result
    assert any(e["type"] in ("progress", "heartbeat") for e in events)
    assert any(e["type"] == "result" for e in events)
    result_evt = next(e for e in events if e["type"] == "result")
    assert "examples" in result_evt["data"]


def test_export_anki():
    r = requests.post(f"{BASE}/api/export-anki", headers=HEADERS, json=[
        {"sentence": "hello", "translation": "こんにちは", "target": "ja"}
    ])
    assert r.status_code == 200


def test_rate_limit_header():
    """Ensure requests work and don't immediately 429."""
    for _ in range(3):
        r = requests.get(f"{BASE}/api/languages")
        assert r.status_code == 200
