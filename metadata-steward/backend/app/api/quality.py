"""Agent quality monitoring + evaluation runs.

Live metrics come from the steward database (they work without MLflow);
evaluation runs and traces are read from / linked to MLflow.
"""
from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..evals.suites import calibration, decision_records, run_suite
from ..models import AgentRun, Recommendation
from ..services import observability as obs

router = APIRouter(prefix="/api/quality", tags=["quality"])

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


@router.get("/summary")
def summary(days: int = 30, db: Session = Depends(get_db)):
    since = _now() - timedelta(days=days)

    # --- agents: volume, failures, latency -------------------------------- #
    runs = db.query(AgentRun).filter(AgentRun.started_at >= since).all()
    by_agent: dict[str, list[AgentRun]] = defaultdict(list)
    for r in runs:
        if r.agent_name != "RuleEngine":
            by_agent[r.agent_name].append(r)
    agents = []
    for name, rs in sorted(by_agent.items(), key=lambda kv: -len(kv[1])):
        lat = [
            (r.finished_at - r.started_at).total_seconds()
            for r in rs
            if r.finished_at and r.trace_id is not None and r.finished_at > r.started_at
        ]
        failed = sum(1 for r in rs if r.status == "FAILED")
        agents.append(
            {
                "agent": name,
                "runs": len(rs),
                "failed": failed,
                "failure_rate": round(failed / len(rs), 4) if rs else 0.0,
                "latency_p50_s": round(median(lat), 2) if lat else None,
                "latency_p95_s": round(_pct(lat, 0.95), 2) if lat else None,
                "traced": sum(1 for r in rs if r.trace_id),
            }
        )

    # --- human decisions: acceptance, edits, calibration ------------------ #
    decisions = [d for d in decision_records(db) if not d["decided_at"] or d["decided_at"] >= since.isoformat()]
    by_field: dict[str, list[dict]] = defaultdict(list)
    for d in decisions:
        by_field[d["field"]].append(d)
    recs = db.query(Recommendation).filter(Recommendation.created_at >= since).all()
    recs_by_field: dict[str, list[Recommendation]] = defaultdict(list)
    for r in recs:
        recs_by_field[r.field].append(r)
    fields = []
    for fld in sorted(set(by_field) | set(recs_by_field)):
        ds, rs = by_field.get(fld, []), recs_by_field.get(fld, [])
        accepted = [d for d in ds if d["accepted"]]
        fields.append(
            {
                "field": fld,
                "recommendations": len(rs),
                "auto_applied": sum(1 for r in rs if r.status == "APPLIED" and r.action_mode == "AUTO_APPLY"),
                "pending": sum(1 for r in rs if r.status == "PENDING"),
                "reviewed": len(ds),
                "acceptance_rate": round(len(accepted) / len(ds), 4) if ds else None,
                "edit_rate": round(mean(1.0 if d["edited"] else 0.0 for d in accepted), 4) if accepted else None,
                "avg_confidence": round(mean(r.confidence for r in rs), 4) if rs else None,
            }
        )
    buckets, brier, ece = calibration(decisions)

    # --- daily trend ------------------------------------------------------- #
    trend: dict[str, dict] = {}
    for i in range(min(days, 30) - 1, -1, -1):
        day = (_now() - timedelta(days=i)).date().isoformat()
        trend[day] = {"day": day, "recommendations": 0, "accepted": 0, "rejected": 0}
    for r in recs:
        day = r.created_at.date().isoformat()
        if day in trend:
            trend[day]["recommendations"] += 1
    for d in decisions:
        day = (d["decided_at"] or "")[:10]
        if day in trend:
            trend[day]["accepted" if d["accepted"] else "rejected"] += 1

    recent = (
        db.query(AgentRun)
        .filter(AgentRun.trace_id.isnot(None))
        .order_by(AgentRun.started_at.desc())
        .limit(10)
        .all()
    )
    reviewed = len(decisions)
    return {
        "window_days": days,
        "totals": {
            "agent_runs": sum(a["runs"] for a in agents),
            "failure_rate": round(
                sum(a["failed"] for a in agents) / max(1, sum(a["runs"] for a in agents)), 4
            ),
            "reviewed": reviewed,
            "acceptance_rate": round(mean(1.0 if d["accepted"] else 0.0 for d in decisions), 4) if decisions else None,
            "edit_rate": round(
                mean(1.0 if d["edited"] else 0.0 for d in decisions if d["accepted"]), 4
            )
            if any(d["accepted"] for d in decisions)
            else None,
            "brier_score": brier if decisions else None,
            "calibration_error": ece if decisions else None,
        },
        "agents": agents,
        "fields": fields,
        "calibration": buckets,
        "trend": list(trend.values()),
        "recent_traces": [
            {
                "agent": r.agent_name,
                "finding_id": r.finding_id,
                "status": r.status,
                "started_at": r.started_at,
                "latency_s": round((r.finished_at - r.started_at).total_seconds(), 2) if r.finished_at else None,
                "trace_id": r.trace_id,
                "trace_url": obs.trace_url(r.trace_id),
            }
            for r in recent
        ],
        "mlflow": obs.status(),
    }


