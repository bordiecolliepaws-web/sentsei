"""Quiz endpoints."""
import json
import time
import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request

from models import SUPPORTED_LANGUAGES, CURATED_SENTENCES, QuizCheckRequest
from cache import get_quiz_answers, cleanup_quiz_answers
from auth import APP_PASSWORD, rate_limit_check, rate_limit_cleanup, get_rate_limit_key, require_password
from llm import (
    OLLAMA_MODEL, deterministic_pronunciation, parse_json_object,
    new_quiz_id, translation_hint, ollama_chat,
    get_model_for_language,
)

router = APIRouter()


@router.api_route("/api/quiz", methods=["GET", "POST"])
async def get_quiz(
    request: Request,
    lang: str,
    gender: str = "neutral",
    formality: str = "polite",
    _pw=Depends(require_password),
):

    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, "Unsupported language")

    lang_name = SUPPORTED_LANGUAGES[lang]
    quiz_answers = get_quiz_answers()

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
        quiz_id = new_quiz_id(lang, sentence)
        cleanup_quiz_answers()
        quiz_answers[quiz_id] = {
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

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=get_model_for_language(lang), temperature=0.2, num_predict=256, timeout=60
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    parsed = parse_json_object(text) or {}
    translation_en = (parsed.get("translation_en") or "").strip()
    translation_zh = (parsed.get("translation_zh") or "").strip()

    if not translation_en and not translation_zh:
        raise HTTPException(502, "Failed to generate quiz answer")
    if not translation_en:
        translation_en = translation_zh
    if not translation_zh:
        translation_zh = translation_en

    quiz_id = new_quiz_id(lang, sentence)
    cleanup_quiz_answers()
    quiz_answers[quiz_id] = {
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
        "hint": translation_hint(translation_en),
        "pronunciation": deterministic_pronunciation(sentence, lang),
    }


@router.post("/api/quiz-check", tags=["Quiz"], summary="Check a quiz answer")
async def quiz_check(
    request: Request,
    req: QuizCheckRequest,
    _pw=Depends(require_password),
):

    rate_key = get_rate_limit_key(request)
    rate_limit_cleanup()
    if not rate_limit_check(rate_key):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    answer = req.answer.strip()
    if not answer:
        raise HTTPException(400, "Answer is required")

    cleanup_quiz_answers()
    quiz_answers = get_quiz_answers()
    quiz = quiz_answers.get(req.quiz_id)

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

    system_msg = "You are a translation quiz grader. Grade semantic equivalence only. Return strict JSON only."

    text = await ollama_chat(
        [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}],
        model=get_model_for_language(quiz["language"]), temperature=0.1, num_predict=196, timeout=60
    )

    if text is None:
        raise HTTPException(502, "LLM API error")

    parsed = parse_json_object(text) or {}
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
