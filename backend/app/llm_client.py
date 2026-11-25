import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from groq import Groq

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) if os.getenv("GROQ_API_KEY") else None

GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-4-hydrogen"
]
GROQ_MODEL = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]


def _call_gemini(contents: str, system_instruction: str | None, response_schema, temperature: float) -> str:
    config_kwargs = {"temperature": temperature}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    config = types.GenerateContentConfig(**config_kwargs)
    last_error = None

    for model_id in GEMINI_MODELS:
        for attempt in range(2):
            try:
                res = gemini_client.models.generate_content(
                    model=model_id,
                    contents=contents,
                    config=config,
                )
                return res.text
            except APIError as e:
                last_error = e
                if e.code in (429, 503):
                    time.sleep(0.8 * (attempt + 1))
                    continue
                break
    raise RuntimeError(f"Gemini unavailable: {last_error}")


def _call_groq(contents: str, system_instruction: str | None, response_schema, temperature: float) -> str:
    if not groq_client:
        raise RuntimeError("GROQ_API_KEY not configured in .env")

    sys_prompt = system_instruction or "You are a helpful assistant."
    if response_schema is not None:
        schema_json = response_schema.model_json_schema()
        sys_prompt += (
            f"\n\nYou MUST output ONLY valid JSON matching this exact JSON Schema:\n{schema_json}"
        )

    last_error = None
    for model_id in GROQ_MODELS:
        try:
            kwargs = {
                "model": model_id,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": contents},
                ],
            }
            if response_schema is not None:
                kwargs["response_format"] = {"type": "json_object"}

            res = groq_client.chat.completions.create(**kwargs)
            return res.choices[0].message.content
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Groq unavailable: {last_error}")

def generate_with_fallback(
    contents: str,
    system_instruction: str | None = None,
    response_schema=None,
    temperature: float = 0.1,
    prefer: str = "gemini",
) -> str:
    """
    Routes AI calls between Gemini and Groq with automatic cross-provider failover.
    - prefer='gemini': Best for structured extraction & Hindi/Marathi translation (falls back to Groq on 503).
    - prefer='groq': Ultra-fast inference for Stage 4 follow-up chat (falls back to Gemini if needed).
    """
    providers = [_call_gemini, _call_groq] if prefer == "gemini" else [_call_groq, _call_gemini]
    errors = []

    for provider_fn in providers:
        try:
            return provider_fn(contents, system_instruction, response_schema, temperature)
        except Exception as e:
            errors.append(str(e))

    raise RuntimeError(f"All AI providers failed: {' | '.join(errors)}")