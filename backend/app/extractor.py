import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.schemas import CanonicalNotice

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID = "gemini-3.5-flash-lite"

SYSTEM_PROMPT = """
You are a precise college notice analyzer. You will be given numbered clauses [C1], [C2], ... from an official college notice.
Extract the structured canonical summary in clear, simple English.

Rules:
1. Every bullet, deadline, document, and edge condition MUST cite the exact source clause code (e.g., 'C1', 'C4').
2. Never invent dates, fees, eligibility criteria, or clause codes that are not explicitly in the provided text.
3. Keep summary_bullets short, actionable, and free of bureaucratic jargon.
4. Put any conditional or exception rules (e.g., 'not valid for hostelites', 'late fee applies after...') into edge_conditions with their exact C# citation.
"""


def _validate_citations(notice: CanonicalNotice, valid_codes: set[str]) -> CanonicalNotice:
    """Deterministic guardrail: ensures every C# citation actually exists in the parsed document."""
    notice.summary_bullets = [
        item for item in notice.summary_bullets if item.citation in valid_codes
    ]
    notice.deadlines = [
        item for item in notice.deadlines if item.citation in valid_codes
    ]
    notice.required_documents = [
        item for item in notice.required_documents if item.citation in valid_codes
    ]
    notice.edge_conditions = [
        item for item in notice.edge_conditions if item.citation in valid_codes
    ]
    if notice.hard_rules.citation not in valid_codes:
        notice.hard_rules.citation = None
    return notice


def extract_canonical_notice(clauses: list[dict]) -> dict:
    """
    Runs AI Call #1 once per notice to produce the validated Canonical English JSON.
    """
    if not clauses:
        raise ValueError("No clauses provided for extraction.")

    valid_codes = {c["clause_code"] for c in clauses}
    formatted_input = "\n".join(f"[{c['clause_code']}] {c['raw_text']}" for c in clauses)

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=formatted_input,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=CanonicalNotice,
            temperature=0.1,
        ),
    )

    parsed_notice = CanonicalNotice.model_validate_json(response.text)
    verified_notice = _validate_citations(parsed_notice, valid_codes)
    return verified_notice.model_dump()