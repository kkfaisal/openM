"""Audit trail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditEvent
from ..schemas import AuditEventOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
def list_audit(limit: int = 300, db: Session = Depends(get_db)):
    events = (
        db.query(AuditEvent).order_by(desc(AuditEvent.timestamp)).limit(limit).all()
    )
    return [AuditEventOut.model_validate(e) for e in events]
