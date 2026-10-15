"""Scan orchestration (the daily steward workflow, triggered on demand)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import ScanRun
from . import findings, health


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def run_scan(db: Session, *, investigate: bool = True) -> ScanRun:
    """Scan the catalog, create findings, recalculate health, (optionally)
    run agents, and persist a ScanRun record."""
    run = ScanRun(status="RUNNING", started_at=_now())
    db.add(run)
    db.flush()

    # In OpenMetadata mode, refresh the local snapshot before detecting.
    from ..config import settings

    if settings.catalog_backend == "openmetadata":
        from . import sync

        # Per-dataset sync; connection errors are recorded on the dataset
        # instead of failing the whole scan.
        sync.sync_all(db)
        db.flush()

    created, scanned = findings.detect_findings(db)
    run.tables_scanned = scanned
    run.findings_created = created
    db.flush()

    if investigate:
        from ..config import openai_api_key
        from . import agents

        # "Always use LLM": only investigate when a key is configured.
        if openai_api_key():
            _ = agents.investigate_all_open(db)

    health.compute_health(db)

    run.status = "SUCCEEDED"
    run.finished_at = _now()
    db.commit()
    db.refresh(run)
    return run
