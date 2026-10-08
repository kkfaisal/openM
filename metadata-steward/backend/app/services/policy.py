"""Policy engine.

Deterministic evaluation of every proposed change. Policies are rows in the
database (configurable from the UI). Evaluation is first-match-wins by
priority; every field has a safe default when no policy matches.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Policy

# Conservative defaults (per spec: initial release requires approval for most).
_DEFAULTS: dict[str, str] = {
    "description": "REQUIRE_APPROVAL",
    "column_description": "REQUIRE_APPROVAL",
    "owner": "REQUIRE_APPROVAL",
    "domain": "REQUIRE_APPROVAL",
    "classification": "REQUIRE_APPROVAL",
    "glossary": "REQUIRE_APPROVAL",
}


def _matches(policy: Policy, *, field: str, confidence: float, critical: bool) -> bool:
    if policy.field != field:
        return False
    cond = policy.conditions or {}
    if "min_confidence" in cond and confidence < float(cond["min_confidence"]):
        return False
    if "max_confidence" in cond and confidence > float(cond["max_confidence"]):
        return False
    if "critical_only" in cond and cond["critical_only"] and not critical:
        return False
    if "not_critical" in cond and cond["not_critical"] and critical:
        return False
    return True


def evaluate(
    db: Session,
    *,
    field: str,
    confidence: float,
    critical: bool = False,
) -> tuple[str, Policy | None]:
    """Return (action_mode, matched_policy)."""
    policies = (
        db.query(Policy)
        .filter(Policy.enabled.is_(True))
        .order_by(Policy.priority.asc())
        .all()
    )
    for policy in policies:
        if _matches(policy, field=field, confidence=confidence, critical=critical):
            return policy.action_mode, policy
    return _DEFAULTS.get(field, "REQUIRE_APPROVAL"), None


def default_policies() -> list[dict]:
    """Seed policies (safe, human-in-the-loop defaults)."""
    return [
        {
            "name": "Description auto-apply (high confidence)",
            "description": (
                "Apply table descriptions automatically when confidence is high "
                "and the asset is not critical."
            ),
            "field": "description",
            "conditions": {"min_confidence": 0.85, "not_critical": True},
            "action_mode": "AUTO_APPLY",
            "priority": 10,
            "enabled": True,
        },
        {
            "name": "Owner changes require approval",
            "description": "Ownership changes always require a human steward.",
            "field": "owner",
            "conditions": {},
            "action_mode": "REQUIRE_APPROVAL",
            "priority": 20,
            "enabled": True,
        },
        {
            "name": "Domain changes require approval",
            "description": "Domain assignment always requires a human steward.",
            "field": "domain",
            "conditions": {},
            "action_mode": "REQUIRE_APPROVAL",
            "priority": 30,
            "enabled": True,
        },
        {
            "name": "Sensitive classification requires approval",
            "description": (
                "Sensitive classifications are never applied automatically, "
                "even at high confidence."
            ),
            "field": "classification",
            "conditions": {},
            "action_mode": "REQUIRE_APPROVAL",
            "priority": 40,
            "enabled": True,
        },
        {
            "name": "Glossary associations require approval",
            "description": "Glossary term associations require a human steward.",
            "field": "glossary",
            "conditions": {},
            "action_mode": "REQUIRE_APPROVAL",
            "priority": 50,
            "enabled": True,
        },
    ]
