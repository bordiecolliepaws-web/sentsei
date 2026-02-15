"""Sent-Say — Sentence-based language learning app."""
import json
import re as _re
import random
import hashlib
import time
from typing import Optional, List
from pathlib import Path
from collections import OrderedDict, defaultdict
from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

# Deterministic pronunciation libraries
import pykakasi
from pypinyin import pinyin, Style as PinyinStyle
from korean_romanizer.romanizer import Romanizer

from opencc import OpenCC
_kakasi = pykakasi.kakasi()
_s2twp = OpenCC('s2twp')  # Simplified → Traditional (Taiwan phrases)


def ensure_traditional_chinese(obj):
    """Recursively convert any simplified Chinese to Traditional Chinese (Taiwan) in JSON output."""
    if isinstance(obj, str):
        return _s2twp.convert(obj)
    elif isinstance(obj, list):
        return [ensure_traditional_chinese(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: ensure_traditional_chinese(v) for k, v in obj.items()}
    return obj


def deterministic_pronunciation(text: str, lang_code: str) -> Optional[str]:
    """Generate deterministic pronunciation for supported languages."""
    if lang_code == "ja":
        result = _kakasi.convert(text)
        return " ".join(item["hepburn"] for item in result if item["hepburn"].strip())
    elif lang_code == "zh":
        result = pinyin(text, style=PinyinStyle.TONE)
        return " ".join(p[0] for p in result)
    elif lang_code == "ko":
        r = Romanizer(text)
        return r.romanize()
    return None


def deterministic_word_pronunciation(word: str, lang_code: str) -> Optional[str]:
    """Generate deterministic pronunciation for a single word."""
    return deterministic_pronunciation(word, lang_code)

app = FastAPI()

# --- In-memory LRU cache for translations ---
CACHE_MAX = 500          # max entries
CACHE_TTL = 3600 * 24    # 24h expiry
_translation_cache: OrderedDict = OrderedDict()  # key -> (timestamp, result)
QUIZ_ANSWER_TTL = 3600   # quiz answer retention (seconds)
_quiz_answers: dict = {}  # quiz_id -> answer payload


def _cache_key(sentence: str, target: str, gender: str, formality: str) -> str:
    raw = f"{sentence.strip().lower()}|{target}|{gender}|{formality}"
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_get(key: str):
    entry = _translation_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > CACHE_TTL:
        _translation_cache.pop(key, None)
        return None
    _translation_cache.move_to_end(key)
    return result


def cache_put(key: str, result: dict):
    _translation_cache[key] = (time.time(), result)
    if len(_translation_cache) > CACHE_MAX:
        _translation_cache.popitem(last=False)


def _cleanup_quiz_answers():
    cutoff = time.time() - QUIZ_ANSWER_TTL
    stale_ids = [qid for qid, payload in _quiz_answers.items() if payload.get("created_at", 0) < cutoff]
    for qid in stale_ids:
        _quiz_answers.pop(qid, None)


def _new_quiz_id(lang: str, sentence: str) -> str:
    raw = f"{lang}|{sentence}|{time.time_ns()}|{random.random()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _translation_hint(text: str) -> str:
    cleaned = (text or "").strip().strip("\"'“”‘’")
    if not cleaned:
        return ""
    first = _re.split(r"\s+", cleaned)[0]
    first = _re.sub(r"^[^\w\u4e00-\u9fff]+|[^\w\u4e00-\u9fff]+$", "", first)
    if not first:
        first = cleaned[:2]
    if any('\u4e00' <= c <= '\u9fff' for c in first) and len(first) > 2:
        first = first[:2]
    return first


def _parse_json_object(text: str) -> Optional[dict]:
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


# --- IP-based sliding window rate limiter ---
RATE_LIMIT_REQUESTS = 30   # max requests per window
RATE_LIMIT_WINDOW = 60     # window in seconds
_rate_buckets: dict = defaultdict(list)  # ip -> [timestamps]


def _rate_limit_check(ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    # Prune old timestamps
    _rate_buckets[ip] = [t for t in _rate_buckets[ip] if t > cutoff]
    if len(_rate_buckets[ip]) >= RATE_LIMIT_REQUESTS:
        return False
    _rate_buckets[ip].append(now)
    return True


# Periodic cleanup of stale IPs (run every 100 checks)
_rate_check_counter = 0


def _rate_limit_cleanup():
    global _rate_check_counter
    _rate_check_counter += 1
    if _rate_check_counter % 100 == 0:
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW
        stale = [ip for ip, ts in _rate_buckets.items() if not ts or ts[-1] < cutoff]
        for ip in stale:
            del _rate_buckets[ip]


APP_PASSWORD = "sentsei2026"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
TAIDE_MODEL = "jcai/llama3-taide-lx-8b-chat-alpha1:Q4_K_M"

# Load CC-CEDICT dictionary + jieba custom words
_cedict_data = {}
_cedict_path = Path(__file__).parent / "cedict_dict.json"
if _cedict_path.exists():
    _cedict_data = json.loads(_cedict_path.read_text())

# Load CC-CEDICT words into jieba for better segmentation
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

def _cedict_lookup(word: str) -> Optional[str]:
    """Look up a word in CC-CEDICT dictionary, with particle overrides."""
    if word in _particle_overrides:
        return _particle_overrides[word]
    return _cedict_data.get(word)

SUPPORTED_LANGUAGES = {
    "he": "Hebrew",
    "ja": "Japanese",
    "ko": "Korean",
    "en": "English",
    "zh": "Chinese",
    "el": "Greek",
    "it": "Italian",
    "es": "Spanish",
}

CURATED_SENTENCES = {
    "ja": [
        {"sentence": "ここで働かせてください。", "difficulty": "easy", "category": "anime", "source": "Spirited Away"},
        {"sentence": "君の名は。", "difficulty": "easy", "category": "anime", "source": "Your Name"},
        {"sentence": "諦めたらそこで試合終了ですよ。", "difficulty": "medium", "category": "anime", "source": "Slam Dunk"},
        {"sentence": "お前はもう死んでいる。", "difficulty": "easy", "category": "anime", "source": "Fist of the North Star"},
        {"sentence": "海賊王におれはなる！", "difficulty": "easy", "category": "anime", "source": "One Piece"},
        {"sentence": "生きろ。そなたは美しい。", "difficulty": "medium", "category": "movie", "source": "Princess Mononoke"},
        {"sentence": "まだ会ったことのない君を、探している。", "difficulty": "medium", "category": "anime", "source": "Your Name"},
        {"sentence": "行け。振り向くんじゃない。", "difficulty": "easy", "category": "anime", "source": "Spirited Away"},
        {"sentence": "生きるべきか死ぬべきか、それが問題だ。", "difficulty": "hard", "category": "literature", "source": "Hamlet (Japanese translation)"},
    ],
    "ko": [
        {"sentence": "아들아, 너는 계획이 다 있구나.", "difficulty": "easy", "category": "movie", "source": "Parasite"},
        {"sentence": "가장 완벽한 계획이 뭔지 알아? 무계획이야.", "difficulty": "medium", "category": "movie", "source": "Parasite"},
        {"sentence": "무궁화 꽃이 피었습니다.", "difficulty": "easy", "category": "drama", "source": "Squid Game"},
        {"sentence": "우리는 깐부잖아.", "difficulty": "easy", "category": "drama", "source": "Squid Game"},
        {"sentence": "날이 좋아서, 날이 좋지 않아서, 날이 적당해서 모든 날이 좋았다.", "difficulty": "hard", "category": "drama", "source": "Goblin"},
        {"sentence": "시작이 반이다.", "difficulty": "easy", "category": "proverb", "source": "Korean proverb"},
        {"sentence": "고생 끝에 낙이 온다.", "difficulty": "medium", "category": "proverb", "source": "Korean proverb"},
        {"sentence": "티끌 모아 태산.", "difficulty": "easy", "category": "proverb", "source": "Korean proverb"},
        {"sentence": "묻고 더블로 가!", "difficulty": "medium", "category": "movie", "source": "Tazza: The High Rollers"},
    ],
    "zh": [
        {"sentence": "學而時習之，不亦說乎？", "difficulty": "medium", "category": "literature", "source": "《論語》"},
        {"sentence": "千里之行，始於足下。", "difficulty": "easy", "category": "literature", "source": "《道德經》"},
        {"sentence": "三人行，必有我師焉。", "difficulty": "easy", "category": "literature", "source": "《論語》"},
        {"sentence": "知之為知之，不知為不知，是知也。", "difficulty": "medium", "category": "literature", "source": "《論語》"},
        {"sentence": "天行健，君子以自強不息。", "difficulty": "hard", "category": "literature", "source": "《周易》"},
        {"sentence": "路漫漫其修遠兮，吾將上下而求索。", "difficulty": "hard", "category": "literature", "source": "《離騷》"},
        {"sentence": "海內存知己，天涯若比鄰。", "difficulty": "medium", "category": "literature", "source": "王勃"},
        {"sentence": "失敗為成功之母。", "difficulty": "easy", "category": "proverb", "source": "Chinese saying"},
        {"sentence": "水滴石穿。", "difficulty": "easy", "category": "proverb", "source": "Chinese saying"},
    ],
    "he": [
        {"sentence": "אם אין אני לי, מי לי?", "difficulty": "medium", "category": "literature", "source": "Pirkei Avot"},
        {"sentence": "גם זה יעבור.", "difficulty": "easy", "category": "proverb", "source": "Hebrew saying"},
        {"sentence": "עוד לא אבדה תקוותנו.", "difficulty": "medium", "category": "song", "source": "Hatikvah"},
        {"sentence": "להיות עם חופשי בארצנו.", "difficulty": "easy", "category": "song", "source": "Hatikvah"},
        {"sentence": "ואהבת לרעך כמוך.", "difficulty": "medium", "category": "literature", "source": "Leviticus 19:18"},
        {"sentence": "החיים והמוות ביד הלשון.", "difficulty": "hard", "category": "literature", "source": "Proverbs 18:21"},
        {"sentence": "כל העולם כולו גשר צר מאוד.", "difficulty": "hard", "category": "literature", "source": "Rabbi Nachman"},
        {"sentence": "אין דבר העומד בפני הרצון.", "difficulty": "medium", "category": "proverb", "source": "Hebrew saying"},
        {"sentence": "סוף מעשה במחשבה תחילה.", "difficulty": "medium", "category": "literature", "source": "Lekha Dodi"},
    ],
    "en": [
        {"sentence": "May the Force be with you.", "difficulty": "easy", "category": "movie", "source": "Star Wars"},
        {"sentence": "I'll be back.", "difficulty": "easy", "category": "movie", "source": "The Terminator"},
        {"sentence": "To be, or not to be, that is the question.", "difficulty": "hard", "category": "literature", "source": "Hamlet"},
        {"sentence": "All the world's a stage.", "difficulty": "medium", "category": "literature", "source": "As You Like It"},
        {"sentence": "Here's looking at you, kid.", "difficulty": "easy", "category": "movie", "source": "Casablanca"},
        {"sentence": "Keep your friends close, but your enemies closer.", "difficulty": "medium", "category": "movie", "source": "The Godfather Part II"},
        {"sentence": "Frankly, my dear, I don't give a damn.", "difficulty": "medium", "category": "movie", "source": "Gone with the Wind"},
        {"sentence": "It was the best of times, it was the worst of times.", "difficulty": "hard", "category": "literature", "source": "A Tale of Two Cities"},
        {"sentence": "Not all those who wander are lost.", "difficulty": "medium", "category": "literature", "source": "J.R.R. Tolkien"},
    ],
    "el": [
        {"sentence": "Γνῶθι σεαυτόν.", "difficulty": "easy", "category": "literature", "source": "Delphic maxim"},
        {"sentence": "Ἓν οἶδα ὅτι οὐδὲν οἶδα.", "difficulty": "hard", "category": "literature", "source": "Socrates"},
        {"sentence": "Πάντα ῥεῖ.", "difficulty": "easy", "category": "literature", "source": "Heraclitus"},
        {"sentence": "Μολὼν λαβέ.", "difficulty": "easy", "category": "history", "source": "Leonidas"},
        {"sentence": "Ελευθερία ή θάνατος.", "difficulty": "easy", "category": "history", "source": "Greek motto"},
        {"sentence": "Οὐκ ἐν τῷ πολλῷ τὸ εὖ.", "difficulty": "hard", "category": "proverb", "source": "Ancient Greek saying"},
        {"sentence": "Δεν ελπίζω τίποτα. Δεν φοβάμαι τίποτα. Είμαι λεύτερος.", "difficulty": "hard", "category": "literature", "source": "Nikos Kazantzakis"},
        {"sentence": "Καλύτερα αργά παρά ποτέ.", "difficulty": "easy", "category": "proverb", "source": "Greek proverb"},
        {"sentence": "Η αρχή είναι το ήμισυ του παντός.", "difficulty": "medium", "category": "literature", "source": "Aristotle"},
    ],
    "it": [
        {"sentence": "Nel mezzo del cammin di nostra vita.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Lasciate ogni speranza, voi ch'entrate.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Fatti non foste a viver come bruti.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Amor, ch'a nullo amato amar perdona.", "difficulty": "hard", "category": "literature", "source": "Dante, Inferno"},
        {"sentence": "Buongiorno, principessa!", "difficulty": "easy", "category": "movie", "source": "La vita è bella"},
        {"sentence": "Chi va piano va sano e va lontano.", "difficulty": "easy", "category": "proverb", "source": "Italian proverb"},
        {"sentence": "Finché c'è vita c'è speranza.", "difficulty": "medium", "category": "proverb", "source": "Italian proverb"},
        {"sentence": "La vita è bella.", "difficulty": "easy", "category": "movie", "source": "La vita è bella"},
        {"sentence": "Il fine giustifica i mezzi.", "difficulty": "medium", "category": "literature", "source": "Attributed to Machiavelli"},
    ],
    "es": [
        {"sentence": "En un lugar de La Mancha, de cuyo nombre no quiero acordarme.", "difficulty": "hard", "category": "literature", "source": "Don Quijote"},
        {"sentence": "Caminante, no hay camino, se hace camino al andar.", "difficulty": "medium", "category": "literature", "source": "Antonio Machado"},
        {"sentence": "Más vale tarde que nunca.", "difficulty": "easy", "category": "proverb", "source": "Spanish proverb"},
        {"sentence": "No hay mal que por bien no venga.", "difficulty": "medium", "category": "proverb", "source": "Spanish proverb"},
        {"sentence": "El que madruga, Dios le ayuda.", "difficulty": "easy", "category": "proverb", "source": "Spanish proverb"},
        {"sentence": "Poderoso caballero es don Dinero.", "difficulty": "hard", "category": "literature", "source": "Francisco de Quevedo"},
        {"sentence": "Volverán las oscuras golondrinas.", "difficulty": "medium", "category": "literature", "source": "Gustavo Adolfo Bécquer"},
        {"sentence": "¡Hasta la vista, baby!", "difficulty": "easy", "category": "movie", "source": "Terminator 2"},
        {"sentence": "Quien tiene un amigo, tiene un tesoro.", "difficulty": "easy", "category": "proverb", "source": "Spanish saying"},
    ],
}

STORIES = {
    "spirited-away": {
        "id": "spirited-away",
        "title": "千と千尋の神隠し",
        "source": "Spirited Away",
        "language": "ja",
        "sentences": [
            "ここで働かせてください。",
            "千尋という名は贅沢な名だね。",
            "千だ。今からお前の名前は千だ。",
            "一度あったことは忘れないものさ。思い出せないだけで。",
            "行け。振り向くんじゃない。",
        ],
    },
    "your-name": {
        "id": "your-name",
        "title": "君の名は。",
        "source": "Your Name",
        "language": "ja",
        "sentences": [
            "朝、目が覚めると、なぜか泣いている。",
            "まだ会ったことのない君を、探している。",
            "お前は誰だ？",
            "君の名は。",
            "大事な人。忘れたくない人。忘れちゃダメな人。",
        ],
    },
    "parasite": {
        "id": "parasite",
        "title": "기생충",
        "source": "Parasite",
        "language": "ko",
        "sentences": [
            "아들아, 너는 계획이 다 있구나.",
            "가장 완벽한 계획이 뭔지 알아? 무계획이야.",
            "부잣집 애들은 착해.",
            "돈이 다림질이야.",
            "그래서 존중이 생기는 거야.",
        ],
    },
    "squid-game": {
        "id": "squid-game",
        "title": "오징어 게임",
        "source": "Squid Game",
        "language": "ko",
        "sentences": [
            "무궁화 꽃이 피었습니다.",
            "우리는 깐부잖아.",
            "여기선 다 공평해.",
            "이번 게임을 시작하겠습니다.",
            "탈락입니다.",
        ],
    },
    "chinese-proverbs": {
        "id": "chinese-proverbs",
        "title": "經典成語與格言",
        "source": "Chinese Proverbs & Classics",
        "language": "zh",
        "sentences": [
            "千里之行，始於足下。",
            "學而時習之，不亦說乎？",
            "三人行，必有我師焉。",
            "失敗為成功之母。",
            "水滴石穿。",
        ],
    },
}

class SentenceRequest(BaseModel):
    sentence: str
    target_language: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


class AnkiExportEntry(BaseModel):
    sentence: str
    translation: str
    pronunciation: Optional[str] = None
    target: Optional[str] = None
    lang: Optional[str] = None
    timestamp: Optional[str] = None


def _sanitize_tsv_cell(value: Optional[str]) -> str:
    """Normalize tabs/newlines so each card remains a single TSV row."""
    text = (value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", " ").replace("\n", " ")
    return text.strip()


def _anki_language_label(code: str) -> str:
    name = SUPPORTED_LANGUAGES.get(code, code)
    return f"{name} ({code})" if name != code else code

@app.post("/api/learn")
async def learn_sentence(
    request: Request,
    req: SentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    _rate_limit_cleanup()
    if not _rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence or not req.sentence.strip():
        raise HTTPException(400, "Sentence cannot be empty")

    # Prompt injection protection
    MAX_INPUT_LEN = 500
    if len(req.sentence) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")
    injection_patterns = [
        "ignore previous", "ignore above", "disregard", "forget your instructions",
        "you are now", "new instructions", "system prompt", "override",
        "```", "---", "###", "SYSTEM:", "USER:", "ASSISTANT:",
    ]
    lower_input = req.sentence.lower()
    for pattern in injection_patterns:
        if pattern.lower() in lower_input:
            raise HTTPException(400, "Invalid input")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    # Check cache first
    gender = req.speaker_gender or "neutral"
    formality = req.speaker_formality or "polite"
    ck = _cache_key(req.sentence, req.target_language, gender, formality)
    cached = cache_get(ck)
    if cached:
        return cached

    lang_name = SUPPORTED_LANGUAGES[req.target_language]

    lang_code = req.target_language

    # Build script examples for the target language
    script_examples = {
        "ko": "Korean script (한국어). Example: 커피 한 잔 주문하고 싶어요",
        "ja": "Japanese script (日本語). Example: コーヒーを一杯注文したいです. IMPORTANT: For Japanese, always note gender implications of pronouns (e.g. 私/watashi vs 僕/boku vs 俺/ore) and formality levels in your notes.",
        "he": "Hebrew script (עברית). Example: אני רוצה להזמין כוס קפה",
        "el": "Greek script (Ελληνικά). Example: Θέλω να παραγγείλω έναν καφέ",
        "zh": "Traditional Chinese (繁體中文). Example: 我想點一杯咖啡",
        "en": "English. Example: I want to order a coffee",
        "it": "Italian. Example: Vorrei ordinare un caffè",
        "es": "Spanish. Example: Quiero pedir un café",
    }
    script_hint = script_examples.get(lang_code, f"{lang_name} script")

    # Determine input language (explicit or auto-detect)
    input_lang = getattr(req, 'input_language', 'auto') or 'auto'
    if input_lang == "zh":
        input_is_chinese = True
    elif input_lang == "en":
        input_is_chinese = False
    else:  # auto-detect
        input_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.sentence)

    # Detect source language
    source_lang = "Traditional Chinese (繁體中文, 台灣用法)" if input_is_chinese else "English"
    source_lang_short = "繁體中文" if input_is_chinese else "English"

    prompt = f"""TASK: Translate this sentence into {lang_name} and break it down.

TARGET LANGUAGE: {lang_name} — {script_hint}
SOURCE LANGUAGE (what the user typed in): {source_lang}

INPUT: "{req.sentence}"

IMPORTANT: The input may contain mixed languages (e.g. Chinese + English words). Understand the MEANING of the entire sentence, then translate the WHOLE MEANING into {lang_name}. Do NOT keep any source language words in the translation.

You MUST translate into {lang_name}. For example, if target is Korean, write 한국어. If Japanese, write 日本語. If Hebrew, write עברית. Do NOT output Chinese unless the target language IS Chinese. Do NOT echo back the input sentence as the translation.

CRITICAL RULES:
1. The "translation" field MUST be written in {lang_name} using {script_hint}. NOT Chinese, NOT English (unless target IS English).
2. The "word" fields in breakdown MUST be {lang_name} words in {lang_name} script.
3. ALL "meaning" fields MUST be in {source_lang_short}. ALL "grammar_notes" MUST be in {source_lang_short}. ALL "cultural_note" and "note" fields MUST be in {source_lang_short}. The user reads {source_lang_short}, so write ALL explanations in {source_lang_short}. NEVER write explanations in Chinese if the source is English. NEVER write explanations in English if the source is Chinese.
4. When writing ANY Chinese text, use ONLY Traditional Chinese (繁體中文) with Taiwan usage. NEVER Simplified Chinese.
5. Do NOT mix languages. Explanations in one language only.

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "translation": "DIRECT translation — stay close to the structure and meaning of the input sentence. Translate faithfully in {lang_name} script (e.g. for Korean use 한글, for Japanese use 日本語, etc.)",
  "pronunciation": "FULL romanized pronunciation of the translation using standard systems: Japanese=Hepburn romaji (e.g. oshiete kudasai, NOT OLLOW-te), Chinese=pinyin with tones, Korean=Revised Romanization, Hebrew=standard transliteration, Greek=standard transliteration",
  "literal": "word-by-word literal translation back to the detected source language",
  "breakdown": [
    {{
      "word": "each word/particle EXACTLY as it appears in the translation above — do NOT invent words that aren't in the translation. Split naturally (e.g. for Chinese: 我/練得越多/越/覺得/自信, NOT 越自信 if the sentence says 越覺得自信). For grammar patterns like 越...越..., show each 越 with its attached word separately.",
      "pronunciation": "romanized pronunciation (Japanese: Hepburn romaji like 'kudasai', NOT made-up spellings)",
      "meaning": "meaning in {source_lang_short} ONLY",
      "difficulty": "easy|medium|hard",
      "note": "brief grammar/usage note in {source_lang_short} ONLY, otherwise null. NEVER write notes in {lang_name} when source is {source_lang_short}."
    }}
  ],
  "grammar_notes": [
    "Key grammar pattern or structure explanation (1-3 short notes). MUST be written in {source_lang_short}. NEVER in {lang_name} unless {lang_name} IS {source_lang_short}."
  ],
  "cultural_note": "optional cultural context or usage tip (in the detected source language), null if none",
  "formality": "casual|polite|formal — what register this translation uses",
  "alternative": "an alternative way to say this (different formality or phrasing), or null",
  "native_expression": "ALWAYS provide this. This is how a native {lang_name} speaker would NATURALLY rephrase this — more colloquial, idiomatic, or restructured compared to the direct translation above. Format: 'native sentence | FULL PRONUNCIATION | EXPLANATION IN {source_lang_short}'. Example for Chinese: '這咖啡也太好喝了吧 | zhè kāfēi yě tài hǎo hē le ba | Uses 也太...了吧 (yě tài...le ba), a common exclamation pattern meaning \"this is way too [good]\"'. When mentioning {lang_name} words in the explanation, always add pronunciation and meaning in parentheses. CRITICAL: The native expression must preserve the SAME MEANING as the input. Do NOT change key concepts (e.g. if the input says 'confident', the native expression must also be about confidence, NOT progress or something else). You can change structure, formality, and phrasing, but the core meaning must stay the same. If the native expression uses different vocabulary, explain WHY in the explanation. Only null if the direct translation is already exactly how a native would say it."
}}"""

    # Inject speaker identity
    speaker_block = f"""
SPEAKER IDENTITY:
- Gender: {gender} — adjust pronouns, gendered words accordingly. For Japanese: use 僕/俺 for male, あたし for female, 私 for neutral. For Hebrew: adjust verb conjugation, adjectives, pronouns. For Spanish/Italian: adjust adjective agreement.
- Formality: {formality} — use appropriate register. For Korean: casual=반말, polite=존댓말, formal=격식체. For Japanese: casual=タメ口, polite=です/ます, formal=敬語. For Chinese: casual=street/口語 (e.g. 老闆買單, 我要吃拉麵), polite=standard (e.g. 請問可以結帳嗎), formal=written/公文. IMPORTANT: If casual, translate like how a young Taiwanese person would actually say it in daily life — short, direct, colloquial. Do NOT use 請問/可以...嗎 patterns for casual speech.
The "formality" field in the response MUST be "{formality}".
"""
    prompt = prompt + "\n" + speaker_block

    # Always use qwen2.5 for structured JSON (TAIDE can't reliably produce JSON)
    model = OLLAMA_MODEL

    taiwan_chinese_rules = """
TAIWAN CHINESE RULES (apply when target is Chinese or explanations are in Chinese):
- Use ONLY Traditional Chinese (繁體中文) with Taiwan usage (台灣用法)
- NEVER use mainland China phrasing. Use Taiwanese daily speech patterns.
- Examples of correct Taiwan vs incorrect mainland usage:
  - ✅ 跟我說一個笑話 / ❌ 給我講一個笑話
  - ✅ 講個笑話給我聽 / ❌ 給我講個笑話
  - ✅ 好棒 / ❌ 真棒
  - ✅ 沒問題 / ❌ 沒事兒
  - ✅ 很厲害 / ❌ 牛逼
  - ✅ 軟體 / ❌ 軟件
  - ✅ 資訊 / ❌ 信息
  - ✅ 影片 / ❌ 視頻
  - ✅ 計程車 / ❌ 出租車
  - ✅ 捷運 / ❌ 地鐵
  - ✅ 腳踏車 / ❌ 自行車
"""

    explanation_lang_instruction = f"CRITICAL: ALL explanations (meaning, grammar_notes, note, cultural_note) MUST be written in {source_lang_short}. Do NOT write explanations in any other language."

    if lang_code == "zh":
        casual_hint = ""
        if formality == "casual":
            casual_hint = "口語程度：口語/街頭用法。像台灣年輕人跟朋友或在小吃店講話一樣。例：'Can I get the bill?' → '老闆，買單！'，不要用'請問可以開帳單嗎'。簡短、直接、自然。"
        elif formality == "formal":
            casual_hint = "口語程度：正式/書面用法。使用敬語和完整句型。"
        else:
            casual_hint = "口語程度：禮貌/標準用法。"
        system_msg = f"你是一位台灣華語教師，專門教外國人學繁體中文（台灣用法）。翻譯必須完全使用繁體中文，絕對不可以使用簡體字或大陸用語。{casual_hint} 重要：翻譯中不可以夾雜任何英文單字（例如 menu 要翻成「菜單」，bill 要翻成「帳單」）。{explanation_lang_instruction} 請只回傳有效的 JSON 格式。\n{taiwan_chinese_rules}"
    elif input_is_chinese and lang_code == "en":
        system_msg = f"You are an English language teacher helping Chinese speakers learn English. The user writes in Chinese and you translate into ENGLISH. The 'translation' field MUST be in English. The 'pronunciation' field should be English pronunciation guide. The 'word' fields in breakdown MUST be English words. {explanation_lang_instruction} The 'native_expression' field should show how a native English speaker would naturally say it in English, with 繁體中文 explanation. Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    elif input_is_chinese:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. {explanation_lang_instruction} Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    else:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. {explanation_lang_instruction} Always respond with valid JSON only."

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2048},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")

    data = resp.json()
    text = data.get("message", {}).get("content", "")

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                raise HTTPException(502, f"Failed to parse LLM response: {text[:300]}")
        else:
            raise HTTPException(502, f"Failed to parse LLM response: {text[:300]}")

    # Validation: check if translation is just echoing back the input
    translation_text = result.get("translation", "")
    input_clean = req.sentence.strip().replace(" ", "")
    trans_clean = translation_text.strip().replace(" ", "")
    if lang_code not in ("zh", "en") and input_is_chinese and trans_clean and input_clean:
        # If translation is mostly CJK and looks like input was echoed back
        cjk_ratio = sum(1 for c in trans_clean if '\u4e00' <= c <= '\u9fff') / max(len(trans_clean), 1)
        if cjk_ratio > 0.5 and lang_code in ("ja",):
            # For Japanese, CJK is normal (kanji), but check if it's identical to input
            if trans_clean == input_clean or input_clean in trans_clean:
                result["_warning"] = "Translation may be echoing input. Model struggled with this input."
        elif cjk_ratio > 0.5 and lang_code not in ("ja", "zh"):
            result["_warning"] = "Translation may be in the wrong language."

    # Post-process: detect English words leaking into Chinese translations
    if lang_code == "zh" and translation_text:
        import re
        english_words = re.findall(r'[a-zA-Z]{2,}', translation_text)
        if english_words:
            # Common English-to-Chinese replacements
            en_to_zh = {
                'menu': '菜單', 'bill': '帳單', 'coffee': '咖啡', 'beer': '啤酒',
                'ok': '好', 'sorry': '抱歉', 'thanks': '謝謝', 'thank': '謝',
                'taxi': '計程車', 'bus': '公車', 'hotel': '旅館', 'wifi': '無線網路',
                'email': '電子郵件', 'phone': '手機', 'app': '應用程式',
                'restaurant': '餐廳', 'bar': '酒吧', 'shop': '商店',
            }
            fixed = translation_text
            for word in english_words:
                replacement = en_to_zh.get(word.lower())
                if replacement:
                    fixed = fixed.replace(word, replacement)
            if fixed != translation_text:
                result["translation"] = fixed
                translation_text = fixed

    # Two-pass: TAIDE taiwanification for Chinese translations
    if lang_code == "zh" and translation_text:
        try:
            taide_prompt = f"""請把以下中文改成道地的台灣繁體中文（台灣口語用法）。只需要回傳修改後的句子，不要加任何解釋。如果已經是台灣用法就原樣回傳。
{casual_hint}

原文：{translation_text}
台灣用法："""
            taide_resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={"model": TAIDE_MODEL, "messages": [{"role": "user", "content": taide_prompt}], "stream": False, "options": {"temperature": 0.3, "num_predict": 200}},
                timeout=30
            )
            if taide_resp.ok:
                taide_text = taide_resp.json().get("message", {}).get("content", "").strip()
                # Only use if it's pure Chinese (no English, no JSON, reasonable length)
                if taide_text and len(taide_text) < len(translation_text) * 3 and not taide_text.startswith("{"):
                    import re as _re
                    if not _re.search(r'[a-zA-Z]{3,}', taide_text):
                        # Clean up: remove quotes, trailing punctuation artifacts
                        taide_text = taide_text.strip('"\'').strip()
                        if taide_text:
                            result["translation"] = taide_text
                            translation_text = taide_text
        except Exception:
            pass  # Fall back to qwen output

    # Post-process: override LLM pronunciation with deterministic libraries
    det_pron = deterministic_pronunciation(translation_text, lang_code)
    if det_pron:
        result["pronunciation"] = det_pron

    # Override per-word pronunciation in breakdown
    breakdown = result.get("breakdown", [])
    for item in breakdown:
        word = item.get("word", "")
        word_pron = deterministic_word_pronunciation(word, lang_code)
        if word_pron:
            item["pronunciation"] = word_pron

    # Re-segment Chinese breakdowns if they're character-by-character
    if lang_code == "zh" and breakdown and translation_text:
        avg_word_len = sum(len(item.get("word", "")) for item in breakdown) / max(len(breakdown), 1)
        if avg_word_len <= 1.2 and len(breakdown) > 3:
            # Model split character-by-character — re-segment with jieba
            import jieba
            words = list(jieba.cut(translation_text.replace("，", "").replace("。", "").replace("！", "").replace("？", "")))
            words = [w.strip() for w in words if w.strip()]
            new_breakdown = []
            for w in words:
                pron = deterministic_word_pronunciation(w, lang_code) or ""
                new_breakdown.append({
                    "word": w,
                    "pronunciation": pron,
                    "meaning": "",  # Will be filled by model on next pass or left for user
                    "difficulty": "medium",
                    "note": None
                })
            # Look up meanings from CC-CEDICT (120k+ entries)
            for item in new_breakdown:
                w = item["word"]
                meaning = _cedict_lookup(w)
                if meaning:
                    item["meaning"] = meaning
                else:
                    # Try constituent characters
                    chars = [_cedict_lookup(c) or "" for c in w]
                    combined = " + ".join(c for c in chars if c)
                    item["meaning"] = combined if combined else w
            breakdown = new_breakdown
            result["breakdown"] = breakdown

    # Filter out hallucinated breakdown words not in the translation
    if breakdown and translation_text:
        clean_translation = translation_text.replace(" ", "").replace("，", "").replace(",", "").replace("。", "").replace(".", "").replace("！", "").replace("!", "").replace("？", "").replace("?", "")
        filtered = []
        for item in breakdown:
            word = item.get("word", "").strip()
            if not word:
                continue
            # Check if the word actually appears in the translation
            word_clean = word.replace(" ", "")
            if word_clean in clean_translation:
                filtered.append(item)
            # else: hallucinated word, skip it
        result["breakdown"] = filtered

    # Post-process: Japanese gender/pronoun warnings
    if lang_code == "ja" and translation_text:
        gender_markers = {
            "私": ("watashi", "neutral/formal, used by all genders"),
            "僕": ("boku", "masculine, casual — used by boys/men"),
            "俺": ("ore", "masculine, very casual/rough — used by men"),
            "あたし": ("atashi", "feminine, casual — used by women/girls"),
            "わたくし": ("watakushi", "very formal, gender-neutral"),
        }
        detected = []
        for marker, (reading, desc) in gender_markers.items():
            if marker in translation_text:
                detected.append(f"⚠️ '{marker}' ({reading}): {desc}")
        if detected:
            gender_note = " | ".join(detected)
            existing_notes = result.get("grammar_notes", []) or []
            existing_notes.insert(0, f"Gender/formality note: {gender_note}")
            result["grammar_notes"] = existing_notes

    # Post-process: fix native_expression pronunciation and check for duplicates
    native = result.get("native_expression")
    translation = result.get("translation", "")
    if native and "|" in native:
        parts = native.split("|", 2)
        if len(parts) >= 3:
            native_sentence = parts[0].strip()
            native_explanation = parts[2].strip()
            # Fix explanation language: if input is English but explanation is Chinese, translate it
            if not input_is_chinese and native_explanation:
                cjk_count = sum(1 for c in native_explanation if '\u4e00' <= c <= '\u9fff')
                if cjk_count > len(native_explanation) * 0.3:
                    # Explanation is mostly Chinese — ask qwen to translate
                    try:
                        fix_resp = requests.post(
                            f"{OLLAMA_URL}/api/chat",
                            json={"model": OLLAMA_MODEL, "messages": [
                                {"role": "user", "content": f"Translate this Chinese explanation to English. Only output the English translation:\n{native_explanation}"}
                            ], "stream": False, "options": {"temperature": 0.1, "num_predict": 100}},
                            timeout=15
                        )
                        if fix_resp.ok:
                            fixed_expl = fix_resp.json().get("message", {}).get("content", "").strip()
                            if fixed_expl and len(fixed_expl) < 200:
                                native_explanation = fixed_expl
                    except Exception:
                        pass
            # Generate correct pronunciation using deterministic lib
            native_pron = deterministic_pronunciation(native_sentence, lang_code)
            if native_pron:
                result["native_expression"] = f"{native_sentence} | {native_pron} | {native_explanation}"
    elif native and translation:
        native_core = native.split("(")[0].strip().rstrip("。.!！")
        trans_core = translation.strip().rstrip("。.!！")
        if native_core == trans_core:
            result["native_expression"] = None

    # Dataset-based Taiwanese native phrases (keyword matching)
    if lang_code == "zh":
        try:
            phrases_file = Path(__file__).parent / "taiwanese_phrases.json"
            if phrases_file.exists():
                tw_data = json.loads(phrases_file.read_text())
                input_lower = req.sentence.lower()
                trans_text = translation_text or ""
                matches = []
                for p in tw_data.get("phrases", []):
                    score = sum(1 for kw in p["keywords"] if kw.lower() in input_lower or kw in trans_text)
                    if score > 0:
                        matches.append((score, p))
                matches.sort(key=lambda x: -x[0])
                # Add top 2 matches as "tw_native_phrases"
                if matches:
                    top = matches[:2]
                    result["tw_native_phrases"] = [
                        {"phrase": m[1]["phrase"], "pinyin": m[1]["pinyin"], "meaning": m[1]["meaning"], "context": m[1].get("context", "")}
                        for m in top
                    ]
        except Exception:
            pass

    # Post-process: enforce explanations in source language
    if not input_is_chinese:
        # When input is English, grammar_notes and meanings must be in English
        # Strip Chinese-only content; if a note is mostly Chinese, re-wrap it
        def _mostly_cjk(s):
            if not s:
                return False
            cjk = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
            return cjk / max(len(s.replace(" ", "")), 1) > 0.3

        notes = result.get("grammar_notes", []) or []
        cleaned_notes = []
        for note in notes:
            if not _mostly_cjk(note):
                cleaned_notes.append(note)
            else:
                # Try to salvage English content from the note
                import re as _re_notes
                salvaged = _re_notes.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]+', '', note).strip()
                # Clean up leftover punctuation/parens
                salvaged = _re_notes.sub(r'\s+', ' ', salvaged).strip(' ()-:,.')
                if len(salvaged) > 15:  # Only keep if there's enough English content
                    cleaned_notes.append(salvaged)
        result["grammar_notes"] = cleaned_notes

        # If all grammar notes were dropped, generate a minimal fallback
        if not cleaned_notes and notes:
            target = result.get("translation", "")
            if target:
                result["grammar_notes"] = [f"Note: The original grammar notes were in the target language. Review the breakdown for word-by-word details."]

        for item in result.get("breakdown", []):
            meaning = item.get("meaning", "")
            # Strip any CJK characters from meanings when source is English
            # e.g. "一杯 (a cup of)" → "a cup of"
            if any('\u4e00' <= c <= '\u9fff' for c in meaning):
                import re as _re2
                # Remove CJK chars and clean up
                cleaned = _re2.sub(r'[\u4e00-\u9fff]+', '', meaning).strip()
                # Remove leading/trailing parens and whitespace
                cleaned = _re2.sub(r'^\(?\s*', '', cleaned)
                cleaned = _re2.sub(r'\s*\)?\s*$', '', cleaned)
                if cleaned:
                    item["meaning"] = cleaned

    # Ensure all Chinese text is Traditional Chinese (Taiwan)
    result = ensure_traditional_chinese(result)

    # Cache the result
    cache_put(ck, result)

    return result


