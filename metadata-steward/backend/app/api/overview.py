"""Overview / dashboard endpoint."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    AgentRun,
    AuditEvent,
    CatalogColumn,
    CatalogDomain,
    CatalogTable,
    Finding,
    HealthSnapshot,
    MetadataChange,
    Recommendation,
)
from ..schemas import OverviewStats
from ..services import catalog

router = APIRouter(prefix="/api", tags=["overview"])


@router.get("/overview", response_model=OverviewStats)
def overview(db: Session = Depends(get_db)) -> OverviewStats:
    total_tables = catalog.count_tables(db)
    total_columns = catalog.count_columns(db)

    open_findings = (
        db.query(Finding)
        .filter(Finding.status.in_(["OPEN", "INVESTIGATING", "RECOMMENDED"]))
        .count()
    )

    severity_rows = (
        db.query(Finding.severity, func.count(Finding.id))
        .group_by(Finding.severity)
        .all()
    )
    findings_by_severity = {s: c for s, c in severity_rows}

    type_rows = (
        db.query(Finding.type, func.count(Finding.id))
        .group_by(Finding.type)
        .all()
    )
    findings_by_type = dict(type_rows)

    pending_approvals = (
        db.query(Recommendation)
        .filter(Recommendation.status == "PENDING")
        .count()
    )
    auto_resolved = (
        db.query(Recommendation).filter(Recommendation.status == "APPLIED").count()
    )
    recommendations_total = db.query(Recommendation).count()
    agent_runs = db.query(AgentRun).count()

    changes_last_7d = (
        db.query(MetadataChange)
        .filter(MetadataChange.applied_at >= _cutoff(7))
        .count()
    )

    stale_assets = catalog.count_stale_tables(db)
    sensitive_findings = (
        db.query(Finding).filter(Finding.type == "MISSING_CLASSIFICATION").count()
    )

    # Domains + health-ish table counts
    domains: list[dict] = []
    for dom in db.query(CatalogDomain).order_by(CatalogDomain.name).all():
        tcount = (
            db.query(CatalogTable).filter(CatalogTable.domain_id == dom.id).count()
        )
        missing_owner = (
            db.query(CatalogTable)
            .filter(
                CatalogTable.domain_id == dom.id,
                CatalogTable.owner_team_id.is_(None),
            )
            .count()
        )
        missing_desc = (
            db.query(CatalogTable)
            .filter(
                CatalogTable.domain_id == dom.id,
                CatalogTable.description.is_(None),
            )
            .count()
        )
        domains.append(
            {
                "name": dom.name,
                "display_name": dom.display_name,
                "tables": tcount,
                "missing_owner": missing_owner,
                "missing_description": missing_desc,
            }
        )

    recent_actions = []
    for ev in (
        db.query(AuditEvent)
        .order_by(desc(AuditEvent.timestamp))
        .limit(10)
        .all()
    ):
        recent_actions.append(
            {
                "id": ev.id,
                "action": ev.action,
                "actor": ev.actor,
                "entity": ev.entity,
                "field": ev.field,
                "new_value": ev.new_value,
                "timestamp": ev.timestamp.isoformat(),
            }
        )

    snapshots = (
        db.query(HealthSnapshot)
        .order_by(HealthSnapshot.created_at.asc())
        .all()
    )
    trend = [
        {
            "overall": round(s.overall * 100, 1),
            "created_at": s.created_at.isoformat(),
        }
        for s in snapshots
    ]

    health = snapshots[-1].overall if snapshots else 0.0
    health_delta = 0.0
    if len(snapshots) >= 2:
        health_delta = snapshots[-1].overall - snapshots[-2].overall

    return OverviewStats(
        health=round(health * 100, 1),
        health_delta=round(health_delta * 100, 1),
        total_tables=total_tables,
        total_columns=total_columns,
        open_findings=open_findings,
        findings_by_severity=findings_by_severity,
        findings_by_type=findings_by_type,
        pending_approvals=pending_approvals,
        auto_resolved=auto_resolved,
        recommendations_total=recommendations_total,
        agent_runs=agent_runs,
        changes_last_7d=changes_last_7d,
        stale_assets=stale_assets,
        sensitive_findings=sensitive_findings,
        domains=domains,
        recent_actions=recent_actions,
        trend=trend,
    )


def _cutoff(days: int):
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
