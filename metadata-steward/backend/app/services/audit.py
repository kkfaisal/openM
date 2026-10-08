"""Audit trail service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import AuditEvent


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def record(
    db: Session,
    *,
    action: str,
    actor: str = "steward",
    actor_type: str = "system",
    entity: str | None = None,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    detail: str | None = None,
    confidence: float | None = None,
    policy: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_type=actor_type,
        actor=actor,
        action=action,
        entity=entity,
        field=field,
        old_value=old_value,
        new_value=new_value,
        detail=detail,
        confidence=confidence,
        policy=policy,
        timestamp=_now(),
    )
    db.add(event)
    return event
