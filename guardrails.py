"""Lightweight input guardrails for the Tamil Nadu agriculture RAG app.

Checks user questions before retrieval or answer generation. This module does not
perform web search and does not change the indexed knowledge base.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    message: str
    category: str = "allowed"


_PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"reveal\s+(the\s+)?(system prompt|hidden prompt|api key|secret)",
    r"show\s+(me\s+)?(the\s+)?(api key|secret|environment variables)",
    r"act\s+as\s+if\s+there\s+are\s+no\s+rules",
]


def check_question(question: str) -> GuardrailResult:
    """Return allow/block result using injection checks and OpenAI moderation.

    Fails closed if moderation cannot be completed, rather than silently skipping
    the safety check. The caller should show the returned message to the user.
    """
    text = (question or "").strip()
    if not text:
        return GuardrailResult(False, "Please enter a question.", "empty_input")

    if any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in _PROMPT_INJECTION_PATTERNS
    ):
        return GuardrailResult(
            False,
            "இந்தக் கேள்வி பாதுகாப்பு விதிகளை மீற முயற்சிப்பதால் தடுக்கப்பட்டது. "
            "வேளாண்மைத் திட்டங்கள் தொடர்பான கேள்வியை முயற்சிக்கவும்.",
            "prompt_injection",
        )

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return GuardrailResult(
            False,
            "Safety check unavailable because OPENAI_API_KEY is not configured. Please contact the app administrator.",
            "configuration_error",
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        result = client.moderations.create(
            model=os.getenv("OPENAI_MODERATION_MODEL", "omni-moderation-latest"),
            input=text,
        )
        moderation = result.results[0]
        if moderation.flagged:
            return GuardrailResult(
                False,
                "இந்தக் கேள்விக்கு பாதுகாப்பாக உதவ முடியாது. தமிழ்நாடு வேளாண்மைத் திட்டங்கள், "
                "மானியங்கள் அல்லது தகுதி விவரங்கள் பற்றி கேட்கலாம்.",
                "moderation_block",
            )
        return GuardrailResult(True, "Safety check passed.", "allowed")
    except Exception:
        return GuardrailResult(
            False,
            "The safety check could not be completed, so this question was not processed. Please try again shortly.",
            "moderation_unavailable",
        )
