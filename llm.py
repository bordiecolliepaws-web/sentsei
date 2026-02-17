"""LLM interaction (Ollama), prompt building, pronunciation, and post-processing."""
import os
import json
import re as _re
import hashlib
import random
import time
from typing import Optional, List
from pathlib import Path

from log import get_logger

logger = get_logger("sentsei.llm")

import httpx
import MeCab
import pykakasi
from pypinyin import pinyin, Style as PinyinStyle
from korean_romanizer.romanizer import Romanizer
from opencc import OpenCC

from models import SUPPORTED_LANGUAGES

# --- Config ---
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b-instruct-q3_K_M"
TAIDE_MODEL = "jcai/llama3-taide-lx-8b-chat-alpha1:Q4_K_M"

# --- Pronunciation ---
_kakasi = pykakasi.kakasi()
_mecab_tagger = MeCab.Tagger()
_s2twp = OpenCC('s2twp')

# Common reading overrides (MeCab/unidic sometimes gives formal readings)
_JA_READING_OVERRIDES = {
    "私": "watashi",      # unidic gives watakushi (formal)
    "俺": "ore",
    "僕": "boku",
}

# Japanese punctuation to strip from romaji output
_JA_PUNCT = set("、。！？「」『』（）…—·〜～，")


def _katakana_to_romaji(kata: str) -> str:
    """Convert katakana string to Hepburn romaji via pykakasi."""
    conv = _kakasi.convert(kata)
    return "".join(item["hepburn"] for item in conv)


def _clean_long_vowels(romaji: str) -> str:
    """Convert doubled vowels to macron notation (standard Hepburn)."""
    romaji = _re.sub(r"aa", "ā", romaji)
    romaji = _re.sub(r"ii", "ī", romaji)
    romaji = _re.sub(r"uu", "ū", romaji)
    romaji = _re.sub(r"ee", "ē", romaji)
    romaji = _re.sub(r"ou", "ō", romaji)
    romaji = _re.sub(r"oo", "ō", romaji)
    return romaji


def _japanese_pronunciation(text: str) -> str:
    """High-quality Japanese romanization using MeCab tokenization + pykakasi conversion.
    
    Improvements over raw pykakasi:
    - Correct particle pronunciation (は→wa, を→o, へ→e)
    - Proper long vowel macrons (ā, ī, ū, ē, ō)
    - Better tokenization (食べたいです → tabe tai desu, not tabeta idesu)
    - Common reading overrides (私→watashi, not watakushi)
    - Punctuation stripped from output
    """
    node = _mecab_tagger.parseToNode(text)
    parts = []
    while node:
        surface = node.surface
        if not surface:
            node = node.next
            continue
        
        # Skip punctuation
        if all(c in _JA_PUNCT for c in surface):
            node = node.next
            continue
        
        features = node.feature.split(",")
        pos = features[0] if features else ""
        
        # Check overrides first
        if surface in _JA_READING_OVERRIDES:
            parts.append(_JA_READING_OVERRIDES[surface])
            node = node.next
            continue
        
        # Particle corrections
        if "助詞" in pos:
            if surface == "は":
                parts.append("wa")
                node = node.next
                continue
            elif surface == "を":
                parts.append("o")
                node = node.next
                continue
            elif surface == "へ":
                parts.append("e")
                node = node.next
                continue
        
        # Use MeCab pronunciation field (index 9 in unidic) if available
        pronunciation_kata = features[9] if len(features) > 9 and features[9] != "*" else None
        if pronunciation_kata:
            romaji = _katakana_to_romaji(pronunciation_kata)
        else:
            romaji = _katakana_to_romaji(surface)
        
        if romaji.strip():
            parts.append(romaji)
        
        node = node.next
    
    raw = " ".join(parts)
    return _clean_long_vowels(raw)


_GREEK_TRANSLIT = {
    'Α': 'A', 'Β': 'V', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z',
    'Η': 'I', 'Θ': 'Th', 'Ι': 'I', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M',
    'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P', 'Ρ': 'R', 'Σ': 'S',
    'Τ': 'T', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'Ch', 'Ψ': 'Ps', 'Ω': 'O',
    'α': 'a', 'β': 'v', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z',
    'η': 'i', 'θ': 'th', 'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm',
    'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p', 'ρ': 'r', 'σ': 's',
    'ς': 's', 'τ': 't', 'υ': 'y', 'φ': 'f', 'χ': 'ch', 'ψ': 'ps',
    'ω': 'o', 'ά': 'á', 'έ': 'é', 'ή': 'í', 'ί': 'í', 'ό': 'ó',
    'ύ': 'ý', 'ώ': 'ó', 'ϊ': 'i', 'ϋ': 'y', 'ΐ': 'í', 'ΰ': 'ý',
    'Ά': 'Á', 'Έ': 'É', 'Ή': 'Í', 'Ί': 'Í', 'Ό': 'Ó', 'Ύ': 'Ý', 'Ώ': 'Ó',
}

