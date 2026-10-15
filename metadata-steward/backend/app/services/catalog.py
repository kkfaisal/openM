"""Catalog access layer.

This is the only place that reads/writes the metadata system of record
(the ``catalog_*`` tables in demo mode). Agents never touch the catalog
directly — they go through these typed helpers. In a production build this
layer would delegate to the OpenMetadata REST API while keeping the same
interface.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    CatalogColumn,
    CatalogDomain,
    CatalogTable,
    CatalogTeam,
    MetadataChange,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _using_om() -> bool:
    from ..config import settings

    return settings.catalog_backend == "openmetadata"


def _om_client(table: CatalogTable):
    """The OpenMetadata instance that owns this table."""
    from .openmetadata_client import client_for_tool, get_client

    if table.tool is not None and table.tool.type == "openmetadata":
        return client_for_tool(table.tool)
    return get_client()


def list_domains(db: Session) -> list[CatalogDomain]:
    return db.query(CatalogDomain).order_by(CatalogDomain.name).all()


def list_tables(
    db: Session,
    *,
    domain: str | None = None,
    service: str | None = None,
    schema: str | None = None,
    q: str | None = None,
    limit: int = 500,
) -> list[CatalogTable]:
    query = db.query(CatalogTable)
    if domain:
        query = query.join(CatalogDomain).filter(CatalogDomain.name == domain)
    if service:
        query = query.filter(CatalogTable.service_name == service)
    if schema:
        query = query.filter(CatalogTable.schema_name == schema)
    if q:
        query = query.filter(CatalogTable.fqn.ilike(f"%{q}%"))
    return query.order_by(CatalogTable.fqn).limit(limit).all()


def get_table(db: Session, fqn: str) -> CatalogTable | None:
    return db.query(CatalogTable).filter(CatalogTable.fqn == fqn).first()


def get_table_by_id(db: Session, table_id: int) -> CatalogTable | None:
    return db.query(CatalogTable).filter(CatalogTable.id == table_id).first()


def domain_name(db: Session, table: CatalogTable) -> str | None:
    if table.domain_id and table.domain:
        return table.domain.name
    return None


def owner_name(db: Session, table: CatalogTable) -> str | None:
    if table.owner_team_id and table.owner:
        return table.owner.name
    return None


def column_names(table: CatalogTable) -> list[str]:
    return [c.name for c in table.columns]


def count_tables(db: Session) -> int:
    return db.query(CatalogTable).count()


def count_columns(db: Session) -> int:
    return db.query(CatalogColumn).count()


def count_stale_tables(db: Session, days: int = 90) -> int:
    cutoff = _now() - timedelta(days=days)
    return (
        db.query(CatalogTable)
        .filter(
            (CatalogTable.last_queried_at == None)  # noqa: E711
            | (CatalogTable.last_queried_at < cutoff)
        )
        .count()
    )


# ---- Writes (the only write path into the catalog) ---- #
def _record_change(
    db: Session,
    *,
    table: CatalogTable,
    field: str,
    old_value: str | None,
    new_value: str | None,
    recommendation_id: str | None,
    applied_by: str = "steward",
) -> MetadataChange:
    change = MetadataChange(
        entity=table.fqn,
        field=field,
        old_value=old_value,
        new_value=new_value,
        recommendation_id=recommendation_id,
        applied_at=_now(),
        verified=True,
        applied_by=applied_by,
        rollback_value=old_value,
    )
    db.add(change)
    return change


def update_description(
    db: Session,
    *,
    table: CatalogTable,
    value: str,
    recommendation_id: str | None = None,
    applied_by: str = "steward",
) -> MetadataChange:
    if _using_om():
        _om_client(table).update_table_description(table.fqn, value)
    old = table.description
    table.description = value
    return _record_change(
        db,
        table=table,
        field="description",
        old_value=old,
        new_value=value,
        recommendation_id=recommendation_id,
        applied_by=applied_by,
    )


def update_owner(
    db: Session,
    *,
    table: CatalogTable,
    team_name: str,
    recommendation_id: str | None = None,
    applied_by: str = "steward",
) -> MetadataChange:
    if _using_om():
        _om_client(table).update_table_owner(table.fqn, team_name)
    team = db.query(CatalogTeam).filter(CatalogTeam.name == team_name).first()
    if team is None:
        team = CatalogTeam(name=team_name)
        db.add(team)
        db.flush()
    old = owner_name(db, table)
    table.owner_team_id = team.id
    return _record_change(
        db,
        table=table,
        field="owner",
        old_value=old,
        new_value=team_name,
        recommendation_id=recommendation_id,
        applied_by=applied_by,
    )


def update_domain(
    db: Session,
    *,
    table: CatalogTable,
    domain: str,
    recommendation_id: str | None = None,
    applied_by: str = "steward",
) -> MetadataChange:
    if _using_om():
        _om_client(table).update_table_domain(table.fqn, domain)
    dom = db.query(CatalogDomain).filter(CatalogDomain.name == domain).first()
    old = domain_name(db, table)
    if dom is None:
        dom = CatalogDomain(name=domain, display_name=domain)
        db.add(dom)
        db.flush()
    table.domain_id = dom.id
    return _record_change(
        db,
        table=table,
        field="domain",
        old_value=old,
        new_value=domain,
        recommendation_id=recommendation_id,
        applied_by=applied_by,
    )


def update_column_classification(
    db: Session,
    *,
    column: CatalogColumn,
    table: CatalogTable,
    value: str,
    recommendation_id: str | None = None,
    applied_by: str = "steward",
) -> MetadataChange:
    if _using_om():
        _om_client(table).update_column_tag(table.fqn, column.name, value)
    old = column.classification
    column.classification = value
    return _record_change(
        db,
        table=table,
        field=f"column.{column.name}.classification",
        old_value=old,
        new_value=value,
        recommendation_id=recommendation_id,
        applied_by=applied_by,
    )


def update_column_description(
    db: Session,
    *,
    column: CatalogColumn,
    table: CatalogTable,
    value: str,
    recommendation_id: str | None = None,
    applied_by: str = "steward",
) -> MetadataChange:
    if _using_om():
        _om_client(table).update_column_description(table.fqn, column.name, value)
    old = column.description
    column.description = value
    return _record_change(
        db,
        table=table,
        field=f"column.{column.name}.description",
        old_value=old,
        new_value=value,
        recommendation_id=recommendation_id,
        applied_by=applied_by,
    )


def recent_changes(db: Session, days: int = 7) -> list[MetadataChange]:
    cutoff = _now() - timedelta(days=days)
    return (
        db.query(MetadataChange)
        .filter(MetadataChange.applied_at >= cutoff)
        .order_by(MetadataChange.applied_at.desc())
        .all()
    )


def tables_by_domain(db: Session) -> dict[str, int]:
    rows = (
        db.query(CatalogDomain.name, func.count(CatalogTable.id))
        .join(CatalogTable, CatalogTable.domain_id == CatalogDomain.id)
        .group_by(CatalogDomain.name)
        .all()
    )
    return {name: count for name, count in rows}
