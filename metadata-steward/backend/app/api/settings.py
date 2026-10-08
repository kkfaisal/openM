"""System settings endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import openai_api_key, set_openai_api_key, settings as app_settings
from ..db import get_db
from ..models import SystemSetting
from ..schemas import OpenAIKeyUpdate, SettingOut, SettingUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db)):
    rows = db.query(SystemSetting).all()
    # Always expose runtime configuration too (no secrets).
    base = [
        SettingOut(key="app_name", value={"value": app_settings.app_name}),
        SettingOut(key="version", value={"value": app_settings.version}),
        SettingOut(
            key="catalog_backend",
            value={"value": app_settings.catalog_backend},
        ),
        SettingOut(key="llm_provider", value={"value": app_settings.llm_provider}),
        SettingOut(key="openai_model", value={"value": app_settings.openai_model}),
        SettingOut(
            key="openmetadata_configured",
            value={"value": bool(app_settings.openmetadata_host)},
        ),
        SettingOut(
            key="openmetadata_host",
            value={"value": app_settings.openmetadata_host or ""},
        ),
        SettingOut(
            key="openai_configured",
            value={"value": bool(openai_api_key())},
        ),
    ]
    base += [SettingOut(key=r.key, value=r.value) for r in rows]
    return base


@router.put("/{key}", response_model=SettingOut)
def update_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None:
        row = SystemSetting(key=key, value=body.value)
        db.add(row)
    else:
        row.value = body.value
    db.commit()
    return SettingOut(key=key, value=body.value)


@router.post("/openai_api_key", response_model=SettingOut)
def save_openai_api_key(body: OpenAIKeyUpdate, db: Session = Depends(get_db)):
    """Save the OpenAI API key at runtime (persisted + used immediately)."""
    key = (body.api_key or "").strip()
    row = db.query(SystemSetting).filter(SystemSetting.key == "openai_api_key").first()
    if row is None:
        row = SystemSetting(key="openai_api_key", value={"value": key})
        db.add(row)
    else:
        row.value = {"value": key}
    db.commit()
    set_openai_api_key(key)
    return SettingOut(
        key="openai_api_key", value={"configured": bool(key)}
    )