_GREEK_DIGRAPHS = {
    'ου': 'ou', 'Ου': 'Ou', 'ΟΥ': 'OU',
    'αι': 'e', 'Αι': 'E', 'ΑΙ': 'E',
    'ει': 'i', 'Ει': 'I', 'ΕΙ': 'I',
    'οι': 'i', 'Οι': 'I', 'ΟΙ': 'I',
    'αυ': 'av', 'Αυ': 'Av', 'ΑΥ': 'AV',
    'ευ': 'ev', 'Ευ': 'Ev', 'ΕΥ': 'EV',
    'μπ': 'b', 'Μπ': 'B', 'ΜΠ': 'B',
    'ντ': 'nt', 'Ντ': 'Nt', 'ΝΤ': 'NT',
    'γκ': 'gk', 'Γκ': 'Gk', 'ΓΚ': 'GK',
    'γγ': 'ng', 'ΓΓ': 'NG',
}


_HEBREW_CONSLIT = {
    'א': '', 'ב': 'v', 'ג': 'g', 'ד': 'd', 'ה': 'h',
    'ז': 'z', 'ח': 'ch', 'ט': 't', 'כ': 'kh', 'ך': 'kh',
    'ל': 'l', 'מ': 'm', 'ם': 'm', 'נ': 'n', 'ן': 'n',
    'ס': 's', 'ע': "'", 'פ': 'f', 'ף': 'f', 'צ': 'ts', 'ץ': 'ts',
    'ק': 'k', 'ר': 'r', 'ש': 'sh', 'ת': 't',
}

# Dagesh/shin-dot variants (2-char: consonant + combining mark)
_HEBREW_DAGESH = {
    'בּ': 'b', 'גּ': 'g', 'דּ': 'd', 'כּ': 'k', 'פּ': 'p', 'תּ': 't',
    'שׁ': 'sh', 'שׂ': 's',
}

# Hebrew niqqud (vowel marks)
_HEBREW_VOWELS = {
    '\u05B0': 'e',   # shva
    '\u05B1': 'e',   # hataf segol
    '\u05B2': 'a',   # hataf patach
    '\u05B3': 'o',   # hataf qamats
    '\u05B4': 'i',   # hiriq
    '\u05B5': 'e',   # tsere
    '\u05B6': 'e',   # segol
    '\u05B7': 'a',   # patach
    '\u05B8': 'a',   # qamats
    '\u05B9': 'o',   # holam
    '\u05BA': 'o',   # holam haser
    '\u05BB': 'u',   # qubuts
}

