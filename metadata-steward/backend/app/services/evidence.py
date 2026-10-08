"""Evidence helpers.

Every recommendation must carry verifiable evidence (never private
chain-of-thought). These helpers attach evidence rows to a finding or
recommendation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Evidence


def attach(
    db: Session,
    *,
    type: str,
    value: str,
    source: str | None = None,
    finding_id: str | None = None,
    recommendation_id: str | None = None,
) -> Evidence:
    ev = Evidence(
        type=type,
        value=value,
        source=source,
        finding_id=finding_id,
        recommendation_id=recommendation_id,
    )
    db.add(ev)
    return ev
