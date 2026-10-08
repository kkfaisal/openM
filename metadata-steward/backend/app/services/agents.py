"""Agent logic + investigation orchestrator.

Each agent is a small, focused function that gathers evidence and produces a
recommendation. The orchestrator records an observable ``AgentRun`` (tool
calls / steps / summary) but never exposes model chain-of-thought.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    AgentRun,
    CatalogTable,
    Finding,
    Recommendation,
)
from . import catalog, confidence, evidence, policy
from .llm import PromptOverride, get_llm


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _record_run(
    db: Session,
    *,
    agent_name: str,
    finding_id: str | None,
    status: str,
    steps: list[dict],
    summary: str,
    result_json: dict | None = None,
) -> AgentRun:
    run = AgentRun(
        agent_name=agent_name,
        finding_id=finding_id,
        status=status,
        steps=steps,
        summary=summary,
        result_json=result_json,
        started_at=_now(),
        finished_at=_now() if status != "RUNNING" else None,
    )
    db.add(run)
    return run


def _dataset_context(db: Session, table: CatalogTable):
    """Load the editable dataset context (keyed by service.database)."""
    if not table.service_name or not table.database_name:
        return None
    from ..models import DatasetContext

    key = f"{table.service_name}.{table.database_name}"
    return db.query(DatasetContext).filter(DatasetContext.key == key).first()


def _context_snapshot(ctx, instructions: str | None) -> str | None:
    """Snapshot the context + instructions used for a recommendation."""
    parts = []
    if ctx and ctx.description.strip():
        parts.append(ctx.description.strip())
    if instructions and instructions.strip():
        parts.append(f"[instructions] {instructions.strip()}")
    return "\n\n".join(parts) if parts else None


def _merge_context(context: str | None, facts_block: str | None) -> str | None:
    """Combine dataset context with connected-source facts for the LLM prompt."""
    if facts_block:
        return (
            f"{context}\n\nExtracted from connected sources:\n{facts_block}"
            if context
            else f"Extracted from connected sources:\n{facts_block}"
        )
    return context


def build_prompt_preview(
    db: Session, kind: str, fqn: str, column_name: str | None = None
) -> tuple[str, str]:
    """Build the default (system, user) OpenAI prompt for a generation kind.

    Used by the prompt-preview endpoint so the UI can show the exact prompt that
    would be sent before the user optionally overrides it.
    """
    from . import sources as sources_service
    from .findings import detect_sensitive_columns
    from .llm import (
        classification_prompt,
        column_description_prompt,
        description_prompt,
    )

    table = catalog.get_table(db, fqn)
    if table is None:
        raise ValueError(f"Entity not found: {fqn}")

    ctx = _dataset_context(db, table)
    context = ctx.description.strip() if ctx and ctx.description.strip() else None

    if kind == "table_description":
        dom = catalog.domain_name(db, table)
        cols = catalog.column_names(table)
        instructions = (
            ctx.table_instructions.strip()
            if ctx and ctx.table_instructions.strip()
            else None
        )
        facts_block = sources_service.facts_text(
            sources_service.relevant_facts(
                db, table=table, categories={"description", "general"}
            )
        )
        return description_prompt(
            entity_fqn=table.fqn,
            entity_name=table.name,
            domain=dom,
            columns=cols,
            existing_description=table.description,
            context=_merge_context(context, facts_block),
            instructions=instructions,
        )

    if kind in ("column_description", "classification"):
        col = next((c for c in table.columns if c.name == column_name), None)
        if col is None:
            raise ValueError(f"Column not found: {column_name}")

        if kind == "column_description":
            instructions = (
                ctx.column_instructions.strip()
                if ctx and ctx.column_instructions.strip()
                else None
            )
            facts_block = sources_service.facts_text(
                sources_service.relevant_facts(
                    db, table=table, column_name=col.name,
                    categories={"description", "general"},
                )
            )
            return column_description_prompt(
                column_name=col.name,
                data_type=col.data_type,
                table_name=table.name,
                context=_merge_context(context, facts_block),
                instructions=instructions,
            )

        label = None
        for name, lab in detect_sensitive_columns(table):
            if name == col.name:
                label = lab
                break
        if label is None:
            label = "PersonalData"
        neighbor = _neighboring_classification(db, table, col.name)
        facts_block = sources_service.facts_text(
            sources_service.relevant_facts(
                db, table=table, column_name=col.name,
                categories={"classification", "general"},
            )
        )
        return classification_prompt(
            column_name=col.name,
            data_type=col.data_type,
            table_name=table.name,
            context=context,
            sensitive_label=label,
            neighbor=neighbor,
            facts_block=facts_block,
            existing_classification=col.classification,
        )

    raise ValueError(f"Unknown prompt kind: {kind}")


def _common_owner(db: Session, table: CatalogTable) -> str | None:
    """Most common owner among tables in the same schema."""
    others = (
        db.query(CatalogTable)
        .filter(
            CatalogTable.schema_name == table.schema_name,
            CatalogTable.owner_team_id.isnot(None),
        )
        .all()
    )
    if not others:
        return None
    counts: dict[str, int] = {}
    for t in others:
        if t.owner:
            counts[t.owner.name] = counts.get(t.owner.name, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _domain_team(db: Session, table: CatalogTable) -> str | None:
    """A team that maps to the table's domain (domain name + 'Data Engineering')."""
    dom = catalog.domain_name(db, table)
    if not dom:
        return None
    return f"{dom.title()} Data Engineering"