# --- Multi-sentence splitter ---

def _split_sentences(text: str) -> List[str]:
    """Split text into individual sentences on common terminators."""
    # Split on sentence-ending punctuation followed by space or end
    parts = _re.split(r'(?<=[.!?。！？])\s*', text.strip())
    # Filter empty strings, strip whitespace
    return [s.strip() for s in parts if s.strip()]


class MultiSentenceRequest(BaseModel):
    sentences: str  # raw paragraph text
    target_language: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


class QuizCheckRequest(BaseModel):
    quiz_id: str
    answer: str
    target_language: str


@app.post("/api/learn-multi")
async def learn_multi(
    request: Request,
    req: MultiSentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    """Split input into sentences and translate each one."""
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    parts = _split_sentences(req.sentences)
    if not parts:
        raise HTTPException(400, "No sentences detected")

    if len(parts) == 1:
        # Single sentence — delegate to normal endpoint
        single_req = SentenceRequest(
            sentence=parts[0],
            target_language=req.target_language,
            speaker_gender=req.speaker_gender,
            speaker_formality=req.speaker_formality,
        )
        result = await learn_sentence(request, single_req, x_app_password)
        return {"mode": "single", "results": [{"sentence": parts[0], "result": result}]}

    # Multiple sentences — process sequentially (respects rate limits)
    results = []
    for sentence in parts[:10]:  # cap at 10 sentences
        single_req = SentenceRequest(
            sentence=sentence,
            target_language=req.target_language,
            speaker_gender=req.speaker_gender,
            speaker_formality=req.speaker_formality,
        )
        try:
            result = await learn_sentence(request, single_req, x_app_password)
            results.append({"sentence": sentence, "result": result})
        except HTTPException as e:
            results.append({"sentence": sentence, "error": e.detail})

    return {"mode": "multi", "results": results}


class WordDetailRequest(BaseModel):
    word: str
    meaning: str
    target_language: str
    sentence_context: Optional[str] = None

@app.post("/api/word-detail")
async def word_detail(
    request: Request,
    req: WordDetailRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    _rate_limit_cleanup()
    if not _rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[req.target_language]

    # Detect if meaning is Chinese
    meaning_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.meaning)
    explain_lang = "繁體中文 (Traditional Chinese, Taiwan usage)" if meaning_is_chinese else "English"

    context_line = f'\nThe word appeared in this sentence: "{req.sentence_context}"' if req.sentence_context else ""

    prompt = f"""Give details about the {lang_name} word "{req.word}" (meaning: {req.meaning}).{context_line}

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "examples": [
    {{"sentence": "example sentence using the word in {lang_name}", "pronunciation": "romanized", "meaning": "translation in {explain_lang}"}},
    {{"sentence": "another example", "pronunciation": "romanized", "meaning": "translation in {explain_lang}"}}
  ],
  "conjugations": [
    {{"form": "conjugated/inflected form in {lang_name}", "label": "tense/form name in {explain_lang}"}}
  ],
  "related": [
    {{"word": "related word in {lang_name}", "meaning": "meaning in {explain_lang}"}}
  ]
}}

Rules:
- Give 2-3 example sentences, 2-4 conjugations/forms (if applicable), 2-3 related words
- If the word doesn't conjugate (particles, nouns), return empty conjugations array
- All explanations in {explain_lang}
- Examples should be simple, practical sentences"""

    system_msg = f"You are a {lang_name} vocabulary teacher. Respond with valid JSON only."

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1024},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")

    data = resp.json()
    text = data.get("message", {}).get("content", "")

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
            except json.JSONDecodeError:
                return {"examples": [], "conjugations": [], "related": []}
        else:
            return {"examples": [], "conjugations": [], "related": []}

    result = ensure_traditional_chinese(result)
    return result

