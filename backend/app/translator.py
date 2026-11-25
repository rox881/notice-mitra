import hashlib
import json
from pydantic import BaseModel

from app.llm_client import generate_with_fallback

# In-memory cache keyed by "{notice_hash}:{lang}" (0 tokens on repeat views)
_TRANSLATION_CACHE: dict[str, dict] = {}

LANG_NAMES = {
    "hi": "Hindi (Devanagari script)",
    "mr": "Marathi (Devanagari script)",
}


class TranslatedBullet(BaseModel):
    text: str
    citation: str


class TranslatedDeadline(BaseModel):
    event: str
    date: str
    citation: str


class TranslatedNoticeView(BaseModel):
    title: str
    summary_bullets: list[TranslatedBullet]
    deadlines: list[TranslatedDeadline]
    required_documents: list[TranslatedBullet]
    edge_conditions: list[TranslatedBullet]


def _compute_cache_key(canonical: dict, lang: str) -> str:
    payload = json.dumps(canonical, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{digest}:{lang}"


def get_localized_notice(canonical: dict, lang: str = "en") -> dict:
    """
    Returns the notice display fields in 'en', 'hi', or 'mr'.
    - 'en': 0 tokens (returns canonical English directly)
    - 'hi' / 'mr': Checks cache first; runs AI Call #2 only on cache miss.
    """
    lang = lang.strip().lower()
    base_view = {
        "lang": "en",
        "cached": True,
        "title": canonical["title"],
        "category": canonical["category"],
        "urgency": canonical["urgency"],
        "summary_bullets": canonical.get("summary_bullets", []),
        "deadlines": canonical.get("deadlines", []),
        "required_documents": canonical.get("required_documents", []),
        "edge_conditions": canonical.get("edge_conditions", []),
    }

    if lang == "en" or lang not in LANG_NAMES:
        return base_view

    cache_key = _compute_cache_key(canonical, lang)
    if cache_key in _TRANSLATION_CACHE:
        return {**_TRANSLATION_CACHE[cache_key], "cached": True}

    # AI Call #2: Translate only user-facing fields into natural Hindi/Marathi
    translatable_payload = {
        "title": canonical["title"],
        "summary_bullets": canonical.get("summary_bullets", []),
        "deadlines": canonical.get("deadlines", []),
        "required_documents": canonical.get("required_documents", []),
        "edge_conditions": canonical.get("edge_conditions", []),
    }

    prompt = (
        f"Translate the following structured college notice JSON into natural, clear "
        f"{LANG_NAMES[lang]} suitable for Indian college students.\n"
        f"Rules:\n"
        f"1. Preserve every 'citation' code (e.g., 'C1', 'C4') and numeric date/fee amount EXACTLY as-is.\n"
        f"2. Keep common academic acronyms (like CGPA, ATKT, MahaDBT, PDF, FE/SE/TE/BE) recognizable.\n"
        f"3. Do not add or remove any items.\n\n"
        f"Input JSON:\n{json.dumps(translatable_payload, ensure_ascii=False)}"
    )

    raw_json = generate_with_fallback(
            contents=prompt,
            response_schema=TranslatedNoticeView,
            temperature=0.1,
        )

    translated = TranslatedNoticeView.model_validate_json(raw_json).model_dump()
    result = {
        "lang": lang,
        "cached": False,
        "category": canonical["category"],
        "urgency": canonical["urgency"],
        **translated,
    }

    _TRANSLATION_CACHE[cache_key] = result
    return result