"""Agent run endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgentRun
from ..schemas import AgentRunOut

router = APIRouter(prefix="/api/agent-runs", tags=["agents"])


@router.get("", response_model=list[AgentRunOut])
def list_agent_runs(agent_name: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    query = db.query(AgentRun).order_by(desc(AgentRun.started_at))
    if agent_name:
        query = query.filter(AgentRun.agent_name == agent_name)
    return [AgentRunOut.model_validate(r) for r in query.limit(limit).all()]


@router.get("/{run_id}", response_model=AgentRunOut)
def get_agent_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return AgentRunOut.model_validate(run)