def _neighboring_classification(db: Session, table: CatalogTable, column_name: str) -> str | None:
    """Look for an existing classification on similarly-named columns."""
    base = column_name.lower()
    for other in db.query(CatalogTable).all():
        for col in other.columns:
            if col.classification and base in col.name.lower():
                return col.classification
    return None


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
def description_agent(
    db: Session, finding: Finding, prompt_override: PromptOverride | None = None
) -> Recommendation:
    table = catalog.get_table(db, finding.entity)
    if table is None:
        raise ValueError(f"Entity not found: {finding.entity}")

    steps: list[dict] = []
    steps.append({"step": "Retrieved entity", "detail": finding.entity, "ok": True})

    dom = catalog.domain_name(db, table)
    steps.append({"step": "Inspected domain", "detail": dom or "none", "ok": True})

    cols = catalog.column_names(table)
    steps.append(
        {"step": "Inspected columns", "detail": f"{len(cols)} column(s)", "ok": True}
    )

    ctx = _dataset_context(db, table)
    context = ctx.description.strip() if ctx and ctx.description.strip() else None
    instructions = (
        ctx.table_instructions.strip() if ctx and ctx.table_instructions.strip() else None
    )
    if context or instructions:
        steps.append(
            {"step": "Loaded dataset context + instructions", "detail": context or "", "ok": True}
        )

    # Extracted knowledge from connected sources (Slack/Teams/files).
    from . import sources as sources_service

    src_facts = sources_service.relevant_facts(
        db, table=table, categories={"description", "general"}
    )
    facts_block = sources_service.facts_text(src_facts)
    if facts_block:
        steps.append(
            {"step": "Loaded source knowledge", "detail": f"{len(src_facts)} fact(s)", "ok": True}
        )

    llm_context = context
    if facts_block:
        llm_context = (
            f"{context}\n\nExtracted from connected sources:\n{facts_block}"
            if context
            else f"Extracted from connected sources:\n{facts_block}"
        )

    llm = get_llm()
    draft = llm.generate_description(
        entity_fqn=table.fqn,
        entity_name=table.name,
        domain=dom,
        columns=cols,
        existing_description=table.description,
        context=llm_context,
        instructions=instructions,
        system_prompt=prompt_override.system_prompt if prompt_override else None,
        user_prompt=prompt_override.user_prompt if prompt_override else None,
    )
    steps.append(
        {
            "step": "Generated candidate",
            "detail": draft.text,
            "ok": True,
            "provider": draft.provider,
        }
    )

    snapshot = _context_snapshot(ctx, instructions)
    if facts_block:
        snapshot = (
            f"{snapshot}\n\nSources:\n{facts_block}"
            if snapshot
            else f"Sources:\n{facts_block}"
        )
    recommendation = Recommendation(
        finding_id=finding.id,
        field="description",
        old_value=table.description,
        new_value=draft.text,
        reasoning_summary=draft.rationale,
        confidence=0.0,  # filled after evidence
        context_snapshot=snapshot,
    )
    db.add(recommendation)
    db.flush()

    # Evidence
    evs: list = []
    evs.append(
        evidence.attach(
            db, type="COLUMN_NAME", value=", ".join(cols[:12]),
            source="catalog", recommendation_id=recommendation.id,
        )
    )
    if dom:
        evs.append(
            evidence.attach(
                db, type="DOMAIN_OWNER", value=dom, source="catalog",
                recommendation_id=recommendation.id,
            )
        )
    if context:
        evs.append(
            evidence.attach(
                db, type="DATASET_CONTEXT", value=context,
                source="user", recommendation_id=recommendation.id,
            )
        )
    for f in src_facts:
        evs.append(
            evidence.attach(
                db, type="SOURCE_EXTRACT", value=f.statement,
                source=f.source.name, recommendation_id=recommendation.id,
            )
        )
    # Schema pattern: how many sibling tables already have descriptions?
    siblings = (
        db.query(CatalogTable)
        .filter(
            CatalogTable.schema_name == table.schema_name,
            CatalogTable.id != table.id,
        )
        .all()
    )
    described = sum(1 for s in siblings if s.description)
    if siblings:
        evs.append(
            evidence.attach(
                db, type="SCHEMA_PATTERN",
                value=f"{described}/{len(siblings)} sibling tables have descriptions",
                source="catalog", recommendation_id=recommendation.id,
            )
        )

    recommendation.confidence = confidence.compute_confidence(
        semantic_confidence=draft.semantic_confidence,
        evidence=evs,
        field="description",
    )

    mode, matched = policy.evaluate(
        db, field="description", confidence=recommendation.confidence
    )
    recommendation.action_mode = mode
    recommendation.policy_id = matched.id if matched else None
    steps.append(
        {
            "step": "Policy evaluation",
            "detail": mode,
            "ok": True,
            "policy": matched.name if matched else "default",
        }
    )

    finding.status = "RECOMMENDED"
    db.flush()
    _record_run(
        db,
        agent_name="DescriptionAgent",
        finding_id=finding.id,
        status="SUCCEEDED",
        steps=steps,
        summary=f"Generated description for {table.fqn} ({mode}).",
        result_json={"recommendation_id": recommendation.id, "confidence": recommendation.confidence},
    )
    return recommendation


