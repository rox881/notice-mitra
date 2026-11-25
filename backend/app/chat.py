from typing import Optional
from pydantic import BaseModel, Field

from app.llm_client import generate_with_fallback


class ChatReply(BaseModel):
    answer: str = Field(
        description="Direct, helpful answer in the requested language (EN, HI, or MR) grounded ONLY in the clauses."
    )
    citations: list[str] = Field(
        default_factory=list,
        description="List of exact clause codes used to answer (e.g. ['C2', 'C4']), or [] if not mentioned.",
    )
    found_in_notice: bool = Field(
        description="True if the answer was explicitly found in the clauses; False if absent."
    )


LANG_INSTRUCTIONS = {
    "en": "Reply in clear, simple English.",
    "hi": "Reply in natural, student-friendly Hindi (Devanagari script). Keep academic terms like CGPA, ATKT, MahaDBT recognizable.",
    "mr": "Reply in natural, student-friendly Marathi (Devanagari script). Keep academic terms like CGPA, ATKT, MahaDBT recognizable.",
}


def ask_notice_followup(
    clauses: list[dict],
    question: str,
    lang: str = "en",
    student_profile: Optional[dict] = None,
) -> dict:
    """
    Stage 4: Grounded Multilingual Follow-Up Q&A.
    Locked strictly to [C1..Cn] with deterministic citation verification.
    """
    if not clauses:
        raise ValueError("No notice clauses provided for Q&A.")

    lang = lang.strip().lower()
    lang_rule = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["en"])
    valid_codes = {c["clause_code"] for c in clauses}

    formatted_clauses = "\n".join(f"[{c['clause_code']}] {c['raw_text']}" for c in clauses)
    profile_block = f"\nStudent Profile Context: {student_profile}\n" if student_profile else ""

    system_prompt = (
        "You are a strict, trustworthy college notice assistant. Answer the student's question "
        "using ONLY the provided numbered clauses [C1..Cn] from the official notice.\n\n"
        "STRICT RULES:\n"
        "1. NEVER guess, assume, or use outside knowledge. If the answer is not explicitly stated "
        "in the clauses, set 'found_in_notice' to false, 'citations' to [], and politely say in the "
        "requested language that this detail is not mentioned in the notice and to check with the college admin office.\n"
        "2. Every factual statement MUST be backed by exact clause codes in 'citations' (e.g., ['C2', 'C5']).\n"
        f"3. {lang_rule}"
    )

    user_prompt = (
        f"OFFICIAL NOTICE CLAUSES:\n{formatted_clauses}\n"
        f"{profile_block}\n"
        f"STUDENT QUESTION: {question}"
    )

    raw_json = generate_with_fallback(
        contents=user_prompt,
        system_instruction=system_prompt,
        response_schema=ChatReply,
        temperature=0.1,
        prefer="groq",
    )

    parsed = ChatReply.model_validate_json(raw_json)
    # Deterministic guardrail: keep only real C# codes from this notice
    parsed.citations = [code for code in parsed.citations if code in valid_codes]
    return parsed.model_dump()