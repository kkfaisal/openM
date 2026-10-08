"""Metadata health engine.

Computes coverage dimensions from the catalog and a weighted overall score.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import CatalogTable, HealthSnapshot


def compute_health_for_tables(tables: list[CatalogTable]) -> tuple[float, dict[str, float]]:
    """Compute health dimensions + overall for a given list of tables."""
    n = len(tables)
    if n == 0:
        return 0.0, {}

    total_cols = sum(len(t.columns) for t in tables)

    with_owner = sum(1 for t in tables if t.owner_team_id)
    with_domain = sum(1 for t in tables if t.domain_id)
    with_desc = sum(1 for t in tables if t.description and len(t.description) >= 10)
    documented_cols = sum(
        1 for t in tables for c in t.columns if c.description and len(c.description) >= 5
    )
    classified_cols = sum(
        1 for t in tables for c in t.columns if c.classification
    )
    sensitive_cols = sum(
        1
        for t in tables
        for c in t.columns
        if c.classification is None and _looks_sensitive(c.name)
    )

    ownership = with_owner / n
    domain_cov = with_domain / n
    descriptions = with_desc / n
    column_docs = documented_cols / total_cols if total_cols else 0.0
    classification = (
        1.0 if sensitive_cols == 0 else (classified_cols / max(total_cols, 1))
    )

    dimensions = {
        "ownership": round(ownership, 4),
        "domain": round(domain_cov, 4),
        "descriptions": round(descriptions, 4),
        "column_documentation": round(column_docs, 4),
        "classification": round(classification, 4),
    }

    # Weighted overall (configurable by editing weights, not hard-coded in agents).
    weights = {
        "ownership": 0.3,
        "domain": 0.15,
        "descriptions": 0.2,
        "column_documentation": 0.2,
        "classification": 0.15,
    }
    overall = sum(
        dimensions[k] * w for k, w in weights.items() if k in dimensions
    )
    overall = round(min(max(overall, 0.0), 1.0), 4)
    return overall, dimensions


def compute_health(db: Session) -> tuple[float, dict[str, float]]:
    tables = db.query(CatalogTable).all()
    overall, dimensions = compute_health_for_tables(tables)

    snapshot = HealthSnapshot(overall=overall, dimensions=dimensions)
    db.add(snapshot)
    return overall, dimensions


def latest_snapshot(db: Session) -> HealthSnapshot | None:
    from sqlalchemy import desc

    return (
        db.query(HealthSnapshot)
        .order_by(desc(HealthSnapshot.created_at))
        .first()
    )


def _looks_sensitive(name: str) -> bool:
    import re

    patterns = [
        r"email", r"phone", r"ssn", r"card", r"customer_id", r"address",
        r"dob", r"password", r"token", r"salary", r"ip_address",
    ]
    low = name.lower()
    return any(re.search(p, low) for p in patterns)
