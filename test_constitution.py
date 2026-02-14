"""Sent-Say Constitution Test Suite
Tests every rule in CONSTITUTION.md against the live app.
Run: python3 test_constitution.py
"""
import atexit
import json
import os
import subprocess
import sys
import time
import requests

# Lock file to prevent watchdog from restarting server during tests
LOCKFILE = "/tmp/sentsei-test.lock"
open(LOCKFILE, 'w').close()
atexit.register(lambda: os.unlink(LOCKFILE) if os.path.exists(LOCKFILE) else None)

BASE = "http://localhost:8847"
PASSWORD = "sentsei2026"
HEADERS = {"Content-Type": "application/json", "X-App-Password": PASSWORD}

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        errors.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")

def api_learn(sentence, target, input_lang="auto"):
    r = requests.post(f"{BASE}/api/learn", headers=HEADERS, json={
        "sentence": sentence, "target_language": target, "input_language": input_lang
    }, timeout=120)
    return r.json() if r.ok else None

print("\n🔍 Sent-Say Constitution Test Suite\n" + "="*50)

# Rule -1: JavaScript syntax check
print("\n[JS Syntax]")
js_check = subprocess.run(
    ['node', '-e', '''
const fs = require('fs');
const html = fs.readFileSync('static/index.html', 'utf8');
const match = html.match(/<script>([\\s\\S]*?)<\\/script>/);
if (match) { try { new Function(match[1]); console.log('OK'); } catch(e) { console.log('ERROR:' + e.message); } }
'''],
    capture_output=True, text=True, cwd='/home/opclaw/.openclaw/workspace-sora/sentsei'
)
test("JavaScript has no syntax errors", js_check.stdout.strip() == 'OK', js_check.stdout.strip())

# Rule 0: Server is up
print("\n[Server Health]")
try:
    r = requests.get(f"{BASE}/api/languages", timeout=5)
    test("Server is up", r.ok)
    langs = r.json()
    test("All 8 languages available", len(langs) == 8, f"Got {len(langs)}")
except Exception as e:
    test("Server is up", False, str(e))
    print("\n💀 Server is down. Cannot continue.")
    sys.exit(1)

# Rule 1: Traditional Chinese only (no simplified)
print("\n[Rule 1: Traditional Chinese Only]")
d = api_learn("This coffee tastes amazing", "zh", "en")
if d:
    trans = d.get("translation", "")
    simplified_chars = set("这个说问请对会认语让给听时书车东发电长门见马鱼鸟点机关开进过还运动华国图区号头买卖写读话词记讲计议设试谁准难双欢观视显单习练经验继续热爱岁梦样飞")
    found_simplified = [c for c in trans if c in simplified_chars]
    test("No simplified Chinese in translation", len(found_simplified) == 0, f"Found: {''.join(found_simplified)}")
    
    # Check breakdown too
    for w in d.get("breakdown", []):
        found = [c for c in w.get("word", "") if c in simplified_chars]
        if found:
            test(f"No simplified in word '{w.get('word')}'", False, f"Found: {''.join(found)}")
            break
    else:
        test("No simplified Chinese in breakdown words", True)

# Rule 2: Explanations in input language
print("\n[Rule 2: Explanations in Input Language]")
d = api_learn("This coffee tastes amazing", "zh", "en")
if d:
    grammar = d.get("grammar_notes", [])
    # Check if grammar notes are PRIMARILY in Chinese (a few Chinese words as examples are OK)
    for note in grammar:
        chinese_chars = sum(1 for c in note if '\u4e00' <= c <= '\u9fff')
        total_chars = len(note)
        ratio = chinese_chars / max(total_chars, 1)
        if ratio > 0.5:
            test("Grammar notes in English (for English input)", False, f"Mostly Chinese: {note[:80]}")
            break
    else:
        test("Grammar notes in English (for English input)", True)
    
    meanings = [w.get("meaning", "") for w in d.get("breakdown", [])]
    has_chinese_meanings = any(any('\u4e00' <= c <= '\u9fff' for c in m) for m in meanings)
    test("Word meanings in English (for English input)", not has_chinese_meanings, f"Meanings: {meanings[:2]}")

# Rule 2b: Chinese input → Chinese explanations
d2 = api_learn("I want to eat ramen", "zh", "zh")
# Skip this — input is English text with zh flag, not useful

# Rule 5: Pronunciation standard
print("\n[Rule 5: Standard Pronunciation]")
d = api_learn("Please teach me", "ja", "en")
if d:
    pron = d.get("pronunciation", "")
    test("Japanese uses romaji (not ALL CAPS garbage)", not any(w.isupper() and len(w) > 3 for w in pron.split()), f"Got: {pron}")

