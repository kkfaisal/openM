"""Finding engine — deterministic detection rules.

Runs *before* any LLM reasoning (cost control): cheap, deterministic checks
produce findings; only findings that need reasoning are handed to an agent.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import CatalogTable, Finding

# Column-name signals that a column may contain sensitive data. This is a
# *rule-based* starting point only; a classification agent is expected to add
# evidence before anything is ever applied.
_SENSITIVE_PATTERNS = [
    (re.compile(r"(^|_)email($|_)", re.I), "Email"),
    (re.compile(r"(^|_)phone($|_)", re.I), "Phone Number"),
    (re.compile(r"(^|_)ssn($|_)", re.I), "SSN"),
    (re.compile(r"(^|_)card($|_)|card_hash|pan", re.I), "Payment Card"),
    (re.compile(r"(^|_)customer_id($|_)", re.I), "Customer Identifier"),
    (re.compile(r"(^|_)address($|_)", re.I), "Address"),
    (re.compile(r"(^|_)dob($|_)|birth_date", re.I), "Date of Birth"),
    (re.compile(r"(^|_)password($|_)|secret|token", re.I), "Credential"),
    (re.compile(r"(^|_)salary($|_)|income", re.I), "Personal Financial"),
    (re.compile(r"(^|_)ip_address($|_)", re.I), "IP Address"),
    (re.compile(r"(^|_)(first_name|last_name|full_name)($|_)", re.I), "Name"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def detect_sensitive_columns(table: CatalogTable) -> list[tuple[str, str]]:
    """Return [(column_name, label)] for columns that look sensitive."""
    hits: list[tuple[str, str]] = []
    for col in table.columns:
        for pattern, label in _SENSITIVE_PATTERNS:
            if pattern.search(col.name):
                hits.append((col.name, label))
                break
    return hits


def _exists(db: Session, type: str, entity: str) -> bool:
    return (
        db.query(Finding)
        .filter(
            Finding.type == type,
            Finding.entity == entity,
            Finding.status.in_(["OPEN", "INVESTIGATING", "RECOMMENDED"]),
        )
        .first()
        is not None
    )


def create_finding(
    db: Session,
    *,
    type: str,
    severity: str,
    entity: str,
    entity_type: str,
    domain: str | None,
    summary: str,
    agent: str,
) -> Finding | None:
    """Create a finding unless an active one already exists (no duplicates)."""
    if _exists(db, type, entity):
        return None
    finding = Finding(
        type=type,
        severity=severity,
        entity=entity,
        entity_type=entity_type,
        domain=domain,
        status="OPEN",
        summary=summary,
        agent=agent,
        detected_at=_now(),
    )
    db.add(finding)
    return finding


def detect_findings(db: Session) -> tuple[int, int]:
    """Run all deterministic checks across the catalog.

    Returns (findings_created, tables_scanned).
    """
    from . import catalog

    tables = catalog.list_tables(db, limit=100000)
    created = 0

    for table in tables:
        domain = catalog.domain_name(db, table)
        owner = catalog.owner_name(db, table)

        # Missing description
        if not table.description or len(table.description.strip()) < 10:
            if create_finding(
                db,
                type="MISSING_DESCRIPTION",
                severity="MEDIUM",
                entity=table.fqn,
                entity_type="table",
                domain=domain,
                summary=f"Table '{table.fqn}' has no meaningful description.",
                agent="DescriptionAgent",
            ):
                created += 1

        # Missing owner
        if not owner:
            if create_finding(
                db,
                type="MISSING_OWNER",
                severity="HIGH",
                entity=table.fqn,
                entity_type="table",
                domain=domain,
                summary=f"Table '{table.fqn}' has no assigned owner.",
                agent="OwnershipAgent",
            ):
                created += 1

        # Missing domain
        if not domain:
            if create_finding(
                db,
                type="MISSING_DOMAIN",
                severity="MEDIUM",
                entity=table.fqn,
                entity_type="table",
                domain=None,
                summary=f"Table '{table.fqn}' is not assigned to a domain.",
                agent="OwnershipAgent",
            ):
                created += 1

        # Missing column descriptions — one finding per undocumented column
        # (entity is "table.column" so the agent can target the column).
        for col in table.columns:
            if not col.description:
                if create_finding(
                    db,
                    type="MISSING_COLUMN_DESCRIPTION",
                    severity="LOW",
                    entity=f"{table.fqn}.{col.name}",
                    entity_type="column",
                    domain=domain,
                    summary=(
                        f"Column '{col.name}' of '{table.fqn}' is missing "
                        f"documentation."
                    ),
                    agent="ColumnDescriptionAgent",
                ):
                    created += 1

        # Potentially sensitive columns without classification
        sensitive = detect_sensitive_columns(table)
        for col_name, label in sensitive:
            col = next((c for c in table.columns if c.name == col_name), None)
            if col and not col.classification:
                if create_finding(
                    db,
                    type="MISSING_CLASSIFICATION",
                    severity="HIGH",
                    entity=f"{table.fqn}.{col_name}",
                    entity_type="column",
                    domain=domain,
                    summary=(
                        f"Column '{col_name}' may contain sensitive data "
                        f"({label}) but has no classification."
                    ),
                    agent="ClassificationAgent",
                ):
                    created += 1

        # Stale tables
        cutoff = _now() - timedelta(days=90)
        if table.last_queried_at is None or table.last_queried_at < cutoff:
            last = (
                "never queried"
                if table.last_queried_at is None
                else f"last queried {table.last_queried_at:%Y-%m-%d}"
            )
            if create_finding(
                db,
                type="STALE_ENTITY",
                severity="LOW",
                entity=table.fqn,
                entity_type="table",
                domain=domain,
                summary=f"Table '{table.fqn}' appears stale ({last}).",
                agent="StalenessAgent",
            ):
                created += 1

    return created, len(tables)