@app.get("/api/languages")
async def get_languages():
    return SUPPORTED_LANGUAGES


@app.post("/api/export-anki")
async def export_anki(
    entries: List[AnkiExportEntry],
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    rows: List[str] = []
    for entry in entries:
        front = _sanitize_tsv_cell(entry.sentence)
        if not front:
            continue

        translation = _sanitize_tsv_cell(entry.translation)
        pronunciation = _sanitize_tsv_cell(entry.pronunciation)
        lang_code = (entry.target or entry.lang or "").strip()

        back_parts: List[str] = []
        if translation:
            back_parts.append(translation)
        if pronunciation:
            back_parts.append(f"Pronunciation: {pronunciation}")
        if lang_code:
            back_parts.append(f"Language: {_anki_language_label(lang_code)}")

        back = _sanitize_tsv_cell("<br>".join(back_parts))
        rows.append(f"{front}\t{back}")

    content = "\n".join(rows)
    headers = {"Content-Disposition": 'attachment; filename="sent-say-flashcards.txt"'}
    return Response(content=content, media_type="text/tab-separated-values", headers=headers)

SURPRISE_SENTENCES_EN = [
    {"sentence": "I want to eat ramen for dinner tonight", "difficulty": "easy", "category": "daily life"},
    {"sentence": "Where is the nearest train station?", "difficulty": "easy", "category": "travel"},
    {"sentence": "This coffee tastes absolutely amazing", "difficulty": "easy", "category": "food"},
    {"sentence": "Could you please speak a little slower?", "difficulty": "easy", "category": "travel"},
    {"sentence": "I've been studying this language for three months", "difficulty": "medium", "category": "learning"},
    {"sentence": "The sunset over the ocean was breathtaking", "difficulty": "medium", "category": "nature"},
    {"sentence": "I'm sorry, I don't understand what you're saying", "difficulty": "easy", "category": "travel"},
    {"sentence": "Let's grab a beer after work", "difficulty": "easy", "category": "social"},
    {"sentence": "I need to wake up early tomorrow morning", "difficulty": "easy", "category": "daily life"},
    {"sentence": "What do you recommend from the menu?", "difficulty": "easy", "category": "food"},
    {"sentence": "I've been meaning to tell you something important", "difficulty": "medium", "category": "social"},
    {"sentence": "The more I practice, the more confident I feel", "difficulty": "medium", "category": "learning"},
    {"sentence": "Can I get the bill please?", "difficulty": "easy", "category": "travel"},
    {"sentence": "I think we're lost, let me check the map", "difficulty": "medium", "category": "travel"},
    {"sentence": "If I had known earlier, I would have come sooner", "difficulty": "hard", "category": "grammar"},
]

SURPRISE_SENTENCES_ZH = [
    {"sentence": "今天晚上我想吃拉麵", "difficulty": "easy", "category": "日常生活"},
    {"sentence": "請問最近的捷運站在哪裡？", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "這杯咖啡真的超好喝", "difficulty": "easy", "category": "美食"},
    {"sentence": "你可以講慢一點嗎？", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "我學這個語言已經三個月了", "difficulty": "medium", "category": "學習"},
    {"sentence": "海邊的夕陽真的美到不行", "difficulty": "medium", "category": "自然"},
    {"sentence": "不好意思，我聽不懂你在說什麼", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "下班之後一起去喝一杯吧", "difficulty": "easy", "category": "社交"},
    {"sentence": "我明天早上要早起", "difficulty": "easy", "category": "日常生活"},
    {"sentence": "你們推薦菜單上的什麼？", "difficulty": "easy", "category": "美食"},
    {"sentence": "我一直想跟你說一件很重要的事", "difficulty": "medium", "category": "社交"},
    {"sentence": "越練習就越有自信", "difficulty": "medium", "category": "學習"},
    {"sentence": "可以幫我結帳嗎？", "difficulty": "easy", "category": "旅遊"},
    {"sentence": "我覺得我們迷路了，讓我看一下地圖", "difficulty": "medium", "category": "旅遊"},
    {"sentence": "如果我早點知道的話，我就會早點來", "difficulty": "hard", "category": "文法"},
]

@app.get("/api/surprise")
async def get_surprise_sentence(lang: str, input_lang: str = "en"):
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    pool = SURPRISE_SENTENCES_ZH if input_lang == "zh" else SURPRISE_SENTENCES_EN
    picked = random.choice(pool)
    return {
        "language": lang,
        "sentence": picked["sentence"],
        "difficulty": picked["difficulty"],
        "category": picked["category"],
    }


class QuizHistoryItem(BaseModel):
    sentence: str
    translation: str
    pronunciation: Optional[str] = None

class QuizFromHistoryRequest(BaseModel):
    history: List[QuizHistoryItem]

@app.api_route("/api/quiz", methods=["GET", "POST"])
async def get_quiz(
    request: Request,
    lang: str,
    gender: str = "neutral",
    formality: str = "polite",
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[lang]

    # Try to use user's history for quiz
    history_items = []
    if request.method == "POST":
        try:
            body = await request.json()
            history_items = body.get("history", [])
        except Exception:
            pass

    if history_items:
        picked = random.choice(history_items)
        sentence = picked["translation"]
        source_sentence = picked["sentence"]
        pronunciation = picked.get("pronunciation", "")
        quiz_id = _new_quiz_id(lang, sentence)
        _cleanup_quiz_answers()
        _quiz_answers[quiz_id] = {
            "answer_en": source_sentence,
            "answer_zh": source_sentence,
            "sentence": sentence,
            "created_at": time.time(),
        }
        return {
            "quiz_id": quiz_id,
            "sentence": sentence,
            "pronunciation": pronunciation,
            "source": "Your history",
            "hint": source_sentence[:3] + "..." if len(source_sentence) > 3 else source_sentence,
            "language": lang,
        }

    # Fallback to curated sentences
    sentence_pool = CURATED_SENTENCES.get(lang, [])
    if not sentence_pool:
        raise HTTPException(404, "No curated sentences found for this language")

    picked = random.choice(sentence_pool)
    sentence = picked["sentence"]

    prompt = f"""Translate this {lang_name} sentence into both English and Traditional Chinese (Taiwan usage).

Sentence: "{sentence}"
Context:
- Speaker gender: {gender}
- Formality: {formality}

Return ONLY valid JSON:
{{
  "translation_en": "Natural English meaning",
  "translation_zh": "Natural Traditional Chinese meaning (Taiwan usage)"
}}"""

    system_msg = "You are a translation assistant. Return valid JSON only."

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 256},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")

    content = resp.json().get("message", {}).get("content", "")
    parsed = _parse_json_object(content) or {}

    translation_en = (parsed.get("translation_en") or "").strip()
    translation_zh = (parsed.get("translation_zh") or "").strip()

    if not translation_en and not translation_zh:
        raise HTTPException(502, "Failed to generate quiz answer")
    if not translation_en:
        translation_en = translation_zh
    if not translation_zh:
        translation_zh = translation_en

    quiz_id = _new_quiz_id(lang, sentence)
    _cleanup_quiz_answers()
    _quiz_answers[quiz_id] = {
        "created_at": time.time(),
        "sentence": sentence,
        "language": lang,
        "source": picked.get("source", ""),
        "answer_en": translation_en,
        "answer_zh": translation_zh,
    }

    return {
        "quiz_id": quiz_id,
        "sentence": sentence,
        "source": picked.get("source", ""),
        "language": lang,
        "hint": _translation_hint(translation_en),
        "pronunciation": deterministic_pronunciation(sentence, lang),
    }


@app.post("/api/quiz-check")
async def quiz_check(
    request: Request,
    req: QuizCheckRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    _rate_limit_cleanup()
    if not _rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    answer = req.answer.strip()
    if not answer:
        raise HTTPException(400, "Answer is required")

    _cleanup_quiz_answers()
    quiz = _quiz_answers.get(req.quiz_id)
    if not quiz:
        raise HTTPException(404, "Quiz not found or expired")

    if req.target_language != quiz.get("language"):
        raise HTTPException(400, "Quiz language mismatch")

    lang_name = SUPPORTED_LANGUAGES.get(quiz["language"], quiz["language"])

    prompt = f"""Evaluate whether the learner answer captures the MEANING of the target sentence.
Do not require exact wording.

Target sentence ({lang_name}): "{quiz['sentence']}"
Reference English meaning: "{quiz['answer_en']}"
Reference Traditional Chinese meaning: "{quiz['answer_zh']}"
Learner answer: "{answer}"

Scoring rubric:
- perfect: meaning is fully accurate and complete
- good: meaning is correct with minor wording differences
- partial: some meaning is correct but key details are missing or off
- wrong: meaning is mostly incorrect

Return JSON only in this format:
{{"score": "perfect|good|partial|wrong", "feedback": "brief explanation"}}"""

    system_msg = (
        "You are a translation quiz grader. Grade semantic equivalence only. "
        "Return strict JSON only."
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 196},
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"LLM API error: {resp.status_code}")

    content = resp.json().get("message", {}).get("content", "")
    parsed = _parse_json_object(content) or {}

    score = str(parsed.get("score", "")).strip().lower()
    if score not in {"perfect", "good", "partial", "wrong"}:
        score = "wrong"
    feedback = str(parsed.get("feedback", "")).strip() or "Meaning does not match closely enough."

    answer_en = quiz.get("answer_en", "").strip()
    answer_zh = quiz.get("answer_zh", "").strip()
    if answer_en and answer_zh and answer_zh != answer_en:
        correct_answer = f"{answer_en} / {answer_zh}"
    else:
        correct_answer = answer_en or answer_zh

    return {
        "correct": score in {"perfect", "good"},
        "score": score,
        "correct_answer": correct_answer,
        "feedback": feedback,
    }


class CompareRequest(BaseModel):
    sentence: str
    input_language: Optional[str] = "auto"
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None


@app.post("/api/compare")
async def compare_sentence(
    request: Request,
    req: CompareRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    """Translate one sentence into ALL supported languages side by side."""
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    client_ip = request.client.host if request.client else "unknown"
    _rate_limit_cleanup()
    if not _rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence.strip():
        raise HTTPException(400, "Sentence is required")

    gender = req.speaker_gender or "neutral"
    formality = req.speaker_formality or "polite"

    # Detect input language to exclude it from targets
    input_lang = req.input_language or "auto"
    if input_lang == "zh":
        input_is_chinese = True
    elif input_lang == "en":
        input_is_chinese = False
    else:
        input_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.sentence)

    # Determine which languages to skip (don't translate to the source language)
    skip_langs = set()
    if input_is_chinese:
        skip_langs.add("zh")
    else:
        skip_langs.add("en")

    target_langs = [code for code in SUPPORTED_LANGUAGES if code not in skip_langs]

    # Translate to each language sequentially (reuses learn_sentence with caching)
    results = []
    for lang_code in target_langs:
        single_req = SentenceRequest(
            sentence=req.sentence,
            target_language=lang_code,
            input_language=req.input_language,
            speaker_gender=req.speaker_gender,
            speaker_formality=req.speaker_formality,
        )
        try:
            result = await learn_sentence(request, single_req, x_app_password)
            # Handle both dict and Response objects
            if hasattr(result, 'body'):
                import json as _json
                result = _json.loads(result.body)
            results.append({
                "language": lang_code,
                "language_name": SUPPORTED_LANGUAGES[lang_code],
                "translation": result.get("translation", ""),
                "pronunciation": result.get("pronunciation", ""),
                "formality": result.get("formality", ""),
                "literal": result.get("literal", ""),
            })
        except HTTPException as e:
            if e.status_code == 429:
                # Stop if rate limited
                break
            results.append({
                "language": lang_code,
                "language_name": SUPPORTED_LANGUAGES[lang_code],
                "error": str(e.detail),
            })
        except Exception as e:
            results.append({
                "language": lang_code,
                "language_name": SUPPORTED_LANGUAGES[lang_code],
                "error": str(e),
            })

    return {"sentence": req.sentence, "results": results}


@app.get("/api/stories")
async def list_stories():
    return [
        {
            "id": story["id"],
            "title": story["title"],
            "source": story["source"],
            "language": story["language"],
            "sentence_count": len(story["sentences"]),
        }
        for story in STORIES.values()
    ]

@app.get("/api/story/{story_id}")
async def get_story(story_id: str):
    story = STORIES.get(story_id)
    if not story:
        raise HTTPException(404, "Story not found")
    return story

# --- Feedback ---
FEEDBACK_FILE = Path(__file__).parent / "feedback.jsonl"

class FeedbackRequest(BaseModel):
    message: str
    sentence: Optional[str] = None
    translation: Optional[str] = None
    target_language: Optional[str] = None

@app.post("/api/feedback")
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

app.mount("/", StaticFiles(directory="static", html=True), name="static")
