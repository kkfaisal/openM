"""Local speech-to-text via faster-whisper (a Hugging Face model).

Used when the OpenAI audio endpoint is unavailable (e.g. blocked by a corporate
proxy such as Zscaler). The model is downloaded once into the backend's
``models/`` directory and cached in-process.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2]  # .../backend

# --- Make Hugging Face downloads work behind a TLS-intercepting proxy --- #
def _ca_bundle() -> str:
    import certifi

    combined = _BASE / "certs" / "cacert.pem"
    return str(combined) if combined.exists() else certifi.where()


os.environ.setdefault("SSL_CERT_FILE", _ca_bundle())
os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle())
os.environ.setdefault("CURL_CA_BUNDLE", _ca_bundle())
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HOME", str(_BASE / ".hf_home"))


def _ensure_av_compat() -> None:
    """Newer PyAV dropped the ``metadata_errors`` kwarg that faster-whisper
    still passes; drop it transparently so any PyAV version works."""
    import av

    if getattr(av.open, "__patched_for_faster_whisper__", False):
        return
    _orig = av.open

    def _patched(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        kwargs.pop("metadata_errors", None)
        return _orig(*args, **kwargs)

    _patched.__patched_for_faster_whisper__ = True  # type: ignore[attr-defined]
    av.open = _patched  # type: ignore[assignment]


_ensure_av_compat()

_MODELS_DIR = _BASE / "models"
_TMP_DIR = _BASE / ".tmp"

_model_cache: dict[str, object] = {}


def _model(size: str):
    if size not in _model_cache:
        from faster_whisper import WhisperModel

        _model_cache[size] = WhisperModel(
            size,
            device="cpu",
            compute_type="int8",
            download_root=str(_MODELS_DIR),
        )
    return _model_cache[size]


def transcribe(file_bytes: bytes, filename: str) -> str:
    """Transcribe audio/video bytes to text using the local Whisper model."""
    from ..config import settings

    model = _model(settings.whisper_model)

    # faster-whisper (PyAV) detects the format from the extension, so write to a
    # temp file with the original suffix.
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename or "recording.m4a").suffix or ".m4a"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, dir=str(_TMP_DIR))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_bytes)
        segments, _info = model.transcribe(tmp_path)
        return "".join(s.text for s in segments).strip()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
