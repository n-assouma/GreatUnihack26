"""ElevenLabs text to speech (F15).

Returns MP3 bytes, or None. `None` becomes a 503 and the frontend falls back to the
browser's own voice, so voice output degrades instead of breaking.
"""

from __future__ import annotations

import os

import httpx

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MODEL_ID = "eleven_flash_v2_5"  # lowest latency; the reply is spoken live
MAX_CHARS = 1000

_tts_ever_failed = False


def configured() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY") and os.getenv("ELEVENLABS_VOICE_ID"))


def status() -> str:
    """"real" | "mock" — for /api/health."""
    if not configured():
        return "mock"
    return "degraded" if _tts_ever_failed else "real"


def speak(text: str) -> bytes | None:
    global _tts_ever_failed

    if not configured() or not text.strip():
        return None

    voice_id = os.environ["ELEVENLABS_VOICE_ID"]
    try:
        response = httpx.post(
            API_URL.format(voice_id=voice_id),
            json={"text": text[:MAX_CHARS], "model_id": MODEL_ID},
            headers={
                "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.content
    except httpx.HTTPError as exc:
        _tts_ever_failed = True
        print(f"[tts] ElevenLabs call failed ({type(exc).__name__}: {exc})")
        return None
