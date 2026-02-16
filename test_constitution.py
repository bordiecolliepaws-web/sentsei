"""Sentsei Constitution Test Suite
Tests every rule in CONSTITUTION.md against the live app.
Run: python3 -m pytest test_constitution.py -v --timeout=120
"""
import re
import subprocess
import time
import pytest
import requests


# ── JS Syntax ──────────────────────────────────────────────

def test_js_syntax():
    js_check = subprocess.run(
        ['node', '-e', '''
const fs = require('fs');
let code;
try { code = fs.readFileSync('static/app.js', 'utf8'); } catch(e) {
  const html = fs.readFileSync('static/index.html', 'utf8');
  const match = html.match(/<script>([\\s\\S]*?)<\\/script>/);
  code = match ? match[1] : null;
}
if (code) { try { new Function(code); console.log('OK'); } catch(e) { console.log('ERROR:' + e.message); } }
else { console.log('NO_JS'); }
'''],
        capture_output=True, text=True, cwd='/home/opclaw/.openclaw/workspace-sora/sentsei'
    )
    assert js_check.stdout.strip() == 'OK', f"JS syntax error: {js_check.stdout.strip()}"


# ── Server Health ──────────────────────────────────────────

def test_server_up(base_url):
    r = requests.get(f"{base_url}/api/languages", timeout=5)
    assert r.ok

def test_all_languages_available(base_url):
    r = requests.get(f"{base_url}/api/languages", timeout=5)
    assert r.ok
    assert len(r.json()) == 8, f"Got {len(r.json())} languages"


# ── Rule 1: Traditional Chinese Only ──────────────────────

SIMPLIFIED_CHARS = set("这个说问请对会认语让给听时书车东发电长门见马鱼鸟点机关开进过还运动华国图区号头买卖写读话词记讲计议设试谁准难双欢观视显单习练经验继续热爱岁梦样飞")

def test_no_simplified_in_translation(api_learn):
    d = api_learn("This coffee tastes amazing", "zh", "en")
    assert d, "API call failed"
    trans = d.get("translation", "")
    found = [c for c in trans if c in SIMPLIFIED_CHARS]
    assert len(found) == 0, f"Found simplified: {''.join(found)}"

def test_no_simplified_in_breakdown(api_learn):
    d = api_learn("This coffee tastes amazing", "zh", "en")
    assert d, "API call failed"
    for w in d.get("breakdown", []):
        found = [c for c in w.get("word", "") if c in SIMPLIFIED_CHARS]
        assert len(found) == 0, f"Simplified in word '{w.get('word')}': {''.join(found)}"


# ── Rule 2: Explanations in Input Language ────────────────

def test_grammar_notes_in_english_for_english_input(api_learn):
    d = api_learn("This coffee tastes amazing", "zh", "en")
    assert d, "API call failed"
    for note in d.get("grammar_notes", []):
        chinese_chars = sum(1 for c in note if '\u4e00' <= c <= '\u9fff')
        ratio = chinese_chars / max(len(note), 1)
        assert ratio <= 0.5, f"Mostly Chinese grammar note: {note[:80]}"

def test_word_meanings_in_english_for_english_input(api_learn):
    d = api_learn("This coffee tastes amazing", "zh", "en")
    assert d, "API call failed"
    meanings = [w.get("meaning", "") for w in d.get("breakdown", [])]
    for m in meanings:
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in m)
        assert not has_chinese, f"Chinese in meaning: {m}"


# ── Rule 5: Pronunciation ────────────────────────────────

def test_japanese_romaji_not_garbage(api_learn):
    d = api_learn("Please teach me", "ja", "en")
    assert d, "API call failed"
    pron = d.get("pronunciation", "")
    assert not any(w.isupper() and len(w) > 3 for w in pron.split()), f"Bad pronunciation: {pron}"


# ── Rule 8: Layout Order ─────────────────────────────────

def test_source_before_translation_in_html(base_url):
    html = requests.get(f"{base_url}/").text
    app_js_r = requests.get(f"{base_url}/app.js")
    app_js = app_js_r.text if app_js_r.ok else ""
    all_content = html + app_js
    source_pos = all_content.find('result-source')
    trans_pos = all_content.find('result-translation')
    assert source_pos > 0 and source_pos < trans_pos, f"source@{source_pos} trans@{trans_pos}"


# ── Rule 10: Favicon ──────────────────────────────────────

def test_favicon_traditional(base_url):
    html = requests.get(f"{base_url}/").text
    assert '學' in html or '%E5%AD%B8' in html, "Favicon should use 學 (traditional)"


# ── Rule 11: IME Composition Guard ────────────────────────

def test_ime_composition_guard(base_url):
    html = requests.get(f"{base_url}/").text
    app_js_r = requests.get(f"{base_url}/app.js")
    app_js = app_js_r.text if app_js_r.ok else ""
    all_content = html + app_js
    assert 'compositionstart' in all_content
    assert 'compositionend' in all_content
    assert 'isComposing' in all_content


# ── Rule 13: Native Expression ────────────────────────────

def test_native_expression_differs(api_learn):
    d = api_learn("I want to order a coffee", "zh", "en")
    assert d, "API call failed"
    native = d.get("native_expression")
    trans = d.get("translation", "")
    if native:
        native_sentence = native.split("|")[0].strip() if "|" in native else native.split("(")[0].strip()
        assert native_sentence.rstrip("。") != trans.rstrip("。"), f"Both same: {trans}"