# Common Hebrew words with known romanization (unvoweled → romanized)
_HEBREW_DICT = {
    'שלום': 'shalom', 'אני': 'ani', 'אתה': 'ata', 'את': 'at',
    'הוא': 'hu', 'היא': 'hi', 'אנחנו': 'anachnu', 'הם': 'hem',
    'הן': 'hen', 'כן': 'ken', 'לא': 'lo', 'מה': 'ma', 'מי': 'mi',
    'איפה': 'eifo', 'למה': 'lama', 'איך': 'eikh', 'מתי': 'matai',
    'תודה': 'toda', 'בבקשה': 'bevakasha', 'סליחה': 'slikha',
    'בוקר': 'boker', 'ערב': 'erev', 'לילה': 'laila', 'יום': 'yom',
    'טוב': 'tov', 'טובה': 'tova', 'רע': 'ra', 'גדול': 'gadol',
    'קטן': 'katan', 'יפה': 'yafe', 'חדש': 'chadash', 'ישן': 'yashan',
    'אוכל': 'okhel', 'מים': 'mayim', 'לחם': 'lekhem', 'בית': 'bayit',
    'ספר': 'sefer', 'ילד': 'yeled', 'ילדה': 'yalda', 'איש': 'ish',
    'אישה': 'isha', 'אבא': 'aba', 'אמא': 'ima', 'חבר': 'khaver',
    'ברוך': 'barukh', 'הבא': 'haba', 'שם': 'sham', 'פה': 'po',
    'עכשיו': 'akhshav', 'היום': 'hayom', 'מחר': 'makhar', 'אתמול': 'etmol',
    'שנה': 'shana', 'חודש': 'khodesh', 'שבוע': 'shavua',
    'אחד': 'ekhad', 'שניים': 'shnayim', 'שלוש': 'shalosh',
    'ארבע': 'arba', 'חמש': 'khamesh', 'שש': 'shesh', 'שבע': 'sheva',
    'שמונה': 'shmone', 'תשע': 'tesha', 'עשר': 'eser',
    'אהבה': 'ahava', 'חיים': 'khayim', 'עולם': 'olam',
    'ישראל': 'yisrael', 'ירושלים': 'yerushalayim',
    'שמח': 'same\'akh', 'רוצה': 'rotse', 'יודע': 'yode\'a',
    'הולך': 'holekh', 'בא': 'ba', 'רואה': 'ro\'e', 'שומע': 'shome\'a',
    'אוהב': 'ohev', 'אוהבת': 'ohevet', 'לומד': 'lomed',
    'עובד': 'oved', 'גר': 'gar', 'נסיעה': 'nesi\'a', 'טיול': 'tiyul',
    'כסף': 'kesef', 'זמן': 'zman', 'מקום': 'makom', 'דרך': 'derekh',
    'שלומך': 'shlomkha', 'אותך': 'otkha', 'אותי': 'oti', 'אותו': 'oto',
    'שלי': 'sheli', 'שלך': 'shelkha', 'של': 'shel',
    'זה': 'ze', 'זאת': 'zot', 'אלה': 'ele', 'הזה': 'haze',
    'עם': 'im', 'על': 'al', 'אל': 'el', 'מן': 'min', 'בין': 'bein',
    'גם': 'gam', 'רק': 'rak', 'עוד': 'od', 'כבר': 'kvar', 'אז': 'az',
    'יש': 'yesh', 'אין': 'ein', 'צריך': 'tsarikh', 'יכול': 'yakhol',
    'רוצה': 'rotse', 'אוהב': 'ohev', 'אוהבת': 'ohevet',
    'לעשות': 'la\'asot', 'ללכת': 'lalekhet', 'לאכול': 'le\'ekhol',
    'לדבר': 'ledaber', 'לראות': 'lir\'ot', 'לשמוע': 'lishmoa',
    'אחת': 'akhat', 'שתיים': 'shtayim', 'מאה': 'me\'a', 'אלף': 'elef',
    'חם': 'kham', 'קר': 'kar', 'מהר': 'maher', 'לאט': 'le\'at',
    'כל': 'kol', 'הרבה': 'harbe', 'מעט': 'me\'at', 'קצת': 'ktsat',
    'אחרי': 'akharei', 'לפני': 'lifnei', 'ליד': 'leyad',
    'למעלה': 'lemala', 'למטה': 'lemata',
}

def _is_hebrew(ch):
    return '\u05D0' <= ch <= '\u05EA'

