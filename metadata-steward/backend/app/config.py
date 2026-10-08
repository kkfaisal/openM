"""Application configuration.

All values are read from environment variables (never hard-coded secrets).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    app_name: str = "MetaLens"
    version: str = "1.0.0"

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///./metadata_steward.db"
        )
    )

    # CORS
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if o.strip()
        ]
    )

    # OpenMetadata integration
    openmetadata_host: str | None = os.getenv(
        "OPENMETADATA_HOST", "http://127.0.0.1:8585"
    )
    openmetadata_jwt: str | None = os.getenv("OPENMETADATA_JWT")
    openmetadata_email: str = os.getenv(
        "OPENMETADATA_EMAIL", "admin@open-metadata.org"
    )
    openmetadata_password: str = os.getenv("OPENMETADATA_PASSWORD", "admin")
    # "demo" (seeded local catalog) | "openmetadata"
    catalog_backend: str = os.getenv("CATALOG_BACKEND", "openmetadata")

    # LLM
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # OpenAI-compatible base URL (no trailing slash). Point this at a gateway /
    # Azure OpenAI / proxy that is not blocked, e.g. when Zscaler blocks the
    # default api.openai.com audio transcription endpoint.
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    # "heuristic" (no key required) | "openai"
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")

    # Audio/video transcription.
    # "auto" = try OpenAI (whisper-1) then fall back to local Whisper;
    # "openai" = OpenAI only; "local" = local Hugging Face model only.
    transcription_provider: str = os.getenv("TRANSCRIPTION_PROVIDER", "auto")
    # Local Whisper model size: tiny | base | small | medium | large-v3
    whisper_model: str = os.getenv("WHISPER_MODEL", "base")

    # Default action modes (conservative by default)
    default_description_mode: str = os.getenv(
        "DEFAULT_DESCRIPTION_MODE", "REQUIRE_APPROVAL"
    )


settings = Settings()


# Runtime-overridable OpenAI API key (set from the UI; persisted in the DB).
_runtime_openai_key: str | None = None


def set_openai_api_key(key: str | None) -> None:
    global _runtime_openai_key
    _runtime_openai_key = (key or "").strip() or None


def openai_api_key() -> str | None:
    """Return the UI-provided key, falling back to the OPENAI_API_KEY env var."""
    return _runtime_openai_key or settings.openai_api_key
