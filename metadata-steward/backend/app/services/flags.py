"""Runtime feature-flag helpers backed by the ``system_settings`` table."""
from __future__ import annotations

from sqlalchemy.orm import Session


def get_bool_flag(db: Session, key: str, default: bool = False) -> bool:
    """Read a boolean feature flag (``{"value": true|false}``) from settings."""
    from ..models import SystemSetting

    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None or not isinstance(row.value, dict):
        return default
    value = row.value.get("value", default)
    return bool(value)
