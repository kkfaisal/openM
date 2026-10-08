"""Findings endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Finding
from ..schemas import FindingDetail, FindingOut, RegenerateRequest
from ..services import agents
from ..services.flags import get_bool_flag
from ..services.llm import PromptOverride

router = APIRouter(prefix="/api/findings", tags=["findings"])


def _to_out(f: Finding) -> FindingOut:
    return FindingOut.model_validate(f)


def _to_detail(f: Finding) -> FindingDetail:
    return FindingDetail.model_validate(f)


@router.get("", response_model=list[FindingOut])
def list_findings(
    type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    dataset: str | None = None,
    q: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(Finding).order_by(desc(Finding.detected_at))
    if type:
        query = query.filter(Finding.type == type)
    if severity:
        query = query.filter(Finding.severity == severity)
    if status:
        query = query.filter(Finding.status == status)
    if domain:
        query = query.filter(Finding.domain == domain)
    if dataset:
        query = query.filter(Finding.entity.like(f"{dataset}.%"))
    if q:
        query = query.filter(Finding.entity.ilike(f"%{q}%"))
    return [_to_out(f) for f in query.limit(limit).all()]


@router.get("/{finding_id}", response_model=FindingDetail)
def get_finding(finding_id: str, db: Session = Depends(get_db)):
    finding = (
        db.query(Finding)
        .options(
            selectinload(Finding.evidence),
            selectinload(Finding.recommendations),
        )
        .filter(Finding.id == finding_id)
        .first()
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return _to_detail(finding)


@router.post("/{finding_id}/investigate", response_model=FindingDetail)
def investigate_finding(finding_id: str, db: Session = Depends(get_db)):
    from ..config import openai_api_key

    if not openai_api_key():
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key is not configured. Add it in Settings → OpenAI API Key.",
        )
    finding = (
        db.query(Finding)
        .options(
            selectinload(Finding.evidence),
            selectinload(Finding.recommendations),
        )
        .filter(Finding.id == finding_id)
        .first()
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    try:
        agents.investigate(db, finding)
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(finding)
    return _to_detail(finding)


@router.post("/{finding_id}/regenerate", response_model=FindingDetail)
def regenerate_finding(
    finding_id: str,
    body: RegenerateRequest | None = None,
    db: Session = Depends(get_db),
):
    """Regenerate the recommendation for a single finding (column/table level),
    keeping the previous suggestion as a version."""
    from ..config import openai_api_key

    if not openai_api_key():
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key is not configured. Add it in Settings → OpenAI API Key.",
        )
    finding = (
        db.query(Finding)
        .options(
            selectinload(Finding.evidence),
            selectinload(Finding.recommendations),
        )
        .filter(Finding.id == finding_id)
        .first()
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Supersede the current pending suggestion (keep as version history).
    for r in list(finding.recommendations):
        if r.status == "PENDING":
            r.status = "SUPERSEDED"
    finding.status = "OPEN"
    db.commit()

    prompt_override = None
    if get_bool_flag(db, "enable_prompt_editing") and body is not None:
        if body.system_prompt is not None or body.user_prompt is not None:
            prompt_override = PromptOverride(
                system_prompt=body.system_prompt, user_prompt=body.user_prompt
            )

    try:
        agents.investigate(db, finding, prompt_override=prompt_override)
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(finding)
    return _to_detail(finding)
