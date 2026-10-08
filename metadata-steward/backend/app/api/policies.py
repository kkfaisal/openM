"""Policy endpoints (configurable from the UI)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Policy
from ..schemas import PolicyCreate, PolicyOut, PolicyUpdate

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)):
    policies = db.query(Policy).order_by(asc(Policy.priority)).all()
    return [PolicyOut.model_validate(p) for p in policies]


@router.post("", response_model=PolicyOut)
def create_policy(body: PolicyCreate, db: Session = Depends(get_db)):
    policy = Policy(**body.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyOut.model_validate(policy)


@router.put("/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: str, body: PolicyUpdate, db: Session = Depends(get_db)):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    policy.version += 1
    db.commit()
    db.refresh(policy)
    return PolicyOut.model_validate(policy)
