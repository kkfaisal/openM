"""Synchronise OpenMetadata → local operational snapshot.

The local `catalog_*` tables are a fast, searchable snapshot of OpenMetadata.
Agents and the health engine read this snapshot; writes go through
`catalog.py` which both patches OpenMetadata and updates the snapshot.

Sync is scoped per imported dataset (``ToolDataset``): only the tables of
that OpenMetadata database (optionally limited to some schemas) are pulled,
and only that slice of the snapshot is replaced. Tables are upserted by FQN
so their ids stay stable across syncs; tables that disappeared upstream are
removed and their open findings are marked OBSOLETE.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    CatalogColumn,
    CatalogDomain,
    CatalogGlossaryTerm,
    CatalogTable,
    CatalogTeam,
    Finding,
    MetadataTool,
    ToolDataset,
)
from .openmetadata_client import OpenMetadataClient, OpenMetadataError, client_for_tool

log = logging.getLogger(__name__)

_OPEN = ("OPEN", "INVESTIGATING", "RECOMMENDED")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ms_to_dt(ms) -> datetime | None:  # noqa: ANN001
    if not ms:
        return None
    return datetime.fromtimestamp(int(ms) / 1000)


def _first_name(entities: list | None) -> str | None:
    if not entities:
        return None
    return entities[0].get("name")


def _classification_from_tags(tags: list | None) -> str | None:
    for t in tags or []:
        fqn = t.get("tagFQN") or ""
        if fqn.startswith("Sensitive."):
            return fqn
    return None


def _sync_reference_data(
    db: Session, client: OpenMetadataClient
) -> tuple[dict[str, CatalogDomain], dict[str, CatalogTeam]]:
    """Upsert domains/teams/glossary terms by name (shared across tools)."""
    existing_domains = {d.name: d for d in db.query(CatalogDomain).all()}
    for d in client.list_domains():
        name = d.get("name")
        dom = existing_domains.get(name)
        if dom is None:
            dom = CatalogDomain(
                name=name,
                display_name=d.get("displayName") or name,
                description=d.get("description"),
            )
            db.add(dom)
            existing_domains[name] = dom
        else:
            dom.description = d.get("description") or dom.description

    existing_teams = {t.name: t for t in db.query(CatalogTeam).all()}
    for t in client.list_teams():
        name = t.get("name")
        if name not in existing_teams:
            team = CatalogTeam(name=name)
            db.add(team)
            existing_teams[name] = team

    existing_glossary = {g.name for g in db.query(CatalogGlossaryTerm).all()}
    try:
        for g in client.list_glossary_terms():
            name = g.get("name")
            if name not in existing_glossary:
                db.add(CatalogGlossaryTerm(name=name, definition=g.get("description")))
                existing_glossary.add(name)
    except OpenMetadataError as e:  # glossary is optional
        log.info("Skipping glossary sync: %s", e)

    db.flush()
    return existing_domains, existing_teams


def _fetch_tables(client: OpenMetadataClient, ds: ToolDataset) -> list[dict]:
    db_fqn = f"{ds.service_name}.{ds.database_name}"
    if ds.schemas:
        out: list[dict] = []
        for schema in ds.schemas:
            out.extend(client.list_tables(schema_fqn=f"{db_fqn}.{schema}"))
        return out
    return client.list_tables(database_fqn=db_fqn)


def _obsolete_findings(db: Session, fqns: list[str]) -> int:
    n = 0
    for fqn in fqns:
        q = db.query(Finding).filter(
            Finding.status.in_(_OPEN),
            (Finding.entity == fqn) | Finding.entity.like(f"{fqn}.%"),
        )
        for f in q.all():
            f.status = "OBSOLETE"
            f.resolved_at = _now()
            for r in f.recommendations:
                if r.status == "PENDING":
                    r.status = "OBSOLETE"
            n += 1
    return n


def obsolete_orphans(db: Session) -> int:
    """Retire open findings whose table is no longer in the snapshot."""
    known = {fqn for (fqn,) in db.query(CatalogTable.fqn)}
    orphans: set[str] = set()
    for f in db.query(Finding).filter(Finding.status.in_(_OPEN)).all():
        table_fqn = f.entity if f.entity_type == "table" else f.entity.rsplit(".", 1)[0]
        if f.entity not in known and table_fqn not in known:
            orphans.add(f.entity)
    return _obsolete_findings(db, sorted(orphans)) if orphans else 0


def sync_dataset(db: Session, tool: MetadataTool, ds: ToolDataset) -> int:
    """Pull one imported dataset from OpenMetadata into the snapshot.

    Raises OpenMetadataError on connectivity/auth problems (the caller records
    it on the dataset). Returns the number of tables synced.
    """
    client = client_for_tool(tool)
    remote = _fetch_tables(client, ds)
    domains, teams = _sync_reference_data(db, client)

    local = {
        t.fqn: t
        for t in db.query(CatalogTable).filter(
            CatalogTable.service_name == ds.service_name,
            CatalogTable.database_name == ds.database_name,
        )
    }
    seen: set[str] = set()

    for t in remote:
        fqn = t.get("fullyQualifiedName") or ""
        parts = fqn.split(".")
        if len(parts) < 4:
            continue
        seen.add(fqn)
        owner = _first_name(t.get("owners"))
        domain = _first_name(t.get("domains"))
        updated = _ms_to_dt(t.get("updatedAt"))

        table = local.get(fqn)
        if table is None:
            table = CatalogTable(fqn=fqn, tags=[])
            db.add(table)
        table.name = t.get("name") or parts[-1]
        table.service_name = parts[0]
        table.database_name = parts[1]
        table.schema_name = parts[2]
        table.tool_id = tool.id
        table.description = t.get("description") or None
        table.owner_team_id = teams[owner].id if owner in teams else None
        table.domain_id = domains[domain].id if domain in domains else None
        table.last_updated_at = updated
        table.last_ingested_at = _now()
        table.last_queried_at = table.last_queried_at or updated
        db.flush()

        # Columns: rebuild from the source of truth.
        for c in list(table.columns):
            db.delete(c)
        db.flush()
        for i, c in enumerate(t.get("columns") or []):
            db.add(
                CatalogColumn(
                    table_id=table.id,
                    name=c.get("name"),
                    data_type=c.get("dataType") or c.get("dataTypeDisplay") or "VARCHAR",
                    description=c.get("description") or None,
                    classification=_classification_from_tags(c.get("tags")),
                    position=i,
                    tags=[],
                )
            )

    # Tables removed upstream (or filtered out by a schema change).
    gone = [fqn for fqn in local if fqn not in seen]
    if gone:
        _obsolete_findings(db, gone)
        for fqn in gone:
            db.delete(local[fqn])

    ds.table_count = len(seen)
    ds.status = "SYNCED"
    ds.error = None
    ds.last_synced_at = _now()
    tool.status = "CONNECTED"
    tool.last_error = None
    tool.last_checked_at = _now()
    db.flush()
    return len(seen)


def remove_dataset(db: Session, ds: ToolDataset) -> int:
    """Drop a dataset's tables from the snapshot (OpenMetadata is untouched).

    Ingested sources and their RAG index are keyed by dataset and kept, so a
    later re-import picks them up again.
    """
    tables = (
        db.query(CatalogTable)
        .filter(
            CatalogTable.service_name == ds.service_name,
            CatalogTable.database_name == ds.database_name,
        )
        .all()
    )
    _obsolete_findings(db, [t.fqn for t in tables])
    for t in tables:
        db.delete(t)
    db.delete(ds)
    db.flush()
    return len(tables)


def sync_all(db: Session) -> dict[str, int | str]:
    """Sync every imported dataset of every OpenMetadata tool.

    One failing connection never blocks the others; its error is stored on
    the dataset and tool so the UI can show it.
    """
    results: dict[str, int | str] = {}
    datasets = (
        db.query(ToolDataset)
        .join(MetadataTool)
        .filter(MetadataTool.type == "openmetadata")
        .all()
    )
    for ds in datasets:
        tool = ds.tool
        try:
            with db.begin_nested():
                results[ds.dataset_key] = sync_dataset(db, tool, ds)
        except OpenMetadataError as e:
            log.warning("Sync failed for %s: %s", ds.dataset_key, e)
            ds.status = "ERROR"
            ds.error = str(e)[:2000]
            tool.status = "ERROR"
            tool.last_error = str(e)[:2000]
            tool.last_checked_at = _now()
            results[ds.dataset_key] = f"error: {e}"
    db.flush()
    obsolete_orphans(db)
    return results


def sync_from_openmetadata(db: Session, tool_id: str | None = None) -> int:
    """Back-compat entry point: sync the given tool's datasets (or all)."""
    if tool_id is None:
        res = sync_all(db)
        return sum(v for v in res.values() if isinstance(v, int))
    tool = db.get(MetadataTool, tool_id)
    if tool is None:
        return 0
    total = 0
    for ds in tool.datasets:
        total += sync_dataset(db, tool, ds)
    return total

