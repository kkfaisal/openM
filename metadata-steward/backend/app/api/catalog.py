"""Catalog (system of record) read endpoints + description generation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import CatalogTable, Finding
from ..schemas import (
    CatalogDomainOut,
    CatalogTableOut,
    FindingDetail,
    GenerateClassificationRequest,
    GenerateDescriptionRequest,
)
from ..services import agents, catalog
from ..services.flags import get_bool_flag
from ..services.llm import PromptOverride

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/domains", response_model=list[CatalogDomainOut])
def domains(db: Session = Depends(get_db)):
    return catalog.list_domains(db)


@router.get("/tables", response_model=list[CatalogTableOut])
def tables(
    domain: str | None = None,
    service: str | None = None,
    schema: str | None = None,
    q: str | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    rows = catalog.list_tables(
        db, domain=domain, service=service, schema=schema, q=q, limit=limit
    )
    return [_serialize_table(t) for t in rows]


@router.get("/tables/{fqn}", response_model=CatalogTableOut)
def get_table(fqn: str, db: Session = Depends(get_db)):
    table = (
        db.query(CatalogTable)
        .options(selectinload(CatalogTable.columns))
        .filter(CatalogTable.fqn == fqn)
        .first()
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return _serialize_table(table)


@router.post("/tables/{fqn}/generate-description", response_model=FindingDetail)
def generate_description(
    fqn: str, body: GenerateDescriptionRequest | None = None, db: Session = Depends(get_db)
):
    """Generate (or regenerate) a description recommendation for a table or a
    single column — including when a description already exists."""
    table = (
        db.query(CatalogTable)
        .options(selectinload(CatalogTable.columns))
        .filter(CatalogTable.fqn == fqn)
        .first()
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")

    column_name = (body.column if body else None) or None
    if column_name:
        col = next((c for c in table.columns if c.name == column_name), None)
        if col is None:
            raise HTTPException(status_code=404, detail="Column not found")
        finding = _ensure_generation_finding(
            db,
            type="MISSING_COLUMN_DESCRIPTION",
            severity="LOW",
            entity=f"{fqn}.{column_name}",
            entity_type="column",
            domain=table.domain.name if table.domain else None,
            summary=f"Generate a description for column '{column_name}'.",
            agent="ColumnDescriptionAgent",
        )
    else:
        finding = _ensure_generation_finding(
            db,
            type="MISSING_DESCRIPTION",
            severity="MEDIUM",
            entity=fqn,
            entity_type="table",
            domain=table.domain.name if table.domain else None,
            summary=f"Generate a description for table '{fqn}'.",
            agent="DescriptionAgent",
        )

    try:
        # Never auto-apply on explicit generate/regenerate — always route to
        # the approval modal so a human reviews and applies it.
        agents.investigate(
            db, finding, auto_apply=False, prompt_override=_prompt_override(db, body)
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    finding = (
        db.query(Finding)
        .options(selectinload(Finding.evidence), selectinload(Finding.recommendations))
        .filter(Finding.id == finding.id)
        .first()
    )
    return finding


@router.post("/tables/{fqn}/generate-classification", response_model=FindingDetail)
def generate_classification(
    fqn: str, body: GenerateClassificationRequest, db: Session = Depends(get_db)
):
    """Generate (or regenerate) a classification recommendation for a column —
    including when a classification already exists. Always routed to approval."""
    table = (
        db.query(CatalogTable)
        .options(selectinload(CatalogTable.columns))
        .filter(CatalogTable.fqn == fqn)
        .first()
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")

    column_name = (body.column or "").strip()
    col = next((c for c in table.columns if c.name == column_name), None)
    if col is None:
        raise HTTPException(status_code=404, detail="Column not found")

    finding = _ensure_generation_finding(
        db,
        type="MISSING_CLASSIFICATION",
        severity="HIGH",
        entity=f"{fqn}.{column_name}",
        entity_type="column",
        domain=table.domain.name if table.domain else None,
        summary=f"Generate a classification for column '{column_name}'.",
        agent="ClassificationAgent",
    )
    try:
        agents.investigate(
            db, finding, auto_apply=False, prompt_override=_prompt_override(db, body)
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e

    finding = (
        db.query(Finding)
        .options(selectinload(Finding.evidence), selectinload(Finding.recommendations))
        .filter(Finding.id == finding.id)
        .first()
    )
    return finding


def _prompt_override(db: Session, body) -> PromptOverride | None:
    """Return a prompt override only when the global flag is on and a prompt
    override was actually provided in the request."""
    if not get_bool_flag(db, "enable_prompt_editing"):
        return None
    if body is None or (body.system_prompt is None and body.user_prompt is None):
        return None
    return PromptOverride(
        system_prompt=body.system_prompt, user_prompt=body.user_prompt
    )


def _ensure_generation_finding(
    db: Session,
    *,
    type: str,
    severity: str,
    entity: str,
    entity_type: str,
    domain: str | None,
    summary: str,
    agent: str,
) -> Finding:
    """Reuse the active finding for this entity, or create one; then reset it
    to OPEN (superseding any pending recommendation) so it can be regenerated."""
    finding = (
        db.query(Finding)
        .filter(
            Finding.type == type,
            Finding.entity == entity,
            Finding.status.in_(["OPEN", "INVESTIGATING", "RECOMMENDED"]),
        )
        .first()
    )
    if finding is None:
        # Reuse the most recently closed finding for this entity so version
        # history stays continuous when regenerating a description that was
        # already applied (otherwise every regenerate restarts at v1).
        finding = (
            db.query(Finding)
            .filter(Finding.type == type, Finding.entity == entity)
            .order_by(Finding.detected_at.desc())
            .first()
        )
    if finding is None:
        finding = Finding(
            type=type,
            severity=severity,
            entity=entity,
            entity_type=entity_type,
            domain=domain,
            status="OPEN",
            summary=summary,
            agent=agent,
        )
        db.add(finding)
        db.flush()
        return finding

    for rec in list(finding.recommendations):
        if rec.status == "PENDING":
            rec.status = "SUPERSEDED"
    finding.status = "OPEN"
    finding.resolved_at = None
    db.flush()
    return finding


def _serialize_table(t: CatalogTable) -> CatalogTableOut:
    return CatalogTableOut(
        id=t.id,
        fqn=t.fqn,
        name=t.name,
        service_name=t.service_name,
        database_name=t.database_name,
        schema_name=t.schema_name,
        description=t.description,
        domain=t.domain.name if t.domain else None,
        owner=t.owner.name if t.owner else None,
        tags=t.tags or [],
        row_count=t.row_count,
        last_queried_at=t.last_queried_at,
        columns=[
            {
                "id": c.id,
                "name": c.name,
                "data_type": c.data_type,
                "description": c.description,
                "classification": c.classification,
                "tags": c.tags or [],
                "position": c.position,
            }
            for c in sorted(t.columns, key=lambda x: x.position)
        ],
    )
