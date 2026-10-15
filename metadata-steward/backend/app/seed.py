"""Seeding / bootstrap logic.

Two backends:

* ``demo`` — seed the local SQLite catalog with dummy data.
* ``openmetadata`` — ingest dummy data into a real OpenMetadata instance
  (idempotent), sync it back into the local snapshot, then run detection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .config import settings
from .models import (
    CatalogColumn,
    CatalogDomain,
    CatalogGlossaryTerm,
    CatalogTable,
    CatalogTeam,
    MetadataTool,
)
from .services import audit, health, policy
from .services import demo_data as dd


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _days_ago(days: int) -> datetime:
    return _now() - timedelta(days=days)


def _ensure_default_tool(db: Session) -> MetadataTool:
    """Ensure exactly one default tool exists (the current system of record)."""
    tool = db.query(MetadataTool).filter(MetadataTool.is_default.is_(True)).first()
    if tool is None:
        if settings.catalog_backend == "openmetadata":
            tool = MetadataTool(
                name="OpenMetadata",
                type="openmetadata",
                host=settings.openmetadata_host or "",
                status="CONNECTED",
                is_default=True,
            )
        else:
            tool = MetadataTool(
                name="OpenMetadata (demo)",
                type="openmetadata",
                host="",
                status="CONNECTED",
                is_default=True,
            )
        db.add(tool)
        db.flush()
    return tool


def _seed_catalog(db: Session) -> None:
    """Local demo backend: write the dummy catalog into SQLite directly."""
    tool = _ensure_default_tool(db)
    domain_by_name: dict[str, CatalogDomain] = {}
    for name, display, desc in dd.DOMAINS:
        dom = CatalogDomain(name=name, display_name=display, description=desc)
        db.add(dom)
        domain_by_name[name] = dom
    db.flush()

    team_by_name: dict[str, CatalogTeam] = {}
    for name in dd.TEAMS:
        team = CatalogTeam(name=name)
        db.add(team)
        team_by_name[name] = team
    db.flush()

    for name, definition in dd.GLOSSARY:
        db.add(CatalogGlossaryTerm(name=name, definition=definition))
    db.flush()

    for spec in dd.CATALOG:
        table = CatalogTable(
            fqn=spec["fqn"],
            name=spec["name"],
            schema_name=spec["schema_name"],
            service_name="Snowflake",
            database_name="ANALYTICS",
            tool_id=tool.id,
            description=spec["description"],
            domain_id=domain_by_name[spec["domain"]].id if spec["domain"] else None,
            owner_team_id=team_by_name[spec["owner"]].id if spec["owner"] else None,
            row_count=spec["row_count"],
            last_updated_at=_days_ago(2),
            last_ingested_at=_days_ago(1),
            last_queried_at=spec["last_queried_at"],
            tags=[],
        )
        db.add(table)
        db.flush()
        for i, (name, dtype, desc, classification) in enumerate(spec["columns"]):
            db.add(
                CatalogColumn(
                    table_id=table.id,
                    name=name,
                    data_type=dtype,
                    description=desc,
                    classification=classification,
                    position=i,
                    tags=[],
                )
            )
    db.flush()


def _seed_policies(db: Session) -> None:
    from .models import Policy

    if db.query(Policy).count() == 0:
        for p in policy.default_policies():
            db.add(Policy(**p))
    db.flush()


def _seed_history(db: Session) -> None:
    """Demo-only: a couple of pre-existing changes so Activity/Changes/health
    history are not empty on first load (never used in openmetadata mode)."""
    from .models import AuditEvent, MetadataChange

    if db.query(MetadataChange).count() > 0:
        return

    db.add(
        MetadataChange(
            entity="customer.dim_customer",
            field="description",
            old_value=None,
            new_value="Master customer dimension with contact and segmentation attributes.",
            recommendation_id="seed-demo-1",
            applied_at=_days_ago(3),
            verified=True,
            applied_by="steward",
        )
    )
    db.add(
        AuditEvent(
            actor_type="system",
            actor="steward",
            action="APPLY_RECOMMENDATION",
            entity="customer.dim_customer",
            field="description",
            old_value=None,
            new_value="Master customer dimension with contact and segmentation attributes.",
            detail="Description auto-applied (confidence 0.92).",
            confidence=0.92,
            policy="Description auto-apply (high confidence)",
            timestamp=_days_ago(3),
        )
    )
    db.add(
        AuditEvent(
            actor_type="system",
            actor="Scanner",
            action="SCAN_COMPLETED",
            detail="Daily scan completed: 16 tables scanned, 12 findings created.",
            timestamp=_days_ago(1),
        )
    )
    db.flush()


def _run_detection(db: Session) -> None:
    from .config import openai_api_key
    from .services import agents, findings

    findings.detect_findings(db)
    db.flush()
    # "Always use LLM": only generate recommendations when a key is configured.
    if openai_api_key():
        _ = agents.investigate_all_open(db)
    health.compute_health(db)


def _bootstrap_openmetadata(db: Session) -> None:
    """Startup for the OpenMetadata backend.

    * Always: make sure the default tool exists and flag legacy connections
      that were saved without credentials (they were never really tested).
    * Only with ``BOOTSTRAP_DEMO_DATA=true`` (the dev default): create the
      sample Postgres ecommerce database, mirror it into OpenMetadata and
      import it as a dataset of the default tool.

    Startup never calls the LLM; agents run from scans or the UI.
    """
    import os

    from .models import ToolDataset
    from .services import ecommerce, findings, sync
    from .services.openmetadata_client import OpenMetadataError, get_client

    tool = _ensure_default_tool(db)
    for t in db.query(MetadataTool).filter(MetadataTool.type == "openmetadata").all():
        if not t.is_default and not (t.config or {}).get("auth") and t.status == "CONNECTED":
            t.status = "UNVERIFIED"
            t.last_error = "Saved without credentials. Edit the connection and test it."
    db.flush()

    sync.obsolete_orphans(db)

    if os.getenv("BOOTSTRAP_DEMO_DATA", "true").lower() not in ("1", "true", "yes"):
        db.commit()
        return

    try:
        ecommerce.ensure_postgres_database()
        created = ecommerce.ingest(get_client())
    except Exception as e:  # noqa: BLE001 — demo data is best-effort
        tool.status = "ERROR"
        tool.last_error = f"Demo bootstrap failed: {e}"[:2000]
        db.commit()
        return

    key = f"{ecommerce.SERVICE_NAME}.{ecommerce.POSTGRES_DB}"
    ds = db.query(ToolDataset).filter(ToolDataset.dataset_key == key).first()
    if ds is None:
        ds = ToolDataset(
            tool_id=tool.id,
            service_name=ecommerce.SERVICE_NAME,
            database_name=ecommerce.POSTGRES_DB,
            dataset_key=key,
            display_name="ecommerce",
            schemas=[],
        )
        db.add(ds)
        db.flush()
    try:
        synced = sync.sync_dataset(db, ds.tool, ds)
    except OpenMetadataError as e:
        ds.status = "ERROR"
        ds.error = str(e)[:2000]
        db.commit()
        return
    findings.detect_findings(db)
    health.compute_health(db)
    audit.record(
        db,
        action="OPENMETADATA_INGEST_AND_SCAN",
        actor="system",
        actor_type="system",
        detail=(
            f"Demo bootstrap: mirrored the Postgres ecommerce database into "
            f"OpenMetadata (created={created}); synced {synced} tables and ran "
            f"detection."
        ),
    )
    db.commit()


def seed_if_empty(db: Session) -> None:
    """Bootstrap on startup. Idempotent."""
    _seed_policies(db)

    if settings.catalog_backend == "openmetadata":
        _bootstrap_openmetadata(db)
        return

    if db.query(CatalogTable).count() > 0:
        return

    _seed_catalog(db)
    _seed_history(db)
    health.compute_health(db)
    _run_detection(db)
    audit.record(
        db,
        action="BOOTSTRAP",
        actor="system",
        actor_type="system",
        detail="Demo catalog seeded and initial scan completed.",
    )
    db.commit()
