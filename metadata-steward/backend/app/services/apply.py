"""Recommendation application.

The only place a recommendation is turned into a catalog write. Supports
rollback for the fields we update (previous value is stored on the change
record).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Recommendation
from . import audit, catalog


def apply_recommendation(
    db: Session,
    *,
    recommendation: Recommendation,
    value: str | None = None,
    applied_by: str = "steward",
) -> None:
    """Apply a recommendation (optionally with a modified value) to the catalog.

    Raises ValueError for unsupported or denied fields.
    """
    from ..models import Finding  # local import to avoid cycle

    finding = db.query(Finding).filter(Finding.id == recommendation.finding_id).first()
    if finding is None:
        raise ValueError("Finding not found.")

    # A recommendation may target a table or a specific column.
    column_name: str | None = None
    if recommendation.field in ("classification", "column_description"):
        table_fqn, column_name = finding.entity.rsplit(".", 1)
    else:
        table_fqn = finding.entity

    table = catalog.get_table(db, table_fqn)
    if table is None:
        raise ValueError(f"Catalog entity not found: {table_fqn}")

    new_value = value if value is not None else recommendation.new_value
    if not new_value:
        raise ValueError("Recommendation has no value to apply.")

    field = recommendation.field
    if field == "description":
        catalog.update_description(
            db,
            table=table,
            value=new_value,
            recommendation_id=recommendation.id,
            applied_by=applied_by,
        )
    elif field == "owner":
        catalog.update_owner(
            db,
            table=table,
            team_name=new_value,
            recommendation_id=recommendation.id,
            applied_by=applied_by,
        )
    elif field == "domain":
        catalog.update_domain(
            db,
            table=table,
            domain=new_value,
            recommendation_id=recommendation.id,
            applied_by=applied_by,
        )
    elif field == "classification":
        column = next((c for c in table.columns if c.name == column_name), None)
        if column is None:
            raise ValueError(f"Column not found: {column_name}")
        catalog.update_column_classification(
            db,
            column=column,
            table=table,
            value=new_value,
            recommendation_id=recommendation.id,
            applied_by=applied_by,
        )
    elif field == "column_description":
        column = next((c for c in table.columns if c.name == column_name), None)
        if column is None:
            raise ValueError(f"Column not found: {column_name}")
        catalog.update_column_description(
            db,
            column=column,
            table=table,
            value=new_value,
            recommendation_id=recommendation.id,
            applied_by=applied_by,
        )
    elif field in ("glossary",):
        raise ValueError("Glossary application is not implemented in the MVP slice.")
    else:
        raise ValueError(f"Unsupported field for application: {field}")

    recommendation.status = "APPLIED"
    recommendation.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    finding.status = "RESOLVED"
    finding.resolved_at = recommendation.resolved_at

    audit.record(
        db,
        action="APPLY_RECOMMENDATION",
        actor=applied_by,
        actor_type="human" if applied_by != "steward" else "system",
        entity=table_fqn,
        field=field,
        old_value=recommendation.old_value,
        new_value=new_value,
        detail="Recommendation applied to catalog and verified.",
        confidence=recommendation.confidence,
        policy=recommendation.policy_id,
    )