def column_description_agent(
    db: Session, finding: Finding, prompt_override: PromptOverride | None = None
) -> Recommendation:
    """Generate a description for a single undocumented column."""
    table_fqn, column_name = finding.entity.rsplit(".", 1)
    table = catalog.get_table(db, table_fqn)
    if table is None:
        raise ValueError(f"Entity not found: {table_fqn}")
    column = next((c for c in table.columns if c.name == column_name), None)
    if column is None:
        raise ValueError(f"Column not found: {column_name}")

    steps: list[dict] = [
        {"step": "Retrieved entity", "detail": finding.entity, "ok": True},
        {
            "step": "Inspected column",
            "detail": f"{column.name} ({column.data_type})",
            "ok": True,
        },
    ]

    ctx = _dataset_context(db, table)
    context = ctx.description.strip() if ctx and ctx.description.strip() else None
    instructions = (
        ctx.column_instructions.strip()
        if ctx and ctx.column_instructions.strip()
        else None
    )
    if context or instructions:
        steps.append(
            {"step": "Loaded dataset context + instructions", "detail": context or "", "ok": True}
        )

    from . import sources as sources_service

    src_facts = sources_service.relevant_facts(
        db, table=table, column_name=column.name, categories={"description", "general"}
    )
    facts_block = sources_service.facts_text(src_facts)
    if facts_block:
        steps.append(
            {"step": "Loaded source knowledge", "detail": f"{len(src_facts)} fact(s)", "ok": True}
        )

    llm_context = context
    if facts_block:
        llm_context = (
            f"{context}\n\nExtracted from connected sources:\n{facts_block}"
            if context
            else f"Extracted from connected sources:\n{facts_block}"
        )

    llm = get_llm()
    draft = llm.generate_column_description(
        column_name=column.name,
        data_type=column.data_type,
        table_name=table.name,
        context=llm_context,
        instructions=instructions,
        system_prompt=prompt_override.system_prompt if prompt_override else None,
        user_prompt=prompt_override.user_prompt if prompt_override else None,
    )
    steps.append(
        {
            "step": "Generated candidate",
            "detail": draft.text,
            "ok": True,
            "provider": draft.provider,
        }
    )

    snapshot = _context_snapshot(ctx, instructions)
    if facts_block:
        snapshot = (
            f"{snapshot}\n\nSources:\n{facts_block}"
            if snapshot
            else f"Sources:\n{facts_block}"
        )
    recommendation = Recommendation(
        finding_id=finding.id,
        field="column_description",
        old_value=column.description,
        new_value=draft.text,
        reasoning_summary=draft.rationale,
        context_snapshot=snapshot,
    )
    db.add(recommendation)
    db.flush()

    evs: list = [
        evidence.attach(
            db, type="COLUMN_NAME",
            value=f"{column.name} ({column.data_type})",
            source="catalog", recommendation_id=recommendation.id,
        )
    ]
    if context:
        evs.append(
            evidence.attach(
                db, type="DATASET_CONTEXT", value=context,
                source="user", recommendation_id=recommendation.id,
            )
        )
    for f in src_facts:
        evs.append(
            evidence.attach(
                db, type="SOURCE_EXTRACT", value=f.statement,
                source=f.source.name, recommendation_id=recommendation.id,
            )
        )
    recommendation.confidence = confidence.compute_confidence(
        semantic_confidence=draft.semantic_confidence, evidence=evs, field="column_description"
    )
    mode, matched = policy.evaluate(
        db, field="column_description", confidence=recommendation.confidence
    )
    recommendation.action_mode = mode
    recommendation.policy_id = matched.id if matched else None

    finding.status = "RECOMMENDED"
    db.flush()
    _record_run(
        db,
        agent_name="ColumnDescriptionAgent",
        finding_id=finding.id,
        status="SUCCEEDED",
        steps=steps,
        summary=f"Suggested column description for {finding.entity}.",
        result_json={"recommendation_id": recommendation.id, "confidence": recommendation.confidence},
    )
    return recommendation


