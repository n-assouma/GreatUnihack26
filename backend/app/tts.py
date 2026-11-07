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


KEY_PREFIX = "sk_"
_warned_about_key = False


def configured() -> bool:
    """True only if a key that *can* work is present.

    ElevenLabs keys start with `sk_` and are shown only when created or rotated;
    the dashboard also shows an API key *ID*, which looks like a credential but is
    rejected with 400 `api_key_id_used_as_api_key`. We were handed the id once, and
    a non-empty-means-configured check reported tts as "real" in /api/health right
    up until the first call failed. Checking the shape turns that into a startup
    warning instead of a surprise mid-demo.
    """
    global _warned_about_key

    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not key or not voice:
        return False
    if not key.startswith(KEY_PREFIX):
        if not _warned_about_key:
            _warned_about_key = True
            print(
                "[tts] ELEVENLABS_API_KEY does not start with 'sk_', so it cannot work "
                "(this is what an API key ID looks like, not an API key). Create or "
                "rotate a key in ElevenLabs and paste the sk_... value. Falling back "
                "to the browser voice."
            )
        return False
    return True


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
