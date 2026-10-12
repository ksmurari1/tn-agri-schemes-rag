"""Speech-to-text helper for spoken farmer questions (Tamil or English).

This module only converts an audio recording into text. The text is placed in the question box,
where the farmer can review/edit it, and then goes through the normal guardrail -> retrieval -> answer flow.
It never searches the web and never touches the knowledge base.
"""
from __future__ import annotations

import io
import os

DEFAULT_TRANSCRIBE_MODEL = "whisper-1"


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "question.wav",
    model: str | None = None,
    language: str | None = None,
) -> str:
    """Return the transcript of a short audio clip.

    Config (all optional, via .env):
      OPENAI_TRANSCRIBE_MODEL     default: whisper-1
      OPENAI_TRANSCRIBE_LANGUAGE  e.g. ta or en; leave empty to auto-detect
      OPENAI_TRANSCRIBE_PROMPT    optional spelling hints for domain words
    """
    if not audio_bytes:
        raise ValueError("No audio was recorded. Please record your question again.")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing, so voice questions cannot be transcribed.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    kwargs = {
        "model": model or os.getenv("OPENAI_TRANSCRIBE_MODEL", DEFAULT_TRANSCRIBE_MODEL),
        "file": (filename or "question.wav", io.BytesIO(audio_bytes), "audio/wav"),
    }
    lang = (language or os.getenv("OPENAI_TRANSCRIBE_LANGUAGE", "")).strip()
    if lang:
        kwargs["language"] = lang
    prompt = os.getenv("OPENAI_TRANSCRIBE_PROMPT", "").strip()
    if prompt:
        kwargs["prompt"] = prompt
    result = client.audio.transcriptions.create(**kwargs)
    return (getattr(result, "text", "") or "").strip()