def ownership_agent(
    db: Session, finding: Finding, prompt_override: PromptOverride | None = None
) -> Recommendation:
    table = catalog.get_table(db, finding.entity)
    if table is None:
        raise ValueError(f"Entity not found: {finding.entity}")

    steps: list[dict] = [{"step": "Retrieved entity", "detail": finding.entity, "ok": True}]
    dom = catalog.domain_name(db, table)

    common = _common_owner(db, table)
    if common:
        steps.append(
            {"step": "Examined neighboring tables", "detail": common, "ok": True}
        )
    domain_team = _domain_team(db, table)
    if domain_team:
        steps.append({"step": "Inspected domain", "detail": domain_team, "ok": True})

    candidate = common or domain_team or "Data Platform"
    steps.append({"step": "Generated candidate", "detail": candidate, "ok": True})

    recommendation = Recommendation(
        finding_id=finding.id,
        field="owner",
        old_value=None,
        new_value=candidate,
        reasoning_summary=(
            f"Owner inferred from schema pattern ({common})"
            if common
            else f"Owner inferred from domain ({domain_team})"
        ),
    )
    db.add(recommendation)
    db.flush()

    evs: list = []
    if common:
        siblings = (
            db.query(CatalogTable)
            .filter(
                CatalogTable.schema_name == table.schema_name,
                CatalogTable.owner_team_id.isnot(None),
            )
            .all()
        )
        matching = sum(1 for s in siblings if s.owner and s.owner.name == common)
        evs.append(
            evidence.attach(
                db, type="SCHEMA_PATTERN",
                value=f"{matching}/{len(siblings)} sibling tables owned by {common}",
                source="catalog", recommendation_id=recommendation.id,
            )
        )
    if dom:
        evs.append(
            evidence.attach(
                db, type="DOMAIN_OWNER", value=dom, source="catalog",
                recommendation_id=recommendation.id,
            )
        )

    semantic = 0.72 if common else 0.5
    recommendation.confidence = confidence.compute_confidence(
        semantic_confidence=semantic, evidence=evs, field="owner"
    )
    mode, matched = policy.evaluate(
        db, field="owner", confidence=recommendation.confidence
    )
    recommendation.action_mode = mode
    recommendation.policy_id = matched.id if matched else None

    finding.status = "RECOMMENDED"
    db.flush()
    _record_run(
        db,
        agent_name="OwnershipAgent",
        finding_id=finding.id,
        status="SUCCEEDED",
        steps=steps,
        summary=f"Suggested owner '{candidate}' for {table.fqn}.",
        result_json={"recommendation_id": recommendation.id, "confidence": recommendation.confidence},
    )
    return recommendation


