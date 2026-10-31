"""Gemini REST client. Backend-only; the key never reaches the browser. Any failure raises GeminiUnavailable so
callers fall back to deterministic code and say so honestly."""
from __future__ import annotations

import json
import logging

import httpx

from app.config import get_settings

log = logging.getLogger("campusx.gemini")


class GeminiUnavailable(RuntimeError):
    pass


def configured() -> bool:
    return bool(get_settings().gemini_api_key)


def generate(system: str, prompt: str, *, json_mode: bool = False, timeout: float = 15.0) -> str:
    st = get_settings()
    if not st.gemini_api_key:
        raise GeminiUnavailable("GEMINI_API_KEY is not configured")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{st.gemini_model}:generateContent"
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1,
                                 **({"responseMimeType": "application/json"} if json_mode else {})}}
    try:
        r = httpx.post(url, params={"key": st.gemini_api_key}, json=body, timeout=timeout)
        if r.status_code != 200:
            raise GeminiUnavailable(f"Gemini API returned HTTP {r.status_code}")
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except GeminiUnavailable:
        raise
    except Exception as e:  # noqa: BLE001  network, quota, malformed body ...
        log.warning("gemini call failed: %s", type(e).__name__)
        raise GeminiUnavailable(f"Gemini request failed ({type(e).__name__})") from e