def test_native_expression_has_pronunciation(api_learn):
    d = api_learn("I want to order a coffee", "zh", "en")
    assert d, "API call failed"
    native = d.get("native_expression")
    if native:
        assert "|" in native or "(" in native, f"No pronunciation in: {native[:60]}"


# ── Rule 15: Surprise Me ─────────────────────────────────

def test_surprise_english_returns_english(base_url):
    r = requests.get(f"{base_url}/api/surprise?lang=ja&input_lang=en")
    assert r.ok
    sentence = r.json().get("sentence", "")
    has_cjk = any('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in sentence)
    assert not has_cjk, f"Got CJK in English surprise: {sentence}"

def test_surprise_chinese_returns_chinese(base_url):
    r = requests.get(f"{base_url}/api/surprise?lang=ja&input_lang=zh")
    assert r.ok
    sentence = r.json().get("sentence", "")
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in sentence)
    assert has_cjk, f"No Chinese in zh surprise: {sentence}"


# ── Rule 18: No Echo-back ────────────────────────────────

def test_translation_not_echoing_input(api_learn):
    d = api_learn("I want to eat ramen", "ja", "en")
    if not d:
        time.sleep(3)
        d = api_learn("I want to eat ramen", "ja", "en")
    assert d, "API call failed twice"
    trans = d.get("translation", "")
    assert trans != "I want to eat ramen", f"Echo: {trans}"
    has_japanese = any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in trans)
    assert has_japanese, f"No Japanese chars in: {trans}"


# ── Rule 19: Empty Sentence Validation ────────────────────

def test_rejects_empty_sentence(base_url, headers):
    r = requests.post(f"{base_url}/api/learn", headers=headers, json={
        "sentence": "", "target_language": "ja", "input_language": "en"
    }, timeout=10)
    assert r.status_code == 400, f"Got {r.status_code}"

def test_rejects_whitespace_sentence(base_url, headers):
    r = requests.post(f"{base_url}/api/learn", headers=headers, json={
        "sentence": "   ", "target_language": "ja", "input_language": "en"
    }, timeout=10)
    assert r.status_code == 400, f"Got {r.status_code}"


# ── Rule 20: Password Protection ─────────────────────────

def test_rejects_no_password(base_url):
    r = requests.post(f"{base_url}/api/learn", headers={"Content-Type": "application/json"}, json={
        "sentence": "test", "target_language": "ja"
    }, timeout=10)
    assert r.status_code == 401

def test_rejects_wrong_password(base_url):
    r = requests.post(f"{base_url}/api/learn",
        headers={"Content-Type": "application/json", "X-App-Password": "wrong"}, json={
        "sentence": "test", "target_language": "ja"
    }, timeout=10)
    assert r.status_code == 401


# ── Rule 21: OpenCC Traditional Chinese ───────────────────

def test_opencc_traditional(api_learn):
    d = api_learn("Information technology is developing rapidly", "zh", "en")
    assert d, "API call failed"
    trans = d.get("translation", "")
    assert "信息" not in trans or "資訊" in trans, f"Got simplified term: {trans}"


# ── Rule 22: Health Endpoint ──────────────────────────────

def test_health_endpoint(base_url):
    r = requests.get(f"{base_url}/api/health", timeout=10)
    assert r.ok
    h = r.json()
    assert "status" in h
    assert "ollama" in h and "reachable" in h["ollama"]
    assert "cache" in h and "entries" in h["cache"]
    assert "surprise_bank" in h and "total_entries" in h["surprise_bank"]


# ── Rule 23: Surprise Bank Status ─────────────────────────

def test_surprise_bank_status(base_url):
    r = requests.get(f"{base_url}/api/surprise-bank-status", timeout=10)
    assert r.ok
    sb = r.json()
    assert "filling" in sb
    assert "banks" in sb and isinstance(sb["banks"], dict)


# ── Rule 24: Feedback List ────────────────────────────────

def test_feedback_list_requires_auth(base_url):
    r = requests.get(f"{base_url}/api/feedback-list", timeout=10)
    assert r.status_code == 401

def test_feedback_list_with_auth(base_url, headers):
    r = requests.get(f"{base_url}/api/feedback-list", headers={"X-App-Password": headers["X-App-Password"]}, timeout=10)
    assert r.ok
    fb = r.json()
    assert "total" in fb
    assert "entries" in fb and isinstance(fb["entries"], list)


# ── Rule 25: Feedback Delete ──────────────────────────────

def test_feedback_delete_requires_auth(base_url):
    r = requests.delete(f"{base_url}/api/feedback/0", timeout=10)
    assert r.status_code == 401

def test_feedback_delete_out_of_range(base_url, headers):
    r = requests.delete(f"{base_url}/api/feedback/999999",
        headers={"X-App-Password": headers["X-App-Password"]}, timeout=10)
    assert r.status_code == 404


# ── Difficulty Field ──────────────────────────────────────

def test_difficulty_field_wired(api_learn):
    """difficulty should be populated from sentence_difficulty.level"""
    d = api_learn("My neighbor grows beautiful sunflowers", "ja", "en")
    assert d, "API call failed"
    assert d.get("difficulty") is not None, \
        f"difficulty is null, sentence_difficulty={d.get('sentence_difficulty')}"