def domain_agent(
    db: Session, finding: Finding, prompt_override: PromptOverride | None = None
) -> Recommendation:
    """Suggest a domain for an entity with no domain, inferred from siblings."""
    table = catalog.get_table(db, finding.entity)
    if table is None:
        raise ValueError(f"Entity not found: {finding.entity}")

    steps: list[dict] = [{"step": "Retrieved entity", "detail": finding.entity, "ok": True}]

    siblings = (
        db.query(CatalogTable)
        .filter(
            CatalogTable.schema_name == table.schema_name,
            CatalogTable.domain_id.isnot(None),
            CatalogTable.id != table.id,
        )
        .all()
    )
    counts: dict[str, int] = {}
    for s in siblings:
        if s.domain:
            counts[s.domain.name] = counts.get(s.domain.name, 0) + 1

    candidate = None
    if counts:
        # Deterministic tie-break by domain name.
        candidate = max(sorted(counts), key=lambda k: counts[k])
    if not candidate:
        candidate = "Sales"
    steps.append({"step": "Examined sibling domains", "detail": candidate, "ok": True})

    recommendation = Recommendation(
        finding_id=finding.id,
        field="domain",
        old_value=None,
        new_value=candidate,
        reasoning_summary=(
            f"Domain inferred from {len(siblings)} sibling tables in the same schema."
        ),
    )
    db.add(recommendation)
    db.flush()

    evs: list = []
    if counts:
        evs.append(
            evidence.attach(
                db, type="SCHEMA_PATTERN",
                value=f"Sibling domains: {counts}",
                source="catalog", recommendation_id=recommendation.id,
            )
        )
    recommendation.confidence = confidence.compute_confidence(
        semantic_confidence=0.6, evidence=evs, field="domain"
    )
    mode, matched = policy.evaluate(
        db, field="domain", confidence=recommendation.confidence
    )
    recommendation.action_mode = mode
    recommendation.policy_id = matched.id if matched else None

    finding.status = "RECOMMENDED"
    db.flush()
    _record_run(
        db,
        agent_name="DomainAgent",
        finding_id=finding.id,
        status="SUCCEEDED",
        steps=steps,
        summary=f"Suggested domain '{candidate}' for {table.fqn}.",
        result_json={"recommendation_id": recommendation.id, "confidence": recommendation.confidence},
    )
    return recommendation