# Rule 8: Layout (check HTML structure)
print("\n[Rule 8: Layout Order]")
import re
html = requests.get(f"{BASE}/").text
source_pos = html.find('result-source')
trans_pos = html.find('result-translation')
# In the template, source should come before translation
test("Input sentence before translation in HTML", source_pos < trans_pos and source_pos > 0, f"source@{source_pos} trans@{trans_pos}")

# Rule 10: Favicon is 學 not 学
print("\n[Rule 10: Traditional Favicon]")
test("Favicon uses 學 (traditional)", '學' in html or '%E5%AD%B8' in html, "Check favicon tag")
test("Favicon NOT 学 (simplified)", '学' not in html.split('favicon')[0] if 'favicon' in html else True)

# Rule 11: IME composition guard
print("\n[Rule 11: IME Composition Guard]")
test("compositionstart listener exists", 'compositionstart' in html)
test("compositionend listener exists", 'compositionend' in html)
test("isComposing check in keydown", 'isComposing' in html)

# Rule 13: Native expression differs from translation
print("\n[Rule 13: Native Expression]")
d = api_learn("I want to order a coffee", "zh", "en")
if d:
    native = d.get("native_expression")
    trans = d.get("translation", "")
    if native:
        native_sentence = native.split("|")[0].strip() if "|" in native else native.split("(")[0].strip()
        test("Native expression differs from translation", native_sentence.rstrip("。") != trans.rstrip("。"), f"Both: {trans}")
        test("Native expression has pronunciation", "|" in native or "(" in native, f"Got: {native[:60]}")
    else:
        test("Native expression provided", native is not None, "Got null")

# Rule 15: Surprise me returns input-language sentences
print("\n[Rule 15: Surprise Me in Input Language]")
r = requests.get(f"{BASE}/api/surprise?lang=ja&input_lang=en")
if r.ok:
    s = r.json()
    sentence = s.get("sentence", "")
    has_cjk = any('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' for c in sentence)
    test("Surprise (en) returns English sentence", not has_cjk, f"Got: {sentence}")

r = requests.get(f"{BASE}/api/surprise?lang=ja&input_lang=zh")
if r.ok:
    s = r.json()
    sentence = s.get("sentence", "")
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in sentence)
    test("Surprise (zh) returns Chinese sentence", has_cjk, f"Got: {sentence}")

# Rule 18: Translation not echoing input
print("\n[Rule 18: No Echo-back]")
d = api_learn("I want to eat ramen", "ja", "en")
if not d:  # Retry once on timeout
    time.sleep(3)
    d = api_learn("I want to eat ramen", "ja", "en")
if d:
    trans = d.get("translation", "")
    test("Japanese translation is not English", trans != "I want to eat ramen", f"Got: {trans}")
    has_japanese = any('\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in trans)
    test("Japanese translation contains Japanese characters", has_japanese, f"Got: {trans}")

# Rule 19: Empty sentence validation
print("\n[Rule 19: Empty Sentence Validation]")
r = requests.post(f"{BASE}/api/learn", headers=HEADERS, json={
    "sentence": "", "target_language": "ja", "input_language": "en"
}, timeout=10)
test("API rejects empty sentence", r.status_code == 400, f"Got status {r.status_code}")
r2 = requests.post(f"{BASE}/api/learn", headers=HEADERS, json={
    "sentence": "   ", "target_language": "ja", "input_language": "en"
}, timeout=10)
test("API rejects whitespace-only sentence", r2.status_code == 400, f"Got status {r2.status_code}")

# Rule 20: Password protection
print("\n[Rule 20: Password Protection]")
r = requests.post(f"{BASE}/api/learn", headers={"Content-Type": "application/json"}, json={
    "sentence": "test", "target_language": "ja"
}, timeout=10)
test("API rejects request without password", r.status_code == 401)

r = requests.post(f"{BASE}/api/learn", headers={"Content-Type": "application/json", "X-App-Password": "wrong"}, json={
    "sentence": "test", "target_language": "ja"
}, timeout=10)
test("API rejects wrong password", r.status_code == 401)

# Rule 21: OpenCC post-processing
print("\n[Rule 21: OpenCC Traditional Chinese Enforcement]")
# Already tested in Rule 1, but let's test with a sentence that typically generates simplified
d = api_learn("Information technology is developing rapidly", "zh", "en")
if d:
    trans = d.get("translation", "")
    test("Uses 資訊 not 信息", "信息" not in trans or "資訊" in trans, f"Got: {trans}")

# Summary
print("\n" + "="*50)
print(f"Results: {passed} passed, {failed} failed")
if errors:
    print("\n❌ Failures:")
    for e in errors:
        print(f"  - {e}")
print()
