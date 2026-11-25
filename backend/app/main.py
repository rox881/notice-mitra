from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.eligibility import StudentProfile, evaluate_eligibility
from app.extractor import extract_canonical_notice
from app.parser import parse_document, parse_raw_text
from app.translator import get_localized_notice
from app.chat import ask_notice_followup
from pathlib import Path
from fastapi.responses import FileResponse

app = FastAPI(title="Multilingual College Notice Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx"}


class EligibilityRequest(BaseModel):
    canonical: dict
    profile: StudentProfile


class TranslateRequest(BaseModel):
    canonical: dict
    lang: str = "en"  # "en", "hi", or "mr"

class ChatRequest(BaseModel):
    clauses: list[dict]
    question: str
    lang: str = "en"  # "en", "hi", or "mr"
    profile: Optional[StudentProfile] = None


@app.get("/health")
def health_check():
    return {"status": "ok", "stage": "3-eligibility-and-translation-ready"}


@app.post("/api/notices/parse")
async def parse_notice_endpoint(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
):
    if file and file.filename:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '.{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        return parse_document(file_bytes, file.filename)

    if raw_text and raw_text.strip():
        return parse_raw_text(raw_text)

    raise HTTPException(
        status_code=400,
        detail="Provide either a notice file (PDF/DOCX/Image) or pasted raw_text.",
    )


@app.post("/api/notices/analyze")
async def analyze_notice_endpoint(
    file: Optional[UploadFile] = File(None),
    raw_text: Optional[str] = Form(None),
):
    if file and file.filename:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '.{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        parsed = parse_document(file_bytes, file.filename)
    elif raw_text and raw_text.strip():
        parsed = parse_raw_text(raw_text)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a notice file (PDF/DOCX/Image) or pasted raw_text.",
        )

    if not parsed["clauses"]:
        raise HTTPException(status_code=422, detail="No readable text clauses found in notice.")

    try:
        canonical = extract_canonical_notice(parsed["clauses"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    return {
        "filename": parsed["filename"],
        "total_clauses": parsed["total_clauses"],
        "clauses": parsed["clauses"],
        "canonical": canonical,
    }


@app.post("/api/notices/eligibility")
def check_eligibility_endpoint(payload: EligibilityRequest):
    """Stage 3A: 100% Deterministic Eligibility Check (0 AI tokens)."""
    return evaluate_eligibility(payload.canonical, payload.profile)


@app.post("/api/notices/translate")
def translate_notice_endpoint(payload: TranslateRequest):
    """Stage 3B: Lazy-loaded Hindi/Marathi translation with cache (0 tokens on repeat)."""
    try:
        return get_localized_notice(payload.canonical, payload.lang)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

@app.post("/api/notices/chat")
def chat_notice_endpoint(payload: ChatRequest):
    """Stage 4: Grounded Multilingual Follow-Up Chat locked to [C1..Cn]."""
    try:
        profile_dict = payload.profile.model_dump() if payload.profile else None
        return ask_notice_followup(
            clauses=payload.clauses,
            question=payload.question,
            lang=payload.lang,
            student_profile=profile_dict,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(STATIC_INDEX)