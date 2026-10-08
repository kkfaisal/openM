"""Transcription orchestration: OpenAI (whisper-1) with a local fallback."""
from __future__ import annotations

from ..config import settings
from . import local_transcribe
from .llm import get_llm


def transcribe(file_bytes: bytes, filename: str) -> str:
    """Transcribe audio/video, honoring ``TRANSCRIPTION_PROVIDER``.

    ``auto`` (default) tries OpenAI first and silently falls back to the local
    Hugging Face model when OpenAI is unavailable (e.g. blocked by a proxy).
    """
    provider = settings.transcription_provider.lower()

    if provider == "local":
        return local_transcribe.transcribe(file_bytes, filename)

    if provider == "openai":
        return get_llm().transcribe_audio(filename=filename, file_bytes=file_bytes)

    # auto
    try:
        return get_llm().transcribe_audio(filename=filename, file_bytes=file_bytes)
    except Exception:  # noqa: BLE001 — fall back to local on any OpenAI failure
        return local_transcribe.transcribe(file_bytes, filename)
