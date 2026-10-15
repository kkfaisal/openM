"""Encryption for connection secrets stored in the steward database.

Tool credentials (OpenMetadata bot tokens, passwords) are encrypted at rest
with Fernet. The key comes from ``METALENS_SECRET_KEY``. In development, when
the variable is unset, a key is generated once and kept in
``.metalens_secret_key`` next to the database so restarts can still decrypt.
Production deployments must set the variable explicitly.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)

_KEY_FILE = Path(os.getenv("METALENS_SECRET_KEY_FILE", ".metalens_secret_key"))
_fernet: Fernet | None = None


def _load_key() -> bytes:
    env = os.getenv("METALENS_SECRET_KEY")
    if env:
        return env.encode()
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    try:
        _KEY_FILE.chmod(0o600)
    except OSError:
        pass
    log.warning(
        "METALENS_SECRET_KEY is not set; generated a development key at %s. "
        "Set METALENS_SECRET_KEY in production.",
        _KEY_FILE,
    )
    return key


def _f() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def encrypt(value: str) -> str:
    return _f().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _f().decrypt(value.encode()).decode()
    except InvalidToken:
        log.error("Could not decrypt a stored secret (was METALENS_SECRET_KEY rotated?)")
        return None


def mask(value: str | None) -> str | None:
    if not value:
        return None
    return f"{value[:4]}…{value[-4:]}" if len(value) > 12 else "••••"
