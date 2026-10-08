"""Metadata-tool (connection) helpers.

A "tool" is a metadata-management platform (OpenMetadata, Amundsen, DataHub,
Atlan, Collibra, Alation, Unity Catalog, ...). Datasets live under a tool.

Real API sync is implemented for OpenMetadata; other tools can be registered
and, for demo purposes, seeded with a local sample catalog so their datasets
appear immediately. The connector interface is the seam where per-tool syncs
plug in later.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..models import CatalogColumn, CatalogDomain, CatalogTable, CatalogTeam, MetadataTool


def tool_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "tool").lower()).strip("_") or "tool"


def seed_demo_catalog(db: Session, tool: MetadataTool) -> int:
    """Seed a sample catalog scoped to `tool` (distinct service/database/fqn)."""
    from . import demo_data as dd

    slug = tool_slug(tool.name)
    service = f"{slug}_snowflake"
    database = "ANALYTICS"

    domains = {d.name: d for d in db.query(CatalogDomain).all()}
    teams = {t.name: t for t in db.query(CatalogTeam).all()}
    for name, display, desc in dd.DOMAINS:
        if name not in domains:
            d = CatalogDomain(name=name, display_name=display, description=desc)
            db.add(d)
            db.flush()
            domains[name] = d
    for name in dd.TEAMS:
        if name not in teams:
            t = CatalogTeam(name=name)
            db.add(t)
            db.flush()
            teams[name] = t

    count = 0
    for spec in dd.CATALOG:
        table = CatalogTable(
            fqn=f"{service}.{database}.{spec['schema_name']}.{spec['name']}",
            name=spec["name"],
            schema_name=spec["schema_name"],
            service_name=service,
            database_name=database,
            tool_id=tool.id,
            description=spec["description"],
            domain_id=domains[spec["domain"]].id if spec["domain"] in domains else None,
            owner_team_id=teams[spec["owner"]].id if spec["owner"] in teams else None,
            tags=[],
            row_count=spec["row_count"],
            last_queried_at=spec["last_queried_at"],
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
        count += 1
    db.flush()
    return count
