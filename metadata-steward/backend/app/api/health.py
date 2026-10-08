"""Health endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import HealthSnapshot
from ..schemas import HealthOut
from ..services import health

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthOut)
def current_health(db: Session = Depends(get_db)):
    snap = health.latest_snapshot(db)
    if snap is None:
        overall, dimensions = health.compute_health(db)
        db.commit()
        snap = health.latest_snapshot(db)
    return HealthOut.model_validate(snap)


@router.get("/history", response_model=list[HealthOut])
def health_history(limit: int = 60, db: Session = Depends(get_db)):
    snaps = (
        db.query(HealthSnapshot)
        .order_by(desc(HealthSnapshot.created_at))
        .limit(limit)
        .all()
    )
    return [HealthOut.model_validate(s) for s in snaps]