def _hebrew_romanize(text: str) -> str:
    """Romanize Hebrew text. Uses dictionary for common words, falls back to
    character mapping with heuristics for vav/yod as vowel letters."""
    import unicodedata
    # Word-by-word: use dictionary when available, fallback per word
    words = text.split()
    if len(words) > 1:
        parts = []
        for word in words:
            clean = word.strip('.,!?;:\'"')
            if clean in _HEBREW_DICT:
                parts.append(_HEBREW_DICT[clean])
            else:
                parts.append(_hebrew_romanize(word))
        return ' '.join(parts)

    # Single word dictionary check
    clean = text.strip('.,!?;:\'"')
    if clean in _HEBREW_DICT:
        return _HEBREW_DICT[clean]

    # Fallback: character-by-character transliteration
    result = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        # Check for consonant + combining mark pairs (dagesh, shin/sin dot)
        if i + 1 < n:
            pair = text[i:i+2]
            if pair in _HEBREW_DAGESH:
                result.append(_HEBREW_DAGESH[pair])
                i += 2
                continue

        # Niqqud vowel points
        if ch in _HEBREW_VOWELS:
            result.append(_HEBREW_VOWELS[ch])
            i += 1
            continue

        # Skip other combining marks
        if unicodedata.category(ch) == 'Mn':
            i += 1
            continue

        # Vav - could be v, o, or u
        if ch == 'ו':
            # Double vav = v
            if i + 1 < n and text[i+1] == 'ו':
                result.append('v')
                i += 2
                continue
            # Vav between/after consonants in unvoweled text → 'o' (most common)
            # but word-initial vav before consonant → 've-' (conjunction)
            prev_is_cons = (i > 0 and _is_hebrew(text[i-1]) and text[i-1] not in 'וי')
            next_is_cons = (i + 1 < n and _is_hebrew(text[i+1]))
            if i == 0 and next_is_cons:
                # Word-initial vav = ve- conjunction
                result.append('ve')
            elif prev_is_cons and next_is_cons:
                result.append('o')
            elif prev_is_cons and (i + 1 >= n or not _is_hebrew(text[i+1])):
                result.append('o')
            else:
                result.append('v')
            i += 1
            continue

        # Yod - could be y or i
        if ch == 'י':
            prev_is_cons = (i > 0 and _is_hebrew(text[i-1]) and text[i-1] not in 'וי')
            next_is_cons = (i + 1 < n and _is_hebrew(text[i+1]))
            next_not_heb = (i + 1 >= n or not _is_hebrew(text[i+1]))
            if prev_is_cons and (next_is_cons or next_not_heb):
                result.append('i')
            else:
                result.append('y')
            i += 1
            continue

        # Regular consonant
        if ch in _HEBREW_CONSLIT:
            result.append(_HEBREW_CONSLIT[ch])
            i += 1
            continue

        # Pass through spaces, punctuation, etc.
        result.append(ch)
        i += 1
    return "".join(result)


def _greek_romanize(text: str) -> str:
    result = []
    i = 0
    while i < len(text):
        if i + 1 < len(text):
            digraph = text[i:i+2]
            if digraph in _GREEK_DIGRAPHS:
                result.append(_GREEK_DIGRAPHS[digraph])
                i += 2
                continue
        ch = text[i]
        result.append(_GREEK_TRANSLIT.get(ch, ch))
        i += 1
    return "".join(result)


def deterministic_pronunciation(text: str, lang_code: str) -> Optional[str]:
    if lang_code == "ja":
        return _japanese_pronunciation(text)
    elif lang_code == "zh":
        result = pinyin(text, style=PinyinStyle.TONE)
        return " ".join(p[0] for p in result)
    elif lang_code == "ko":
        r = Romanizer(text)
        return r.romanize()
    elif lang_code == "el":
        return _greek_romanize(text)
    elif lang_code == "he":
        return _hebrew_romanize(text)
    elif lang_code in ("it", "es", "en"):
        return text
    return None


def deterministic_word_pronunciation(word: str, lang_code: str) -> Optional[str]:
    return deterministic_pronunciation(word, lang_code)


