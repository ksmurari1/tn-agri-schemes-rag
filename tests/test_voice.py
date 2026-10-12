import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest

from src.voice import transcribe_audio


class _FakeTranscriptions:
    def __init__(self, text):
        self.text, self.kwargs = text, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return type("R", (), {"text": self.text})()


def _install_fake_openai(monkeypatch, text="  வணக்கம் hello  "):
    fake = _FakeTranscriptions(text)

    class FakeClient:
        def __init__(self, api_key=None):
            self.audio = type("A", (), {"transcriptions": fake})()

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    return fake


def test_transcribe_returns_stripped_text_and_default_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_TRANSCRIBE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_TRANSCRIBE_LANGUAGE", raising=False)
    fake = _install_fake_openai(monkeypatch)
    assert transcribe_audio(b"RIFFdata") == "வணக்கம் hello"
    assert fake.kwargs["model"] == "whisper-1"
    assert "language" not in fake.kwargs


def test_transcribe_passes_language_when_configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_TRANSCRIBE_LANGUAGE", "ta")
    fake = _install_fake_openai(monkeypatch)
    transcribe_audio(b"RIFFdata")
    assert fake.kwargs["language"] == "ta"


def test_transcribe_rejects_empty_audio_and_missing_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(ValueError):
        transcribe_audio(b"")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        transcribe_audio(b"RIFFdata")
