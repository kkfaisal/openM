"""Scan endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ScanRun
from ..schemas import ScanResult, ScanRunOut
from ..services import scanner

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.get("", response_model=list[ScanRunOut])
def list_scans(limit: int = 50, db: Session = Depends(get_db)):
    runs = db.query(ScanRun).order_by(desc(ScanRun.started_at)).limit(limit).all()
    return [ScanRunOut.model_validate(r) for r in runs]


@router.post("", response_model=ScanResult)
def trigger_scan(investigate: bool = True, db: Session = Depends(get_db)):
    run = scanner.run_scan(db, investigate=investigate)
    return ScanResult(scan=ScanRunOut.model_validate(run), findings_created=run.findings_created)
