from typing import Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.extractor import extract_canonical_notice
from app.parser import parse_document, parse_raw_text

app = FastAPI(title="Multilingual College Notice Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "docx"}


@app.get("/health")
def health_check():
    return {"status": "ok", "stage": "2-extractor-ready"}


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
    # Stage 1: Deterministic Clause Parsing
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

    # Stage 2: Canonical Extraction + Citation Guardrail
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