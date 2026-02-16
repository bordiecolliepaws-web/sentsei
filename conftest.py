"""Shared fixtures for Sentsei test suite."""
import atexit
import os
import pytest

LOCKFILE = "/tmp/sentsei-test.lock"

@pytest.fixture(scope="session", autouse=True)
def test_lock():
    """Prevent watchdog from restarting server during tests."""
    open(LOCKFILE, 'w').close()
    yield
    if os.path.exists(LOCKFILE):
        os.unlink(LOCKFILE)

@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("SENTSEI_URL", "http://localhost:8847")

@pytest.fixture(scope="session")
def password():
    return os.environ.get("SENTSEI_PASSWORD", "sentsei2026")

@pytest.fixture(scope="session")
def headers(password):
    return {"Content-Type": "application/json", "X-App-Password": password}

@pytest.fixture(scope="session")
def api_learn(base_url, headers):
    """Helper to call /api/learn."""
    import requests
    def _learn(sentence, target, input_lang="auto"):
        r = requests.post(f"{base_url}/api/learn", headers=headers, json={
            "sentence": sentence, "target_language": target, "input_language": input_lang
        }, timeout=120)
        return r.json() if r.ok else None
    return _learn
