"""Metadata change endpoints (catalog writes with rollback info)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MetadataChange
from ..schemas import MetadataChangeOut

router = APIRouter(prefix="/api/changes", tags=["changes"])


@router.get("", response_model=list[MetadataChangeOut])
def list_changes(limit: int = 200, db: Session = Depends(get_db)):
    changes = (
        db.query(MetadataChange)
        .order_by(desc(MetadataChange.applied_at))
        .limit(limit)
        .all()
    )
    return [MetadataChangeOut.model_validate(c) for c in changes]