def classification_agent(
    db: Session, finding: Finding, prompt_override: PromptOverride | None = None
) -> Recommendation:
    table_fqn, column_name = finding.entity.rsplit(".", 1)
    table = catalog.get_table(db, table_fqn)
    if table is None:
        raise ValueError(f"Entity not found: {table_fqn}")
    column = next((c for c in table.columns if c.name == column_name), None)
    if column is None:
        raise ValueError(f"Column not found: {column_name}")

    steps: list[dict] = [
        {"step": "Retrieved entity", "detail": finding.entity, "ok": True},
        {"step": "Inspected column name", "detail": column_name, "ok": True},
    ]

    from .findings import detect_sensitive_columns

    label = None
    for name, lab in detect_sensitive_columns(table):
        if name == column_name:
            label = lab
            break
    if label is None:
        # A column with no matched sensitive pattern is still treated as
        # personal data (a valid tag) rather than producing "Sensitive.Sensitive".
        label = "PersonalData"

    neighbor = _neighboring_classification(db, table, column_name)
    if neighbor:
        steps.append(
            {"step": "Examined similar columns", "detail": neighbor, "ok": True}
        )

    ctx = _dataset_context(db, table)
    context = ctx.description.strip() if ctx and ctx.description.strip() else None

    from . import sources as sources_service

    src_facts = sources_service.relevant_facts(
        db, table=table, column_name=column_name, categories={"classification", "general"}
    )
    facts_block = sources_service.facts_text(src_facts)
    if src_facts:
        steps.append(
            {"step": "Loaded source knowledge", "detail": f"{len(src_facts)} fact(s)", "ok": True}
        )

    llm = get_llm()
    try:
        draft = llm.generate_classification(
            column_name=column.name,
            data_type=column.data_type,
            table_name=table.name,
            context=context,
            sensitive_label=label,
            neighbor=neighbor,
            facts_block=facts_block,
            existing_classification=column.classification,
            system_prompt=prompt_override.system_prompt if prompt_override else None,
            user_prompt=prompt_override.user_prompt if prompt_override else None,
        )
        suggested = draft.text.strip() or f"Sensitive.{label.replace(' ', '')}"
        rationale = draft.rationale
        semantic = draft.semantic_confidence
        provider = draft.provider
    except Exception:  # noqa: BLE001
        suggested = neighbor or f"Sensitive.{label.replace(' ', '')}"
        rationale = (
            f"Column name matches sensitive pattern '{label}'. "
            f"{'Consistent with ' + neighbor + ' used on similar columns.' if neighbor else ''}"
        )
        semantic = 0.6
        provider = "heuristic"
        steps.append(
            {"step": "LLM unavailable; used deterministic classification", "detail": suggested, "ok": True}
        )

    steps.append({"step": "Generated candidate", "detail": suggested, "ok": True, "provider": provider})

    recommendation = Recommendation(
        finding_id=finding.id,
        field="classification",
        old_value=column.classification,
        new_value=suggested,
        reasoning_summary=rationale,
    )
    db.add(recommendation)
    db.flush()

    evs: list = []
    evs.append(
        evidence.attach(
            db, type="SENSITIVE_PATTERN", value=f"Column name contains '{column_name}'",
            source="catalog", recommendation_id=recommendation.id,
        )
    )
    if neighbor:
        evs.append(
            evidence.attach(
                db, type="NAME_SIMILARITY",
                value=f"Similar columns classified as {neighbor}",
                source="catalog", recommendation_id=recommendation.id,
            )
        )
    if context:
        evs.append(
            evidence.attach(
                db, type="DATASET_CONTEXT", value=context,
                source="user", recommendation_id=recommendation.id,
            )
        )
    for f in src_facts:
        evs.append(
            evidence.attach(
                db, type="SOURCE_EXTRACT", value=f.statement,
                source=f.source.name, recommendation_id=recommendation.id,
            )
        )

    recommendation.confidence = confidence.compute_confidence(
        semantic_confidence=semantic, evidence=evs, field="classification"
    )
    # Sensitive classification is *always* gated to approval by policy.
    mode, matched = policy.evaluate(
        db, field="classification", confidence=recommendation.confidence
    )
    recommendation.action_mode = mode
    recommendation.policy_id = matched.id if matched else None

    finding.status = "RECOMMENDED"
    db.flush()
    _record_run(
        db,
        agent_name="ClassificationAgent",
        finding_id=finding.id,
        status="SUCCEEDED",
        steps=steps,
        summary=f"Suggested classification '{suggested}' for {finding.entity}.",
        result_json={"recommendation_id": recommendation.id, "confidence": recommendation.confidence},
    )
    return recommendation


