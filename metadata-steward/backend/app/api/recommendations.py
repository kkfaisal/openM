"""Recommendations + approval workflow endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Approval, Recommendation
from ..schemas import ApprovalOut, ApprovalRequest, RecommendationOut
from ..services import apply, audit

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def _to_out(r: Recommendation) -> RecommendationOut:
    return RecommendationOut.model_validate(r)


def _get(db: Session, rec_id: str) -> Recommendation:
    rec = (
        db.query(Recommendation)
        .options(selectinload(Recommendation.evidence))
        .filter(Recommendation.id == rec_id)
        .first()
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.get("", response_model=list[RecommendationOut])
def list_recommendations(
    status: str | None = None,
    action_mode: str | None = None,
    field: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(Recommendation).order_by(desc(Recommendation.created_at))
    if status:
        query = query.filter(Recommendation.status == status)
    if action_mode:
        query = query.filter(Recommendation.action_mode == action_mode)
    if field:
        query = query.filter(Recommendation.field == field)
    return [_to_out(r) for r in query.limit(limit).all()]


@router.get("/{recommendation_id}", response_model=RecommendationOut)
def get_recommendation(recommendation_id: str, db: Session = Depends(get_db)):
    return _to_out(_get(db, recommendation_id))


def _resolve(
    db: Session,
    rec: Recommendation,
    *,
    decision: str,
    comment: str | None,
    modified_value: str | None,
    decided_by: str,
) -> RecommendationOut:
    if rec.status != "PENDING":
        raise HTTPException(status_code=409, detail="Recommendation already resolved")

    db.add(
        Approval(
            recommendation_id=rec.id,
            decision=decision,
            comment=comment,
            modified_value=modified_value,
            decided_by=decided_by,
        )
    )

    if decision == "APPROVED":
        apply.apply_recommendation(
            db, recommendation=rec, value=modified_value, applied_by=decided_by
        )
    elif decision == "MODIFIED":
        apply.apply_recommendation(
            db, recommendation=rec, value=modified_value, applied_by=decided_by
        )
    elif decision == "REJECTED":
        rec.status = "REJECTED"
        rec.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        from ..models import Finding

        finding = db.query(Finding).filter(Finding.id == rec.finding_id).first()
        if finding:
            finding.status = "REJECTED"
        audit.record(
            db,
            action="REJECT_RECOMMENDATION",
            actor=decided_by,
            actor_type="human",
            entity=finding.entity if finding else None,
            field=rec.field,
            old_value=rec.old_value,
            new_value=rec.new_value,
            detail=comment,
            confidence=rec.confidence,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid decision")

    db.commit()
    db.refresh(rec)
    return _to_out(rec)


@router.post("/{recommendation_id}/approve", response_model=RecommendationOut)
def approve(
    recommendation_id: str,
    body: ApprovalRequest,
    db: Session = Depends(get_db),
):
    rec = _get(db, recommendation_id)
    return _resolve(
        db,
        rec,
        decision="APPROVED",
        comment=body.comment,
        modified_value=body.modified_value,
        decided_by=body.decided_by,
    )


@router.post("/{recommendation_id}/reject", response_model=RecommendationOut)
def reject(
    recommendation_id: str,
    body: ApprovalRequest,
    db: Session = Depends(get_db),
):
    rec = _get(db, recommendation_id)
    return _resolve(
        db,
        rec,
        decision="REJECTED",
        comment=body.comment,
        modified_value=body.modified_value,
        decided_by=body.decided_by,
    )


@router.post("/{recommendation_id}/modify", response_model=RecommendationOut)
def modify(
    recommendation_id: str,
    body: ApprovalRequest,
    db: Session = Depends(get_db),
):
    if not body.modified_value:
        raise HTTPException(status_code=400, detail="modified_value is required")
    rec = _get(db, recommendation_id)
    return _resolve(
        db,
        rec,
        decision="MODIFIED",
        comment=body.comment,
        modified_value=body.modified_value,
        decided_by=body.decided_by,
    )


@router.post("/{recommendation_id}/select", response_model=RecommendationOut)
def select_version(recommendation_id: str, db: Session = Depends(get_db)):
    """Make a previous (superseded) recommendation the current one again, so
    the user can opt into any version's suggestion."""
    rec = _get(db, recommendation_id)
    for other in (
        db.query(Recommendation)
        .filter(
            Recommendation.finding_id == rec.finding_id,
            Recommendation.status == "PENDING",
            Recommendation.id != rec.id,
        )
        .all()
    ):
        other.status = "SUPERSEDED"
    rec.status = "PENDING"
    db.commit()
    db.refresh(rec)
    return _to_out(rec)
