"""Metadata-tool connections (OpenMetadata, Amundsen, DataHub, ...).

OpenMetadata flow:  test connection → save (credentials encrypted) → browse
services/databases/schemas → import selected databases as datasets → sync.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CatalogTable, Finding, MetadataTool, ToolDataset
from ..schemas import (
    BrowseDatabase,
    BrowseSchema,
    BrowseService,
    DatasetImportRequest,
    DatasetImportResult,
    MetadataToolOut,
    ToolAuth,
    ToolAuthOut,
    ToolCreate,
    ToolDatasetOut,
    ToolDatasetUpdate,
    ToolTestRequest,
    ToolTestResult,
    ToolUpdate,
)
from ..services import audit, findings as findings_service, health
from ..services import secrets, sync
from ..services import tools as tools_service
from ..services.openmetadata_client import (
    OpenMetadataError,
    client_for_tool,
    client_from_config,
    reset_client,
)

router = APIRouter(prefix="/api/tools", tags=["tools"])

LIVE_TYPES = {"openmetadata"}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def _ds_out(ds: ToolDataset) -> ToolDatasetOut:
    return ToolDatasetOut(
        id=ds.id,
        tool_id=ds.tool_id,
        service_name=ds.service_name,
        database_name=ds.database_name,
        dataset_key=ds.dataset_key,
        display_name=ds.display_name,
        schemas=list(ds.schemas or []),
        status=ds.status,
        error=ds.error,
        table_count=ds.table_count,
        last_synced_at=ds.last_synced_at,
        created_at=ds.created_at,
    )


def _auth_out(tool: MetadataTool) -> ToolAuthOut:
    auth = (tool.config or {}).get("auth") or {}
    kind = auth.get("type") or ("env" if tool.is_default else "none")
    hint = auth.get("token_hint")
    return ToolAuthOut(
        type=kind,
        email=auth.get("email"),
        token_hint=hint,
        has_secret=bool(auth.get("token_enc") or auth.get("password_enc")),
    )


def _tool_out(db: Session, tool: MetadataTool) -> MetadataToolOut:
    datasets = sorted(tool.datasets, key=lambda d: d.dataset_key)
    if tool.type in LIVE_TYPES:
        count = len(datasets)
    else:
        count = (
            db.query(CatalogTable.service_name, CatalogTable.database_name)
            .filter(CatalogTable.tool_id == tool.id)
            .distinct()
            .count()
        )
    return MetadataToolOut(
        id=tool.id,
        name=tool.name,
        type=tool.type,
        host=tool.host,
        auth=_auth_out(tool),
        verify_ssl=bool((tool.config or {}).get("verify_ssl", True)),
        status=tool.status,
        last_error=tool.last_error,
        last_checked_at=tool.last_checked_at,
        is_default=tool.is_default,
        dataset_count=count,
        datasets=[_ds_out(d) for d in datasets],
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


# --------------------------------------------------------------------------- #
# Credentials
# --------------------------------------------------------------------------- #
def _auth_config(auth: ToolAuth | None, previous: dict | None = None) -> dict:
    """Encrypt the submitted auth; keep the stored secret when left blank."""
    prev = (previous or {}).get("auth") or {}
    if auth is None:
        return prev
    if auth.type == "jwt":
        token = (auth.token or "").strip()
        if token:
            return {
                "type": "jwt",
                "token_enc": secrets.encrypt(token),
                "token_hint": secrets.mask(token),
            }
        if prev.get("type") == "jwt" and prev.get("token_enc"):
            return prev
        raise HTTPException(status_code=400, detail="A bot token is required.")
    if auth.type == "basic":
        email = (auth.email or "").strip()
        if not email:
            raise HTTPException(status_code=400, detail="Email is required.")
        if auth.password:
            return {"type": "basic", "email": email, "password_enc": secrets.encrypt(auth.password)}
        if prev.get("type") == "basic" and prev.get("password_enc"):
            return {**prev, "email": email}
        raise HTTPException(status_code=400, detail="Password is required.")
    return {}


def _normalize_host(host: str | None) -> str:
    h = (host or "").strip().rstrip("/")
    if h.endswith("/api"):
        h = h[: -len("/api")]
    if h and not h.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Host must start with http:// or https://")
    return h


def _test(host: str, config: dict) -> ToolTestResult:
    try:
        client = client_from_config(host, config)
        info = client.version()
        services = len(client.list_database_services())
        return ToolTestResult(
            ok=True,
            version=str(info.get("version") or "") or None,
            services=services,
            message=f"Connected to OpenMetadata {info.get('version', '')}. "
            f"Found {services} database service{'s' if services != 1 else ''}.",
        )
    except OpenMetadataError as e:
        return ToolTestResult(ok=False, message=str(e))


def _get_tool(db: Session, tool_id: str) -> MetadataTool:
    tool = db.get(MetadataTool, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


def _require_live(tool: MetadataTool) -> None:
    if tool.type not in LIVE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Live browsing is not available for {tool.type} yet.",
        )


# --------------------------------------------------------------------------- #
# CRUD + test
# --------------------------------------------------------------------------- #
@router.get("", response_model=list[MetadataToolOut])
def list_tools(db: Session = Depends(get_db)):
    tools = (
        db.query(MetadataTool)
        .order_by(MetadataTool.is_default.desc(), MetadataTool.name.asc())
        .all()
    )
    return [_tool_out(db, t) for t in tools]


@router.post("/test", response_model=ToolTestResult)
def test_connection(body: ToolTestRequest, db: Session = Depends(get_db)):
    if body.type not in LIVE_TYPES:
        return ToolTestResult(ok=False, message=f"No live connector for {body.type} yet.")
    host = _normalize_host(body.host)
    if not host:
        raise HTTPException(status_code=400, detail="Host URL is required.")
    previous = None
    if body.tool_id:
        previous = _get_tool(db, body.tool_id).config
    config = {"auth": _auth_config(body.auth, previous), "verify_ssl": body.verify_ssl}
    return _test(host, config)


@router.post("", response_model=MetadataToolOut)
def create_tool(body: ToolCreate, db: Session = Depends(get_db)):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Connection name is required")
    if db.query(MetadataTool).filter(MetadataTool.name == name).first():
        raise HTTPException(status_code=400, detail="A connection with this name already exists")

    if body.type in LIVE_TYPES:
        host = _normalize_host(body.host)
        if not host:
            raise HTTPException(status_code=400, detail="Host URL is required.")
        config = {"auth": _auth_config(body.auth), "verify_ssl": body.verify_ssl}
        result = _test(host, config)
        if not result.ok:
            raise HTTPException(status_code=400, detail=f"Connection test failed: {result.message}")
        tool = MetadataTool(
            name=name,
            type=body.type,
            host=host,
            config=config,
            status="CONNECTED",
            last_checked_at=_now(),
            is_default=False,
        )
        db.add(tool)
    else:
        # No live connector yet: register it; sample data only on request.
        tool = MetadataTool(
            name=name,
            type=body.type or "custom",
            host=(body.host or "").strip() or None,
            config={},
            status="DEMO" if body.seed_demo else "PENDING",
            is_default=False,
        )
        db.add(tool)
        db.flush()
        if body.seed_demo:
            tools_service.seed_demo_catalog(db, tool)
    db.flush()
    audit.record(
        db,
        action="TOOL_CONNECTED",
        actor="Demo Steward",
        actor_type="human",
        detail=f"Added {body.type} connection '{name}' ({tool.host or 'no host'}).",
    )
    db.commit()
    db.refresh(tool)
    return _tool_out(db, tool)


@router.put("/{tool_id}", response_model=MetadataToolOut)
def update_tool(tool_id: str, body: ToolUpdate, db: Session = Depends(get_db)):
    tool = _get_tool(db, tool_id)
    if body.name is not None and body.name.strip() and body.name.strip() != tool.name:
        if db.query(MetadataTool).filter(MetadataTool.name == body.name.strip()).first():
            raise HTTPException(status_code=400, detail="A connection with this name already exists")
        tool.name = body.name.strip()
    if tool.type in LIVE_TYPES and (body.host is not None or body.auth is not None or body.verify_ssl is not None):
        host = _normalize_host(body.host) if body.host is not None else tool.host or ""
        verify = body.verify_ssl if body.verify_ssl is not None else bool((tool.config or {}).get("verify_ssl", True))
        config = {"auth": _auth_config(body.auth, tool.config), "verify_ssl": verify}
        result = _test(host, config)
        if not result.ok:
            raise HTTPException(status_code=400, detail=f"Connection test failed: {result.message}")
        tool.host = host
        tool.config = config
        tool.status = "CONNECTED"
        tool.last_error = None
        tool.last_checked_at = _now()
    tool.updated_at = _now()
    reset_client(tool.id)
    db.commit()
    db.refresh(tool)
    return _tool_out(db, tool)


@router.post("/{tool_id}/check", response_model=ToolTestResult)
def check_tool(tool_id: str, db: Session = Depends(get_db)):
    """Re-test a saved connection and record the result."""
    tool = _get_tool(db, tool_id)
    _require_live(tool)
    reset_client(tool.id)
    result = _test(tool.host or "", tool.config or {})
    tool.status = "CONNECTED" if result.ok else "ERROR"
    tool.last_error = None if result.ok else result.message
    tool.last_checked_at = _now()
    db.commit()
    return result


@router.delete("/{tool_id}", status_code=204)
def delete_tool(tool_id: str, db: Session = Depends(get_db)):
    tool = _get_tool(db, tool_id)
    if tool.is_default:
        raise HTTPException(status_code=400, detail="The default connection cannot be deleted")

    for ds in list(tool.datasets):
        sync.remove_dataset(db, ds)
    # Non-live tools: remove their seeded tables and findings.
    fqns = [t.fqn for t in db.query(CatalogTable).filter(CatalogTable.tool_id == tool_id).all()]
    for fqn in fqns:
        db.query(Finding).filter(
            (Finding.entity == fqn) | Finding.entity.like(f"{fqn}.%")
        ).delete(synchronize_session=False)
    db.query(CatalogTable).filter(CatalogTable.tool_id == tool_id).delete(synchronize_session=False)
    audit.record(
        db,
        action="TOOL_REMOVED",
        actor="Demo Steward",
        actor_type="human",
        detail=f"Removed connection '{tool.name}'. OpenMetadata itself was not changed.",
    )
    db.delete(tool)
    reset_client(tool_id)
    db.commit()
    return None


# --------------------------------------------------------------------------- #
# Browse + import
# --------------------------------------------------------------------------- #
@router.get("/{tool_id}/browse", response_model=list[BrowseService])
def browse(tool_id: str, db: Session = Depends(get_db)):
    tool = _get_tool(db, tool_id)
    _require_live(tool)
    imported = {
        d.dataset_key: d.tool.name for d in db.query(ToolDataset).all()
    }
    here = {d.dataset_key for d in tool.datasets}
    try:
        client = client_for_tool(tool)
        out: list[BrowseService] = []
        for svc in client.list_database_services():
            dbs = []
            for d in client.list_databases(svc["name"]):
                fqn = d.get("fullyQualifiedName") or f"{svc['name']}.{d['name']}"
                dbs.append(
                    BrowseDatabase(
                        name=d["name"],
                        fqn=fqn,
                        description=d.get("description") or None,
                        imported_by=imported.get(fqn),
                        imported_here=fqn in here,
                    )
                )
            out.append(
                BrowseService(
                    name=svc["name"],
                    service_type=svc.get("serviceType"),
                    databases=sorted(dbs, key=lambda x: x.name.lower()),
                )
            )
        return sorted(out, key=lambda x: x.name.lower())
    except OpenMetadataError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/{tool_id}/browse/schemas", response_model=list[BrowseSchema])
def browse_schemas(tool_id: str, database: str, db: Session = Depends(get_db)):
    tool = _get_tool(db, tool_id)
    _require_live(tool)
    try:
        client = client_for_tool(tool)
        out = []
        for s in client.list_schemas(database):
            fqn = s.get("fullyQualifiedName") or f"{database}.{s['name']}"
            out.append(
                BrowseSchema(name=s["name"], fqn=fqn, table_count=client.count_tables(schema_fqn=fqn))
            )
        return sorted(out, key=lambda x: x.name.lower())
    except OpenMetadataError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/{tool_id}/datasets", response_model=DatasetImportResult)
def import_datasets(tool_id: str, body: DatasetImportRequest, db: Session = Depends(get_db)):
    tool = _get_tool(db, tool_id)
    _require_live(tool)
    if not body.datasets:
        raise HTTPException(status_code=400, detail="Select at least one database to import.")

    imported: list[ToolDataset] = []
    errors: dict[str, str] = {}
    for item in body.datasets:
        key = f"{item.service}.{item.database}"
        existing = db.query(ToolDataset).filter(ToolDataset.dataset_key == key).first()
        if existing and existing.tool_id != tool.id:
            errors[key] = f"Already imported through '{existing.tool.name}'."
            continue
        ds = existing or ToolDataset(
            tool_id=tool.id,
            service_name=item.service,
            database_name=item.database,
            dataset_key=key,
        )
        ds.display_name = (item.display_name or "").strip() or None
        ds.schemas = [s for s in item.schemas if s]
        if existing is None:
            db.add(ds)
            db.flush()
            db.refresh(tool)
        try:
            with db.begin_nested():
                sync.sync_dataset(db, tool, ds)
            imported.append(ds)
        except OpenMetadataError as e:
            ds.status = "ERROR"
            ds.error = str(e)[:2000]
            errors[key] = str(e)
    created = 0
    if imported and body.run_detection:
        created, _ = findings_service.detect_findings(db)
        health.compute_health(db)
    for ds in imported:
        audit.record(
            db,
            action="DATASET_IMPORTED",
            actor="Demo Steward",
            actor_type="human",
            entity=ds.dataset_key,
            detail=f"Imported {ds.table_count} tables from '{tool.name}'"
            + (f" (schemas: {', '.join(ds.schemas)})" if ds.schemas else "")
            + ".",
        )
    db.commit()
    return DatasetImportResult(
        imported=[_ds_out(d) for d in imported], errors=errors, findings_created=created
    )


def _get_ds(db: Session, tool_id: str, ds_id: str) -> ToolDataset:
    ds = db.get(ToolDataset, ds_id)
    if ds is None or ds.tool_id != tool_id:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@router.post("/{tool_id}/datasets/{ds_id}/sync", response_model=ToolDatasetOut)
def sync_one(tool_id: str, ds_id: str, db: Session = Depends(get_db)):
    ds = _get_ds(db, tool_id, ds_id)
    try:
        sync.sync_dataset(db, ds.tool, ds)
    except OpenMetadataError as e:
        db.rollback()
        ds = _get_ds(db, tool_id, ds_id)
        ds.status = "ERROR"
        ds.error = str(e)[:2000]
        db.commit()
        raise HTTPException(status_code=502, detail=str(e)) from e
    findings_service.detect_findings(db)
    health.compute_health(db)
    db.commit()
    return _ds_out(ds)


@router.put("/{tool_id}/datasets/{ds_id}", response_model=ToolDatasetOut)
def update_dataset(tool_id: str, ds_id: str, body: ToolDatasetUpdate, db: Session = Depends(get_db)):
    ds = _get_ds(db, tool_id, ds_id)
    if body.display_name is not None:
        ds.display_name = body.display_name.strip() or None
    if body.schemas is not None:
        ds.schemas = [s for s in body.schemas if s]
        try:
            sync.sync_dataset(db, ds.tool, ds)
        except OpenMetadataError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        findings_service.detect_findings(db)
        health.compute_health(db)
    db.commit()
    return _ds_out(ds)


@router.delete("/{tool_id}/datasets/{ds_id}", status_code=204)
def remove_dataset(tool_id: str, ds_id: str, db: Session = Depends(get_db)):
    ds = _get_ds(db, tool_id, ds_id)
    key = ds.dataset_key
    removed = sync.remove_dataset(db, ds)
    health.compute_health(db)
    audit.record(
        db,
        action="DATASET_REMOVED",
        actor="Demo Steward",
        actor_type="human",
        entity=key,
        detail=f"Stopped tracking {removed} tables. OpenMetadata and ingested sources were kept.",
    )
    db.commit()
    return None
