"""Compare endpoint for Sentsei."""
import json
from fastapi import APIRouter, Depends, HTTPException, Request

from models import SUPPORTED_LANGUAGES, SentenceRequest, CompareRequest
from auth import rate_limit_check, rate_limit_cleanup, require_password
from learn_routes import _learn_sentence_impl, _detect_input_language, MAX_INPUT_LEN

router = APIRouter()


@router.post("/api/compare")
async def compare_sentence(
    request: Request,
    req: CompareRequest,
    _pw=Depends(require_password),
):

    client_ip = request.client.host if request.client else "unknown"
    rate_limit_cleanup()
    if not rate_limit_check(client_ip):
        raise HTTPException(429, "Too many requests. Please wait a minute.")

    if not req.sentence.strip():
        raise HTTPException(400, "Sentence is required")

    if len(req.sentence) > MAX_INPUT_LEN:
        raise HTTPException(400, f"Input too long (max {MAX_INPUT_LEN} characters)")

    input_is_chinese = _detect_input_language(req.sentence, req.input_language or "auto")
    skip_langs = {"zh"} if input_is_chinese else {"en"}
    target_langs = [code for code in SUPPORTED_LANGUAGES if code not in skip_langs]

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
            result = await _learn_sentence_impl(request, single_req)
            if hasattr(result, 'body'):
                result = json.loads(result.body)
            results.append({
                "language": lang_code,
                "language_name": SUPPORTED_LANGUAGES[lang_code],
                "translation": result.get("translation", ""),
                "pronunciation": result.get("pronunciation", ""),
                "formality": result.get("formality", ""),
                "literal": result.get("literal", ""),
                "difficulty": result.get("difficulty"),
            })
        except HTTPException as e:
            if e.status_code == 429:
                break
            results.append({"language": lang_code, "language_name": SUPPORTED_LANGUAGES[lang_code], "error": str(e.detail)})
        except Exception as e:
            results.append({"language": lang_code, "language_name": SUPPORTED_LANGUAGES[lang_code], "error": str(e)})

    return {"sentence": req.sentence, "results": results}
