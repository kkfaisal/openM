"""Confidence engine.

Confidence is *never* a bare LLM number. It combines the agent's semantic
score with the quality and agreement of independent evidence, then normalizes
to [0, 1]. Deterministic evidence can add or subtract; the result is capped so
no recommendation can reach 1.0 purely from a model claim.
"""
from __future__ import annotations

from ..models import Evidence

# Point contributions per evidence type. Independent, verifiable evidence is
# worth more than weak heuristics.
_WEIGHTS: dict[str, float] = {
    "PIPELINE_OWNER": 0.15,
    "SCHEMA_PATTERN": 0.12,
    "DOMAIN_OWNER": 0.12,
    "NEIGHBOR_OWNER": 0.10,
    "HISTORICAL_OWNER": 0.10,
    "COLUMN_NAME": 0.08,
    "NAME_SIMILARITY": 0.08,
    "SENSITIVE_PATTERN": 0.20,
    "GLOSSARY_MATCH": 0.14,
    "UPSTREAM_LINEAGE": 0.08,
    "DOWNSTREAM_LINEAGE": 0.06,
    "SOURCE_EXTRACT": 0.10,
    # Retrieved passages corroborate but are unverified raw text.
    "RAG_PASSAGE": 0.05,
    "CONFLICT": -0.15,
}


def compute_confidence(
    *,
    semantic_confidence: float,
    evidence: list[Evidence],
    field: str | None = None,
) -> float:
    base = min(max(semantic_confidence, 0.0), 0.9)

    delta = 0.0
    for ev in evidence:
        delta += _WEIGHTS.get(ev.type, 0.04)

    # Cap the evidence boost so a pile of weak signals can't reach certainty.
    delta = max(min(delta, 0.35), -0.35)

    score = base + delta
    return round(min(max(score, 0.01), 0.99), 4)
