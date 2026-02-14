"""Sentsei — Sentence-based language learning app."""
import json
import random
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import httpx

# Deterministic pronunciation libraries
import pykakasi
from pypinyin import pinyin, Style as PinyinStyle
from korean_romanizer.romanizer import Romanizer

_kakasi = pykakasi.kakasi()


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

APP_PASSWORD = "sentsei2026"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"
TAIDE_MODEL = "jcai/llama3-taide-lx-8b-chat-alpha1:Q4_K_M"

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
    speaker_gender: Optional[str] = None
    speaker_formality: Optional[str] = None

@app.post("/api/learn")
async def learn_sentence(
    req: SentenceRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

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

    # Detect if input looks Chinese (contains CJK unified ideographs)
    input_is_chinese = any('\u4e00' <= c <= '\u9fff' for c in req.sentence)

    # Detect source language
    source_lang = "Traditional Chinese (繁體中文, 台灣用法)" if input_is_chinese else "English"
    source_lang_short = "繁體中文" if input_is_chinese else "English"

    prompt = f"""TASK: Translate this sentence into {lang_name} and break it down.

TARGET LANGUAGE: {lang_name} — {script_hint}
SOURCE LANGUAGE (what the user typed in): {source_lang}

INPUT: "{req.sentence}"

You MUST translate into {lang_name}. For example, if target is Korean, write 한국어. If Japanese, write 日本語. If Hebrew, write עברית. Do NOT output Chinese unless the target language IS Chinese.

CRITICAL RULES:
1. The "translation" field MUST be written in {lang_name} using {script_hint}. NOT Chinese, NOT English (unless target IS English).
2. The "word" fields in breakdown MUST be {lang_name} words in {lang_name} script.
3. ALL "meaning" fields MUST be in {source_lang_short}. ALL "grammar_notes" MUST be in {source_lang_short}. ALL "cultural_note" and "note" fields MUST be in {source_lang_short}. The user reads {source_lang_short}, so write ALL explanations in {source_lang_short}. NEVER write explanations in Chinese if the source is English. NEVER write explanations in English if the source is Chinese.
4. When writing ANY Chinese text, use ONLY Traditional Chinese (繁體中文) with Taiwan usage. NEVER Simplified Chinese.
5. Do NOT mix languages. Explanations in one language only.

Respond with ONLY valid JSON (no markdown, no code fences) in this exact structure:
{{
  "translation": "the full sentence in {lang_name} script (e.g. for Korean use 한글, for Japanese use 日本語, etc.)",
  "pronunciation": "romanized pronunciation guide using standard systems: Japanese=Hepburn romaji (e.g. oshiete kudasai, NOT OLLOW-te), Chinese=pinyin with tones, Korean=Revised Romanization, Hebrew=standard transliteration, Greek=standard transliteration",
  "literal": "word-by-word literal translation back to the detected source language",
  "breakdown": [
    {{
      "word": "each word/particle written in {lang_name} script",
      "pronunciation": "romanized pronunciation (Japanese: Hepburn romaji like 'kudasai', NOT made-up spellings)",
      "meaning": "meaning in the detected source language",
      "difficulty": "easy|medium|hard",
      "note": "brief grammar/usage note if helpful, otherwise null"
    }}
  ],
  "grammar_notes": [
    "Key grammar pattern or structure explanation (1-3 short notes, in the detected source language)"
  ],
  "cultural_note": "optional cultural context or usage tip (in the detected source language), null if none",
  "formality": "casual|polite|formal — what register this translation uses",
  "alternative": "an alternative way to say this (different formality or phrasing), or null",
  "native_expression": "How a native {lang_name} speaker would NATURALLY say this — MUST be a DIFFERENT sentence from the translation, not a rewording or repetition. Show a genuinely different way a native would express the same idea (different structure, idiom, or colloquial phrasing). Include pronunciation and a brief explanation. MUST be null if you cannot think of a meaningfully different expression."
}}"""

    # Inject speaker identity if provided
    gender = req.speaker_gender or "neutral"
    formality = req.speaker_formality or "polite"
    speaker_block = f"""
SPEAKER IDENTITY:
- Gender: {gender} — adjust pronouns, gendered words accordingly. For Japanese: use 僕/俺 for male, あたし for female, 私 for neutral. For Hebrew: adjust verb conjugation, adjectives, pronouns. For Spanish/Italian: adjust adjective agreement.
- Formality: {formality} — use appropriate register. For Korean: casual=반말, polite=존댓말, formal=격식체. For Japanese: casual=タメ口, polite=です/ます, formal=敬語.
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

    if lang_code == "zh":
        system_msg = f"You are a Taiwanese Chinese (繁體中文/台灣用法) language teacher. You translate into Traditional Chinese as spoken in Taiwan. NEVER use mainland Chinese phrasing or simplified characters. Think like a native Taiwanese speaker. Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    elif input_is_chinese and lang_code == "en":
        system_msg = f"You are an English language teacher helping Chinese speakers learn English. The user writes in Chinese and you translate into ENGLISH. The 'translation' field MUST be in English. The 'pronunciation' field should be English pronunciation guide. The 'word' fields in breakdown MUST be English words. All 'meaning', 'grammar_notes', 'note', and 'cultural_note' fields must be in 繁體中文 (Traditional Chinese, Taiwan usage). The 'native_expression' field should show how a native English speaker would naturally say it in English, with 繁體中文 explanation. Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    elif input_is_chinese:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. All Chinese explanations must use Traditional Chinese (繁體中文) with Taiwan usage (台灣用法). Always respond with valid JSON only.\n{taiwan_chinese_rules}"
    else:
        system_msg = f"You are a {lang_name} language teacher. You ONLY output {lang_name} translations. You NEVER translate into Chinese unless the target language is Chinese. When the target is Korean, you write in 한국어. When Japanese, you write in 日本語. Always respond with valid JSON only."

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

    # Post-process: override LLM pronunciation with deterministic libraries
    translation_text = result.get("translation", "")
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

    # Post-process: null out native_expression if it's just repeating the translation
    native = result.get("native_expression")
    translation = result.get("translation", "")
    if native and translation:
        # Strip pronunciation/explanation suffixes to compare core sentence
        native_core = native.split("(")[0].strip().rstrip("。.!！")
        trans_core = translation.strip().rstrip("。.!！")
        if native_core == trans_core or native_core in trans_core or trans_core in native_core:
            result["native_expression"] = None

    return result

class WordDetailRequest(BaseModel):
    word: str
    meaning: str
    target_language: str
    sentence_context: Optional[str] = None

@app.post("/api/word-detail")
async def word_detail(
    req: WordDetailRequest,
    x_app_password: Optional[str] = Header(default=None),
):
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, "Unauthorized")

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

    return result

@app.get("/api/languages")
async def get_languages():
    return SUPPORTED_LANGUAGES

@app.get("/api/surprise")
async def get_surprise_sentence(lang: str):
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    sentence_pool = CURATED_SENTENCES.get(lang, [])
    if not sentence_pool:
        raise HTTPException(404, "No curated sentences found for this language")

    picked = random.choice(sentence_pool)
    return {
        "language": lang,
        "sentence": picked["sentence"],
        "difficulty": picked["difficulty"],
        "category": picked["category"],
        "source": picked["source"],
    }

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

app.mount("/", StaticFiles(directory="static", html=True), name="static")