def staleness_agent(
    db: Session, finding: Finding, prompt_override: PromptOverride | None = None
) -> Recommendation:
    table = catalog.get_table(db, finding.entity)
    if table is None:
        raise ValueError(f"Entity not found: {finding.entity}")

    last = (
        "never queried"
        if table.last_queried_at is None
        else f"last queried {table.last_queried_at:%Y-%m-%d}"
    )
    steps: list[dict] = [
        {"step": "Retrieved entity", "detail": finding.entity, "ok": True},
        {"step": "Inspected usage", "detail": last, "ok": True},
        {"step": "Inspected lineage", "detail": "no downstream consumers", "ok": True},
    ]

    recommendation = Recommendation(
        finding_id=finding.id,
        field="stale_review",
        old_value=None,
        new_value="Review for deprecation",
        reasoning_summary=(
            f"Table {last}; no downstream consumers detected. "
            "Recommend human review for deprecation."
        ),
        action_mode="INFORMATION_ONLY",
    )
    db.add(recommendation)
    db.flush()

    evs: list = []
    evs.append(
        evidence.attach(
            db, type="DOWNSTREAM_LINEAGE", value="No downstream consumers",
            source="catalog", recommendation_id=recommendation.id,
        )
    )
    evs.append(
        evidence.attach(
            db, type="COLUMN_NAME", value=last, source="catalog",
            recommendation_id=recommendation.id,
        )
    )
    recommendation.confidence = confidence.compute_confidence(
        semantic_confidence=0.6, evidence=evs, field="stale_review"
    )

    finding.status = "RECOMMENDED"
    db.flush()
    _record_run(
        db,
        agent_name="StalenessAgent",
        finding_id=finding.id,
        status="SUCCEEDED",
        steps=steps,
        summary=f"Flagged {finding.entity} for deprecation review.",
        result_json={"recommendation_id": recommendation.id},
    )
    return recommendation


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
_AGENT_MAP = {
    "MISSING_DESCRIPTION": description_agent,
    "MISSING_COLUMN_DESCRIPTION": column_description_agent,
    "MISSING_OWNER": ownership_agent,
    "MISSING_DOMAIN": domain_agent,
    "MISSING_CLASSIFICATION": classification_agent,
    "STALE_ENTITY": staleness_agent,
}


def investigate(
    db: Session,
    finding: Finding,
    *,
    auto_apply: bool = True,
    prompt_override: PromptOverride | None = None,
) -> list[Recommendation]:
    """Run the appropriate agent for a finding and (optionally) apply AUTO_APPLY
    results. The explicit generate/regenerate path passes ``auto_apply=False``
    so the suggestion always goes through human approval."""
    agent = _AGENT_MAP.get(finding.type)
    if agent is None:
        # No reasoning agent for this type; record an information run.
        _record_run(
            db,
            agent_name="RuleEngine",
            finding_id=finding.id,
            status="SUCCEEDED",
            steps=[{"step": "Deterministic check", "detail": finding.type, "ok": True}],
            summary=f"Finding '{finding.type}' handled deterministically.",
        )
        return []

    # Assign the next version for this finding (traceable suggestion history).
    # Compute BEFORE the agent flushes the new recommendation so it isn't
    # counted against itself.
    max_v = (
        db.query(func.max(Recommendation.version))
        .filter(Recommendation.finding_id == finding.id)
        .scalar()
        or 0
    )

    recommendation = agent(db, finding, prompt_override=prompt_override)
    recommendation.version = max_v + 1
    db.flush()

    # Auto-apply safe, high-confidence recommendations immediately (unless the
    # caller is forcing human review, e.g. the generate/regenerate button).
    if auto_apply and recommendation.action_mode == "AUTO_APPLY":
        from .apply import apply_recommendation

        apply_recommendation(db, recommendation=recommendation, applied_by="steward")
    elif not auto_apply and recommendation.action_mode == "AUTO_APPLY":
        # Keep it pending for a human to approve (e.g. explicit generate/regenerate).
        recommendation.action_mode = "REQUIRE_APPROVAL"

    db.commit()
    return [recommendation]


def investigate_all_open(db: Session) -> tuple[int, list[str]]:
    """Investigate every OPEN finding. Returns (success_count, errors).

    LLM failures (e.g. invalid/missing API key) are caught per-finding so a
    scan never crashes the whole run; the finding is left OPEN with a FAILED
    run record and the error message is returned for the caller to surface.
    """
    ids = [f.id for f in db.query(Finding).filter(Finding.status == "OPEN").all()]
    count = 0
    errors: list[str] = []
    for fid in ids:
        finding = db.get(Finding, fid)
        if finding is None:
            continue
        try:
            investigate(db, finding)
            count += 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            _record_run(
                db,
                agent_name="Error",
                finding_id=fid,
                status="FAILED",
                steps=[{"step": "Investigation failed", "detail": str(e), "ok": False}],
                summary=str(e),
            )
            db.commit()
            errors.append(str(e))
    return count, errors
