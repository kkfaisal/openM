"""Metadata-source endpoints: connect channels under a dataset, ingest,
extract, and inspect the extracted knowledge."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CatalogTable, ExtractedFact, MetadataSource, SourceDocument
from ..schemas import (
    ExtractedFactOut,
    SourceConnectRequest,
    SourceDetail,
    SourceDocumentOut,
    SourceExtractResult,
    SourceOut,
    SourceScheduleUpdate,
)
from ..services import sources as sources_service

router = APIRouter(prefix="/api", tags=["sources"])


def _dataset_exists(db: Session, key: str) -> bool:
    try:
        service, database = key.split(".", 1)
    except ValueError:
        return False
    return (
        db.query(CatalogTable)
        .filter(
            CatalogTable.service_name == service,
            CatalogTable.database_name == database,
        )
        .first()
        is not None
    )


def _source_out(source: MetadataSource) -> SourceOut:
    return SourceOut(
        id=source.id,
        name=source.name,
        kind=source.kind,
        connection=source.connection,
        status=source.status,
        document_count=source.document_count,
        fact_count=source.fact_count,
        schedule_enabled=source.schedule_enabled,
        dataset_key=source.dataset_key,
        config=sources_service._mask_config(source.config),
        error=source.error,
        interval_minutes=source.interval_minutes,
        last_sync_at=source.last_sync_at,
        next_sync_at=source.next_sync_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
        summary=source.summary,
    )


@router.get("/datasets/{key}/sources", response_model=list[SourceOut])
def list_sources(key: str, db: Session = Depends(get_db)):
    sources = (
        db.query(MetadataSource)
        .filter(MetadataSource.dataset_key == key)
        .order_by(MetadataSource.created_at.desc())
        .all()
    )
    return [_source_out(s) for s in sources]


@router.post("/datasets/{key}/sources/upload", response_model=SourceOut)
async def upload_source(
    key: str,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    name: str = Form(""),
):
    if not _dataset_exists(db, key):
        raise HTTPException(status_code=404, detail="Dataset not found")
    raw = await file.read()
    try:
        source = sources_service.create_from_upload(
            db,
            dataset_key=key,
            name=name.strip() or (file.filename or "Upload"),
            filename=file.filename or "upload",
            file_bytes=raw,
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _source_out(source)


@router.post("/datasets/{key}/sources", response_model=SourceOut)
def connect_source(key: str, body: SourceConnectRequest, db: Session = Depends(get_db)):
    if not _dataset_exists(db, key):
        raise HTTPException(status_code=404, detail="Dataset not found")
    if body.kind not in ("slack", "teams"):
        raise HTTPException(status_code=400, detail="Only slack/teams API connection is supported here")
    source = sources_service.create_from_api(
        db,
        dataset_key=key,
        name=body.name,
        kind=body.kind,
        config=body.config,
        schedule_enabled=body.schedule_enabled,
        interval_minutes=body.interval_minutes,
    )
    return _source_out(source)


@router.post("/webhooks/{dataset_key}", response_model=SourceOut)
def webhook_ingest(dataset_key: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    """Ingest data pushed from an external system via a per-dataset webhook.

    Accepts our simple ``{"text": ...}`` format, a Slack Events API message, or
    a Teams message. Each POST appends a document to a webhook source (scoped
    by dataset + name + kind) and re-runs extraction.
    """
    if not _dataset_exists(db, dataset_key):
        raise HTTPException(status_code=404, detail="Dataset not found")
    data = sources_service.normalize_webhook_payload(payload)
    if not data["text"]:
        raise HTTPException(status_code=400, detail="A non-empty 'text' field is required")
    source = sources_service.ingest_webhook(
        db,
        dataset_key=dataset_key,
        name=data["name"],
        kind=data["kind"],
        text=data["text"],
        author=data["author"],
        channel=data["channel"],
    )
    return _source_out(source)


@router.get("/sources/{id}", response_model=SourceDetail)
def get_source(id: str, db: Session = Depends(get_db)):
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    facts = (
        db.query(ExtractedFact)
        .filter(ExtractedFact.source_id == id)
        .order_by(ExtractedFact.created_at.desc())
        .all()
    )
    documents = (
        db.query(SourceDocument)
        .filter(SourceDocument.source_id == id)
        .order_by(SourceDocument.ingested_at.asc())
        .limit(200)
        .all()
    )
    return SourceDetail(
        **_source_out(source).model_dump(),
        facts=[ExtractedFactOut.model_validate(f) for f in facts],
        documents=[SourceDocumentOut.model_validate(d) for d in documents],
    )


@router.get("/sources/{id}/documents", response_model=list[SourceDocumentOut])
def list_documents(
    id: str, q: str = "", limit: int = 200, db: Session = Depends(get_db)
):
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    query = db.query(SourceDocument).filter(SourceDocument.source_id == id)
    if q:
        query = query.filter(SourceDocument.content.ilike(f"%{q}%"))
    return [
        SourceDocumentOut.model_validate(d)
        for d in query.order_by(SourceDocument.ingested_at.asc()).limit(min(limit, 1000)).all()
    ]


@router.get("/sources/{id}/facts", response_model=list[ExtractedFactOut])
def list_facts(id: str, db: Session = Depends(get_db)):
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    facts = (
        db.query(ExtractedFact)
        .filter(ExtractedFact.source_id == id)
        .order_by(ExtractedFact.created_at.desc())
        .all()
    )
    return [ExtractedFactOut.model_validate(f) for f in facts]


@router.post("/sources/{id}/extract", response_model=SourceExtractResult)
def extract_source(id: str, db: Session = Depends(get_db)):
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    try:
        n = sources_service.reextract(db, source)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return SourceExtractResult(
        source=_source_out(db.get(MetadataSource, id)),
        documents=source.document_count,
        facts=n,
    )


@router.post("/sources/{id}/sync", response_model=SourceOut)
def sync_source(id: str, db: Session = Depends(get_db)):
    """CDC sync: pull only new/changed messages since the last watermark."""
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.connection != "api":
        raise HTTPException(status_code=400, detail="Only Slack/Teams API sources can be synced")
    try:
        sources_service.sync_source(db, source)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _source_out(db.get(MetadataSource, id))


@router.put("/sources/{id}/schedule", response_model=SourceOut)
def schedule_source(id: str, body: SourceScheduleUpdate, db: Session = Depends(get_db)):
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.connection != "api":
        raise HTTPException(status_code=400, detail="Only Slack/Teams API sources can be scheduled")
    source = sources_service.set_schedule(
        db, source, enabled=body.enabled, interval_minutes=body.interval_minutes
    )
    return _source_out(source)


@router.delete("/sources/{id}", status_code=204)
def delete_source(id: str, db: Session = Depends(get_db)):
    source = db.get(MetadataSource, id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    sources_service.delete_source(db, source)
    return None
