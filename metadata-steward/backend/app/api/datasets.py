"""Dataset hierarchy + editable business context + per-dataset metrics."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..config import openai_api_key
from ..models import (
    CatalogTable,
    DatasetContext,
    DatasetContextVersion,
    Finding,
    MetadataSource,
    Recommendation,
)
from ..schemas import (
    DatasetContextOut,
    DatasetContextUpdate,
    DatasetContextVersionOut,
    DatasetMetrics,
    DatasetOut,
    DatasetSchemaRef,
    DatasetTableRef,
    FindingRef,
    GenerateContextRequest,
    RestoreContextRequest,
    SourceRef,
)
from ..services import health as health_service

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

_OPEN_STATUSES = ("OPEN", "INVESTIGATING", "RECOMMENDED")


def _context_out(ctx: DatasetContext | None) -> DatasetContextOut | None:
    if ctx is None:
        return None
    return DatasetContextOut(
        key=ctx.key,
        description=ctx.description,
        table_instructions=ctx.table_instructions,
        column_instructions=ctx.column_instructions,
        dataset_instructions=ctx.dataset_instructions,
        source=ctx.source,
        version=ctx.version,
        updated_at=ctx.updated_at,
    )


def _metrics(db: Session, findings: list[Finding], tables: list[CatalogTable]) -> DatasetMetrics:
    overall, _ = health_service.compute_health_for_tables(tables)

    open_findings = sum(1 for f in findings if f.status in _OPEN_STATUSES)
    by_severity = Counter(f.severity for f in findings)
    by_type = Counter(f.type for f in findings)

    finding_ids = [f.id for f in findings]
    pending = 0
    applied = 0
    if finding_ids:
        pending = (
            db.query(Recommendation)
            .filter(
                Recommendation.finding_id.in_(finding_ids),
                Recommendation.status == "PENDING",
            )
            .count()
        )
        applied = (
            db.query(Recommendation)
            .filter(
                Recommendation.finding_id.in_(finding_ids),
                Recommendation.status == "APPLIED",
            )
            .count()
        )

    described_tables = sum(1 for t in tables if t.description and t.description.strip())
    described_columns = sum(
        1 for t in tables for c in t.columns if c.description and c.description.strip()
    )
    return DatasetMetrics(
        health=round(overall * 100, 1),
        tables=len(tables),
        columns=sum(len(t.columns) for t in tables),
        described_tables=described_tables,
        described_columns=described_columns,
        open_findings=open_findings,
        pending_approvals=pending,
        auto_resolved=applied,
        findings_by_severity=dict(by_severity),
        findings_by_type=dict(by_type),
    )


@router.get("", response_model=list[DatasetOut])
def list_datasets(db: Session = Depends(get_db)):
    tables = db.query(CatalogTable).order_by(CatalogTable.fqn).all()

    grouped: dict[str, dict] = {}
    for t in tables:
        key = f"{t.service_name}.{t.database_name}"
        if key not in grouped:
            grouped[key] = {
                "service": t.service_name,
                "database": t.database_name,
                "schemas": {},
                "tables": [],
            }
        grouped[key]["schemas"].setdefault(t.schema_name, []).append(t)
        grouped[key]["tables"].append(t)

    out: list[DatasetOut] = []
    for key, g in grouped.items():
        service, database = g["service"], g["database"]
        prefix = f"{service}.{database}."
        findings = (
            db.query(Finding).filter(Finding.entity.like(f"{prefix}%")).all()
        )

        ctx = db.query(DatasetContext).filter(DatasetContext.key == key).first()
        schemas: list[DatasetSchemaRef] = []
        for sname, stables in g["schemas"].items():
            schemas.append(
                DatasetSchemaRef(
                    name=sname,
                    tables=[_table_ref(t, findings) for t in stables],
                )
            )
        sources = [
            SourceRef(
                id=s.id,
                name=s.name,
                kind=s.kind,
                connection=s.connection,
                status=s.status,
                document_count=s.document_count,
                fact_count=s.fact_count,
                schedule_enabled=s.schedule_enabled,
                last_sync_at=s.last_sync_at,
                updated_at=s.updated_at,
            )
            for s in db.query(MetadataSource)
            .filter(MetadataSource.dataset_key == key)
            .order_by(MetadataSource.created_at.desc())
            .all()
        ]
        first = g["tables"][0] if g["tables"] else None
        tool = first.tool if first else None
        out.append(
            DatasetOut(
                key=key,
                service=service,
                database=database,
                tool_id=tool.id if tool else None,
                tool_name=tool.name if tool else None,
                tool_type=tool.type if tool else None,
                schemas=schemas,
                context=_context_out(ctx),
                metrics=_metrics(db, findings, g["tables"]),
                sources=sources,
            )
        )
    return out


def _table_ref(t: CatalogTable, findings: list[Finding]) -> DatasetTableRef:
    refs = [
        FindingRef(id=f.id, type=f.type, entity=f.entity)
        for f in findings
        if f.status in _OPEN_STATUSES
        and (f.entity == t.fqn or f.entity.startswith(f"{t.fqn}."))
    ]
    return DatasetTableRef(
        fqn=t.fqn,
        name=t.name,
        description=t.description,
        owner=t.owner.name if t.owner else None,
        domain=t.domain.name if t.domain else None,
        column_count=len(t.columns),
        findings=refs,
    )


def _archive(db: Session, ctx: DatasetContext) -> None:
    db.add(
        DatasetContextVersion(
            key=ctx.key,
            version=ctx.version,
            description=ctx.description,
            table_instructions=ctx.table_instructions,
            column_instructions=ctx.column_instructions,
            dataset_instructions=ctx.dataset_instructions,
            source=ctx.source,
        )
    )


@router.put("/{key}/context", response_model=DatasetContextOut)
def save_context(key: str, body: DatasetContextUpdate, db: Session = Depends(get_db)):
    ctx = db.query(DatasetContext).filter(DatasetContext.key == key).first()
    if ctx is None:
        ctx = DatasetContext(
            key=key,
            description=body.description,
            table_instructions=body.table_instructions,
            column_instructions=body.column_instructions,
            dataset_instructions=body.dataset_instructions,
            source=body.source,
            version=1,
        )
        db.add(ctx)
    else:
        _archive(db, ctx)
        ctx.description = body.description
        ctx.table_instructions = body.table_instructions
        ctx.column_instructions = body.column_instructions
        ctx.dataset_instructions = body.dataset_instructions
        ctx.source = body.source
        ctx.version += 1
    db.commit()
    db.refresh(ctx)
    return _context_out(ctx)


@router.post("/{key}/generate-context", response_model=DatasetContextOut)
def generate_context(key: str, body: GenerateContextRequest, db: Session = Depends(get_db)):
    if not openai_api_key():
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key is not configured. Add it in Settings → OpenAI API Key.",
        )
    try:
        service, database = key.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset key")

    tables = (
        db.query(CatalogTable)
        .filter(
            CatalogTable.service_name == service,
            CatalogTable.database_name == database,
        )
        .order_by(CatalogTable.name)
        .all()
    )
    if not tables:
        raise HTTPException(status_code=404, detail="Dataset not found")

    from ..services.llm import get_llm

    table_list = [
        {"name": t.name, "columns": [c.name for c in t.columns]} for t in tables
    ]
    existing = db.query(DatasetContext).filter(DatasetContext.key == key).first()
    instructions = (
        body.dataset_instructions
        or (existing.dataset_instructions if existing else "")
    )
    draft = get_llm().generate_dataset_context(
        dataset_name=database, tables=table_list, instructions=instructions or None
    )

    ctx = existing
    if ctx is None:
        ctx = DatasetContext(key=key, description=draft.text, source="ai", version=1)
        db.add(ctx)
    else:
        _archive(db, ctx)
        ctx.description = draft.text
        ctx.source = "ai"
        ctx.version += 1
    db.commit()
    db.refresh(ctx)
    return _context_out(ctx)


@router.post("/{key}/regenerate")
def regenerate(key: str, db: Session = Depends(get_db)):
    """Regenerate table/column description suggestions for this dataset using
    the current dataset context. Returns a report of every old -> new change."""
    if not openai_api_key():
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key is not configured. Add it in Settings → OpenAI API Key.",
        )
    try:
        service, database = key.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid dataset key")

    from ..services import agents, health

    prefix = f"{service}.{database}."
    findings = db.query(Finding).filter(Finding.entity.like(f"{prefix}%")).all()

    # Capture previous suggestions before superseding them.
    old_by_finding: dict[str, dict] = {}
    for f in findings:
        if f.status in ("RESOLVED", "REJECTED"):
            continue
        f.status = "OPEN"
        for r in list(f.recommendations):
            if r.status == "PENDING":
                old_by_finding[f.id] = {
                    "old_value": r.new_value,
                    "old_version": r.version,
                }
                r.status = "SUPERSEDED"
    db.commit()

    _, errors = agents.investigate_all_open(db)
    health.compute_health(db)
    db.commit()

    if errors:
        raise HTTPException(status_code=400, detail=errors[0])

    # Build the old -> new report.
    changes: list[dict] = []
    for f in findings:
        if f.id not in old_by_finding:
            continue
        recs = sorted(f.recommendations, key=lambda r: -r.version)
        new = next((r for r in recs if r.status == "PENDING"), recs[0] if recs else None)
        if new:
            changes.append(
                {
                    "entity": f.entity,
                    "field": new.field,
                    "old_value": old_by_finding[f.id]["old_value"],
                    "old_version": old_by_finding[f.id]["old_version"],
                    "new_value": new.new_value,
                    "new_version": new.version,
                }
            )

    return {"regenerated": len(changes), "changes": changes}


@router.get("/{key}/context/history", response_model=list[DatasetContextVersionOut])
def context_history(key: str, db: Session = Depends(get_db)):
    """List all context versions (current + archived), newest first."""
    versions: list[DatasetContextVersionOut] = []
    ctx = db.query(DatasetContext).filter(DatasetContext.key == key).first()
    if ctx:
        versions.append(
            DatasetContextVersionOut(
                version=ctx.version,
                description=ctx.description,
                table_instructions=ctx.table_instructions,
                column_instructions=ctx.column_instructions,
                dataset_instructions=ctx.dataset_instructions,
                source=ctx.source,
                created_at=ctx.updated_at,
            )
        )
    for v in (
        db.query(DatasetContextVersion)
        .filter(DatasetContextVersion.key == key)
        .order_by(DatasetContextVersion.version.desc())
        .all()
    ):
        versions.append(
            DatasetContextVersionOut(
                version=v.version,
                description=v.description,
                table_instructions=v.table_instructions,
                column_instructions=v.column_instructions,
                dataset_instructions=v.dataset_instructions,
                source=v.source,
                created_at=v.created_at,
            )
        )
    return versions


@router.post("/{key}/context/restore", response_model=DatasetContextOut)
def restore_context(key: str, body: RestoreContextRequest, db: Session = Depends(get_db)):
    """Restore a previous context version as the current one (new version)."""
    ctx = db.query(DatasetContext).filter(DatasetContext.key == key).first()
    if ctx and ctx.version == body.version:
        return _context_out(ctx)

    target = (
        db.query(DatasetContextVersion)
        .filter(
            DatasetContextVersion.key == key,
            DatasetContextVersion.version == body.version,
        )
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Context version not found")

    if ctx is None:
        ctx = DatasetContext(key=key, source=target.source, version=1)
        db.add(ctx)
    else:
        _archive(db, ctx)
        ctx.version += 1

    ctx.description = target.description
    ctx.table_instructions = target.table_instructions
    ctx.column_instructions = target.column_instructions
    ctx.dataset_instructions = target.dataset_instructions
    ctx.source = target.source
    db.commit()
    db.refresh(ctx)
    return _context_out(ctx)