# --------------------------------------------------------------------------- #
# Evaluation runs
# --------------------------------------------------------------------------- #
def _run_job(job_id: str, suite: str, limit: int | None) -> None:
    try:
        with SessionLocal() as db:
            result = run_suite(db, suite, limit=limit)
        with _jobs_lock:
            _jobs[job_id].update(
                status="SUCCEEDED",
                finished_at=_now(),
                metrics=result.metrics,
                run_id=result.run_id,
                run_url=result.run_url,
            )
    except Exception as e:  # noqa: BLE001
        with _jobs_lock:
            _jobs[job_id].update(status="FAILED", finished_at=_now(), error=str(e)[:1000])


@router.post("/evals/run")
def start_eval(suite: str = "golden", limit: int = 20):
    if suite not in ("golden", "decisions"):
        raise HTTPException(status_code=400, detail="suite must be 'golden' or 'decisions'")
    with _jobs_lock:
        if any(j["status"] == "RUNNING" for j in _jobs.values()):
            raise HTTPException(status_code=409, detail="An evaluation is already running.")
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            "id": job_id,
            "suite": suite,
            "limit": limit,
            "status": "RUNNING",
            "started_at": _now(),
            "finished_at": None,
            "metrics": None,
            "run_id": None,
            "run_url": None,
            "error": None,
        }
    threading.Thread(target=_run_job, args=(job_id, suite, limit or None), daemon=True).start()
    return _jobs[job_id]


@router.get("/evals/jobs")
def list_jobs():
    with _jobs_lock:
        return sorted(_jobs.values(), key=lambda j: j["started_at"], reverse=True)[:20]


@router.get("/evals/runs")
def list_runs(limit: int = 20):
    """Past evaluation runs, read from MLflow."""
    if not obs.enabled():
        return {"available": False, "error": obs.status()["error"], "runs": []}
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        exp = client.get_experiment_by_name(obs.EVAL_EXPERIMENT)
        if exp is None:
            return {"available": True, "runs": []}
        runs = client.search_runs([exp.experiment_id], order_by=["attributes.start_time DESC"], max_results=limit)
        return {
            "available": True,
            "runs": [
                {
                    "run_id": r.info.run_id,
                    "name": r.info.run_name,
                    "suite": r.data.tags.get("suite"),
                    "status": r.info.status,
                    "start_time": r.info.start_time,
                    "metrics": r.data.metrics,
                    "params": r.data.params,
                    "url": f"{obs.UI_URL}/#/experiments/{exp.experiment_id}/runs/{r.info.run_id}"
                    if obs.UI_URL
                    else None,
                }
                for r in runs
            ],
        }
    except Exception as e:  # noqa: BLE001
        return {"available": False, "error": str(e)[:500], "runs": []}
