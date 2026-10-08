"""Synchronise OpenMetadata → local operational snapshot.

The local `catalog_*` tables are a fast, searchable snapshot of OpenMetadata.
Agents and the health engine read this snapshot; writes go through
`catalog.py` which both patches OpenMetadata and updates the snapshot.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (
    CatalogColumn,
    CatalogDomain,
    CatalogGlossaryTerm,
    CatalogTable,
    CatalogTeam,
)
from .openmetadata_client import get_client


def _ms_to_dt(ms) -> datetime | None:
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


def sync_from_openmetadata(db: Session, tool_id: str | None = None) -> int:
    """Pull tables/columns/teams/domains from OpenMetadata and rebuild this
    tool's slice of the local snapshot. Only the given tool's tables are
    replaced; shared reference data (domains/teams/glossary) is upserted by
    name so other tools keep working. Returns the number of tables synced."""
    client = get_client()

    tables = client.list_tables()
    domains = client.list_domains()
    teams = client.list_teams()
    glossary_terms = client.list_glossary_terms()

    # Replace only this tool's tables (columns cascade); leave others intact.
    if tool_id:
        db.query(CatalogTable).filter(CatalogTable.tool_id == tool_id).delete()
    else:
        db.query(CatalogTable).delete()
    db.flush()

    # Upsert shared reference data by name (never orphan other tools).
    existing_domains = {d.name: d for d in db.query(CatalogDomain).all()}
    domain_map: dict[str, CatalogDomain] = {}
    for d in domains:
        name = d.get("name")
        dom = existing_domains.get(name)
        if dom is None:
            dom = CatalogDomain(name=name, display_name=name, description=d.get("description"))
            db.add(dom)
        else:
            dom.description = d.get("description") or dom.description
        domain_map[name] = dom

    existing_teams = {t.name: t for t in db.query(CatalogTeam).all()}
    team_map: dict[str, CatalogTeam] = {}
    for t in teams:
        name = t.get("name")
        team = existing_teams.get(name)
        if team is None:
            team = CatalogTeam(name=name)
            db.add(team)
        team_map[name] = team

    existing_glossary = {g.name for g in db.query(CatalogGlossaryTerm).all()}
    for g in glossary_terms:
        name = g.get("name")
        if name not in existing_glossary:
            db.add(CatalogGlossaryTerm(name=name, definition=g.get("description")))

    db.flush()

    for t in tables:
        fqn = t.get("fullyQualifiedName") or ""
        parts = fqn.split(".")
        n = len(parts)
        schema_name = parts[-2] if n >= 2 else ""
        database_name = parts[-3] if n >= 3 else ""
        service_name = parts[-4] if n >= 4 else ""

        owner_name = _first_name(t.get("owners"))
        domain_name = _first_name(t.get("domains"))

        table = CatalogTable(
            fqn=fqn,
            name=t.get("name"),
            service_name=service_name,
            database_name=database_name,
            schema_name=schema_name,
            tool_id=tool_id,
            description=t.get("description"),
            owner_team_id=team_map[owner_name].id if owner_name in team_map else None,
            domain_id=domain_map[domain_name].id if domain_name in domain_map else None,
            tags=[],
            row_count=None,
            last_updated_at=_ms_to_dt(t.get("updatedAt")),
            last_ingested_at=_ms_to_dt(t.get("updatedAt")),
            last_queried_at=_ms_to_dt(t.get("updatedAt")),
        )
        db.add(table)
        db.flush()

        for i, c in enumerate(t.get("columns") or []):
            db.add(
                CatalogColumn(
                    table_id=table.id,
                    name=c.get("name"),
                    data_type=c.get("dataType") or c.get("dataTypeDisplay") or "VARCHAR",
                    description=c.get("description"),
                    classification=_classification_from_tags(c.get("tags")),
                    position=i,
                    tags=[],
                )
            )

    db.flush()
    return len(tables)
