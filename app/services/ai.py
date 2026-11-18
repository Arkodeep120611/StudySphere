"""Thin wrapper around the official google-genai SDK.

The API key is read from server-side config only and is never sent to the browser.
When no key is configured, callers get a 503 with a clear message rather than fake output.
"""

import json

from flask import current_app
from google import genai
from google.genai import types

from ..utils import ApiError


def ai_enabled() -> bool:
    return bool(current_app.config.get("GEMINI_API_KEY"))


def _client():
    if not ai_enabled():
        raise ApiError(
            "AI features are not configured. Add GEMINI_API_KEY to your .env file and restart the server.",
            503,
        )
    client = current_app.extensions.get("gemini_client")
    if client is None:
        client = genai.Client(api_key=current_app.config["GEMINI_API_KEY"])
        current_app.extensions["gemini_client"] = client
    return client


def _call(contents, system_instruction, *, json_output=False, temperature=0.3) -> str:
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        response_mime_type="application/json" if json_output else "text/plain",
    )
    try:
        response = _client().models.generate_content(
            model=current_app.config["GEMINI_MODEL"],
            contents=contents,
            config=config,
        )
        text = (response.text or "").strip()
    except ApiError:
        raise
    except Exception:
        current_app.logger.exception("Gemini request failed")
        raise ApiError(
            "The AI service could not complete the request. Please try again in a moment.", 502
        )
    if not text:
        raise ApiError("The AI service returned an empty response. Please try again.", 502)
    return text


def generate_json(prompt: str, system_instruction: str) -> dict | list:
    raw = _call(prompt, system_instruction, json_output=True, temperature=0.3)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        current_app.logger.warning("Gemini returned non-JSON output: %r", raw[:300])
        raise ApiError("The AI returned malformed data. Please try again.", 502)


def chat(system_instruction: str, history: list[tuple[str, str]], message: str) -> str:
    contents = [
        types.Content(
            role="model" if role == "assistant" else "user",
            parts=[types.Part(text=content)],
        )
        for role, content in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return _call(contents, system_instruction, temperature=0.2)


OCR_PROMPT = (
    "Transcribe the text in each of the following page images, in order. "
    "Return only a JSON array of strings with exactly one string per image, in the same order. "
    "Keep the reading order and line breaks. Use an empty string for a page with no text. "
    "Do not describe images or add commentary."
)


def ocr_pages(images: list[bytes]) -> list[str]:
    """Transcribe page images (JPEG bytes) with Gemini vision. Returns one string per image."""
    parts = [types.Part.from_text(text=OCR_PROMPT)]
    parts += [types.Part.from_bytes(data=image, mime_type="image/jpeg") for image in images]
    raw = _call([types.Content(role="user", parts=parts)], None, json_output=True, temperature=0.0)
    try:
        texts = json.loads(raw)
    except json.JSONDecodeError:
        current_app.logger.warning("OCR returned non-JSON output: %r", raw[:300])
        raise ApiError("The OCR service returned malformed data. Please try again.", 502)
    if not isinstance(texts, list) or len(texts) != len(images) or not all(isinstance(t, str) for t in texts):
        current_app.logger.warning("OCR returned %s items for %s pages", type(texts).__name__, len(images))
        raise ApiError("The OCR service could not read every page. Please try again.", 502)
    return texts