def ensure_traditional_chinese(obj):
    if isinstance(obj, str):
        return _s2twp.convert(obj)
    elif isinstance(obj, list):
        return [ensure_traditional_chinese(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: ensure_traditional_chinese(v) for k, v in obj.items()}
    return obj


def detect_sentence_difficulty(sentence: str, breakdown: list = None) -> dict:
    factors = []
    score = 0
    text = sentence.strip()
    cjk_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' or '\uac00' <= c <= '\ud7af')
    is_cjk = cjk_chars / max(len(text.replace(" ", "")), 1) > 0.3

    if is_cjk:
        meaningful = sum(1 for c in text if c.strip() and c not in '，。！？、「」『』（）…—·')
        if meaningful <= 5:
            score += 5; factors.append("Very short phrase")
        elif meaningful <= 12:
            score += 20; factors.append(f"Medium length ({meaningful} characters)")
        elif meaningful <= 25:
            score += 45; factors.append(f"Long sentence ({meaningful} characters)")
        else:
            score += 65; factors.append(f"Very long sentence ({meaningful} characters)")
        unique_chars = len(set(c for c in text if '\u4e00' <= c <= '\u9fff'))
        if unique_chars > 15:
            score += 15; factors.append(f"High character diversity ({unique_chars} unique)")
        elif unique_chars > 8:
            score += 8
    else:
        words = text.split()
        word_count = len(words)
        if word_count <= 4:
            score += 5; factors.append("Short phrase")
        elif word_count <= 10:
            score += 20; factors.append(f"Medium sentence ({word_count} words)")
        elif word_count <= 20:
            score += 40; factors.append(f"Long sentence ({word_count} words)")
        else:
            score += 60; factors.append(f"Very long sentence ({word_count} words)")
        avg_len = sum(len(w.strip('.,!?;:')) for w in words) / max(word_count, 1)
        if avg_len > 7:
            score += 15; factors.append("Complex vocabulary (long words)")
        elif avg_len > 5:
            score += 8
        complexity_markers = ['although', 'however', 'nevertheless', 'whereas', 'furthermore',
                            'consequently', 'notwithstanding', 'if', 'because', 'since', 'while',
                            'unless', 'whether', 'whom', 'whose', 'whereby']
        found = [m for m in complexity_markers if m in text.lower()]
        if found:
            score += min(len(found) * 8, 20)
            factors.append(f"Complex grammar ({', '.join(found[:3])})")

    if breakdown:
        hard_count = sum(1 for w in breakdown if w.get("difficulty") == "hard")
        medium_count = sum(1 for w in breakdown if w.get("difficulty") == "medium")
        total = len(breakdown)
        if total > 0:
            hard_ratio = hard_count / total
            if hard_ratio > 0.3:
                score += 20; factors.append(f"{hard_count}/{total} words marked hard")
            elif hard_ratio > 0.1:
                score += 10
            if medium_count / total > 0.5:
                score += 5

    score = min(score, 100)
    if score <= 25: level = "beginner"
    elif score <= 55: level = "intermediate"
    else: level = "advanced"
    return {"level": level, "score": score, "factors": factors}


# --- CC-CEDICT Dictionary ---
_cedict_data = {}
_cedict_path = Path(__file__).parent / "cedict_dict.json"
if _cedict_path.exists():
    _cedict_data = json.loads(_cedict_path.read_text())

_jieba_dict_path = Path(__file__).parent / "jieba_tw_dict.txt"
if _jieba_dict_path.exists():
    import jieba as _jieba_init
    with open(_jieba_dict_path) as _f:
        for _line in _f:
            _w = _line.strip()
            if _w:
                _jieba_init.add_word(_w)

_particle_overrides = {
    "的": "(possessive/descriptive particle)", "了": "(completion/change particle)",
    "是": "is; am; are", "在": "at; in; (progressive particle)", "把": "(object-marking particle)",
    "被": "(passive particle)", "得": "(complement particle)", "地": "(adverbial particle)",
    "著": "(continuous aspect particle)", "過": "(experiential particle)",
    "會": "will; can", "能": "can; able to", "要": "want; need; will",
}


def cedict_lookup(word: str) -> Optional[str]:
    if word in _particle_overrides:
        return _particle_overrides[word]
    return _cedict_data.get(word)


# --- Helpers ---

def parse_json_object(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _re.search(r'\{.*\}', text, _re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None


def split_sentences(text: str) -> List[str]:
    parts = _re.split(r'(?<=[.!?。！？])\s*', text.strip())
    return [s.strip() for s in parts if s.strip()]


def new_quiz_id(lang: str, sentence: str) -> str:
    raw = f"{lang}|{sentence}|{time.time_ns()}|{random.random()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def translation_hint(text: str) -> str:
    cleaned = (text or "").strip().strip("\"'""''")
    if not cleaned:
        return ""
    first = _re.split(r"\s+", cleaned)[0]
    first = _re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", first)
    if not first:
        first = cleaned[:2]
    if any('\u4e00' <= c <= '\u9fff' for c in first) and len(first) > 2:
        first = first[:2]
    return first


def sanitize_tsv_cell(value: Optional[str]) -> str:
    text = (value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ").replace("\n", " ")
    return text.strip()


def anki_language_label(code: str) -> str:
    name = SUPPORTED_LANGUAGES.get(code, code)
    return f"{name} ({code})" if name != code else code


async def ollama_chat(messages: list, model: str = None, temperature: float = 0.3,
                      num_predict: int = 2048, timeout: int = 120) -> str:
    """Call Ollama chat API and return the content string."""
    if model is None:
        model = OLLAMA_MODEL
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": num_predict},
            },
        )
    if resp.status_code != 200:
        return None
    return resp.json().get("message", {}).get("content", "")


async def check_ollama_connectivity() -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        logger.warning("Ollama not reachable", extra={"component": "ollama"})
        return False
