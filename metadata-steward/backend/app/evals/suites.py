"""Evaluation suite implementations (see package docstring)."""
from __future__ import annotations

import csv
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

GOLDEN_CSV = Path(__file__).parent / "data" / "ecommerce_golden.csv"
GOLDEN_DATASET = "ecommerce_postgres.ecommerce"


@dataclass
class SuiteResult:
    suite: str
    metrics: dict[str, float]
    params: dict[str, str]
    rows: list[dict] = field(default_factory=list)
    run_id: str | None = None
    run_url: str | None = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _is_sensitive(label: str | None) -> bool:
    lab = (label or "").strip().lower()
    return bool(lab) and lab not in ("none", "public", "nonsensitive", "non-sensitive", "n/a")


def _norm_label(label: str | None) -> str:
    return (label or "").strip().split(".")[-1].lower()


def _detect(column: str) -> str | None:
    """The production rule-based detector (agents only classify its hits)."""
    from ..services.findings import _SENSITIVE_PATTERNS

    for pattern, label in _SENSITIVE_PATTERNS:
        if pattern.search(column):
            return label
    return None


def load_golden(limit: int | None = None) -> list[dict]:
    with GOLDEN_CSV.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("column")]
    if limit:
        # Keep every sensitive row so classification is always exercised.
        sensitive = [r for r in rows if r.get("classification")]
        other = [r for r in rows if not r.get("classification")]
        rows = sensitive[:limit] + other[: max(0, limit - len(sensitive[:limit]))]
    return rows


def _golden_source_ids(db: Session) -> list[str]:
    from ..models import MetadataSource

    return [
        s.id
        for s in db.query(MetadataSource).all()
        if "data_dictionary" in (s.name or "").lower() or "golden" in (s.name or "").lower()
    ]


def _context(table: str, column: str, exclude: list[str]) -> str | None:
    from ..services import rag

    try:
        hits = rag.search(
            f"What does the {column} column in the {table} table mean? {column.replace('_', ' ')}",
            dataset_key=GOLDEN_DATASET,
            k=4,
            exclude_source_ids=exclude,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Eval retrieval failed: %s", e)
        return None
    if not hits:
        return None
    return "Retrieved source passages:\n" + "\n".join(f"- {h.text[:500]}" for h in hits)


# --------------------------------------------------------------------------- #
# Golden suite
# --------------------------------------------------------------------------- #
def run_golden(db: Session, *, limit: int | None = 20) -> SuiteResult:
    from ..services import rag
    from ..services import observability as obs
    from ..services.llm import get_llm

    llm = get_llm()
    provider = type(llm).__name__
    exclude = _golden_source_ids(db)
    rows_in = load_golden(limit)
    out_rows: list[dict] = []

    for r in rows_in:
        table, column, dtype = r["table"], r["column"], r.get("data_type") or "VARCHAR"
        ref_desc, ref_cls = (r.get("description") or "").strip(), (r.get("classification") or "").strip()
        rag_ctx = _context(table, column, exclude)
        detected = _detect(column)
        for variant, ctx in (("no_context", None), ("rag", rag_ctx)):
            t0 = time.perf_counter()
            with obs.span(f"eval:{variant}", "AGENT", table=table, column=column) as span:
                obs.tag_trace(eval_suite="golden", variant=variant)
                span.set_inputs({"table": table, "column": column, "data_type": dtype, "context": ctx})
                error = None
                cls = ""
                try:
                    desc = llm.generate_column_description(
                        column_name=column, data_type=dtype, table_name=table, context=ctx
                    ).text
                    if ref_cls:
                        cls = llm.generate_classification(
                            column_name=column,
                            data_type=dtype,
                            table_name=table,
                            sensitive_label=detected,
                            facts_block=ctx,
                        ).text
                except Exception as e:  # noqa: BLE001
                    desc, error = "", str(e)
                span.set_outputs({"description": desc, "classification": cls})
            out_rows.append(
                {
                    "table": table,
                    "column": column,
                    "variant": variant,
                    "has_context": bool(ctx),
                    "reference_description": ref_desc,
                    "predicted_description": desc,
                    "reference_classification": ref_cls,
                    "predicted_classification": cls,
                    "detected_label": detected,
                    "latency_s": round(time.perf_counter() - t0, 3),
                    "error": error,
                }
            )

    # Score descriptions by embedding similarity to the reference.
    pairs = [(i, x) for i, x in enumerate(out_rows) if x["predicted_description"] and x["reference_description"]]
    if pairs:
        vecs = rag.embed(
            [x["reference_description"] for _, x in pairs] + [x["predicted_description"] for _, x in pairs]
        )
        n = len(pairs)
        for k, (i, _) in enumerate(pairs):
            out_rows[i]["description_similarity"] = round(_cosine(vecs[k], vecs[n + k]), 4)
    for x in out_rows:
        x.setdefault("description_similarity", 0.0)
        x["ref_sensitive"] = _is_sensitive(x["reference_classification"])
        x["detected"] = x["detected_label"] is not None
        x["label_exact"] = x["ref_sensitive"] and _norm_label(x["reference_classification"]) == _norm_label(
            x["predicted_classification"]
        )

    metrics: dict[str, float] = {}
    # Detection is rule-based (identical across variants): score it once.
    base = [x for x in out_rows if x["variant"] == "no_context"]
    tp = sum(1 for x in base if x["ref_sensitive"] and x["detected"])
    fp = sum(1 for x in base if not x["ref_sensitive"] and x["detected"])
    fn = sum(1 for x in base if x["ref_sensitive"] and not x["detected"])
    metrics["detection/precision"] = round(tp / (tp + fp), 4) if tp + fp else 0.0
    metrics["detection/recall"] = round(tp / (tp + fn), 4) if tp + fn else 0.0

    for variant in ("no_context", "rag"):
        vs = [x for x in out_rows if x["variant"] == variant and not x["error"]]
        if not vs:
            continue
        sens = [x for x in vs if x["ref_sensitive"]]
        metrics.update(
            {
                f"{variant}/description_similarity": round(mean(x["description_similarity"] for x in vs), 4),
                f"{variant}/label_exact_match": round(mean(1.0 if x["label_exact"] else 0.0 for x in sens), 4)
                if sens
                else 0.0,
                f"{variant}/latency_s_mean": round(mean(x["latency_s"] for x in vs), 3),
            }
        )
    for m in ("description_similarity", "label_exact_match"):
        if f"rag/{m}" in metrics and f"no_context/{m}" in metrics:
            metrics[f"rag_lift/{m}"] = round(metrics[f"rag/{m}"] - metrics[f"no_context/{m}"], 4)
    metrics["errors"] = float(sum(1 for x in out_rows if x["error"]))
    metrics["cases"] = float(len(rows_in))
    rag_rows = [x for x in out_rows if x["variant"] == "rag"]
    metrics["rag_coverage"] = round(mean(1.0 if x["has_context"] else 0.0 for x in rag_rows), 4) if rag_rows else 0.0

    params = {
        "llm_provider": provider,
        "llm_model": getattr(llm, "model", "heuristic"),
        "embedding_model": rag.MODEL,
        "golden_file": GOLDEN_CSV.name,
        "excluded_sources": str(len(exclude)),
        "limit": str(limit or "all"),
    }
    return SuiteResult(suite="golden", metrics=metrics, params=params, rows=out_rows)


# --------------------------------------------------------------------------- #
# Decisions suite
# --------------------------------------------------------------------------- #
def decision_records(db: Session) -> list[dict]:
    """One row per human-reviewed recommendation."""
    from ..models import Approval, Recommendation

    rows = []
    q = db.query(Approval, Recommendation).join(Recommendation, Approval.recommendation_id == Recommendation.id)
    for a, r in q.all():
        accepted = a.decision in ("APPROVED", "MODIFIED")
        edited = (
            accepted
            and a.modified_value is not None
            and a.modified_value.strip() != (r.new_value or "").strip()
        )
        rows.append(
            {
                "recommendation_id": r.id,
                "field": r.field,
                "confidence": float(r.confidence or 0.0),
                "accepted": accepted,
                "edited": bool(edited),
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "trace_id": r.trace_id,
            }
        )
    return rows


def calibration(rows: list[dict], bins: int = 5, lo: float = 0.5) -> tuple[list[dict], float, float]:
    """Reliability buckets, Brier score and expected calibration error."""
    if not rows:
        return [], 0.0, 0.0
    width = (1.0 - lo) / bins
    buckets = []
    for b in range(bins):
        a, z = lo + b * width, lo + (b + 1) * width
        xs = [r for r in rows if (a <= r["confidence"] < z) or (b == bins - 1 and r["confidence"] >= z)]
        if b == 0:
            xs += [r for r in rows if r["confidence"] < lo]
        if xs:
            buckets.append(
                {
                    "bucket": f"{a:.2f}-{z:.2f}",
                    "count": len(xs),
                    "mean_confidence": round(mean(r["confidence"] for r in xs), 4),
                    "acceptance_rate": round(mean(1.0 if r["accepted"] else 0.0 for r in xs), 4),
                }
            )
    brier = mean((r["confidence"] - (1.0 if r["accepted"] else 0.0)) ** 2 for r in rows)
    ece = sum(
        b["count"] / len(rows) * abs(b["mean_confidence"] - b["acceptance_rate"]) for b in buckets
    )
    return buckets, round(brier, 4), round(ece, 4)


def run_decisions(db: Session) -> SuiteResult:
    rows = decision_records(db)
    buckets, brier, ece = calibration(rows)
    metrics: dict[str, float] = {
        "decisions": float(len(rows)),
        "acceptance_rate": round(mean(1.0 if r["accepted"] else 0.0 for r in rows), 4) if rows else 0.0,
        "edit_rate": round(mean(1.0 if r["edited"] else 0.0 for r in [r for r in rows if r["accepted"]]), 4)
        if any(r["accepted"] for r in rows)
        else 0.0,
        "brier_score": brier,
        "expected_calibration_error": ece,
    }
    for fld in sorted({r["field"] for r in rows}):
        xs = [r for r in rows if r["field"] == fld]
        metrics[f"{fld}/acceptance_rate"] = round(mean(1.0 if r["accepted"] else 0.0 for r in xs), 4)
        metrics[f"{fld}/count"] = float(len(xs))
    return SuiteResult(
        suite="decisions",
        metrics=metrics,
        params={"source": "approvals table"},
        rows=rows + [{"calibration_bucket": b} for b in buckets],
    )


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def log_to_mlflow(result: SuiteResult) -> SuiteResult:
    from ..services import observability as obs

    if not obs.enabled():
        return result
    import mlflow

    mlflow.set_experiment(obs.EVAL_EXPERIMENT)
    try:
        with mlflow.start_run(run_name=f"{result.suite}-{time.strftime('%Y%m%d-%H%M%S')}") as run:
            mlflow.set_tags({"suite": result.suite, "app": "metalens"})
            mlflow.log_params(result.params)
            mlflow.log_metrics({k.replace("/", "."): v for k, v in result.metrics.items()})
            if result.rows:
                import pandas as pd

                mlflow.log_table(pd.DataFrame(result.rows), artifact_file=f"{result.suite}_rows.json")
            result.run_id = run.info.run_id
            exp_id = run.info.experiment_id
            if obs.UI_URL:
                result.run_url = f"{obs.UI_URL}/#/experiments/{exp_id}/runs/{run.info.run_id}"
    finally:
        mlflow.set_experiment(obs.EXPERIMENT)
    return result


def run_suite(db: Session, suite: str, *, limit: int | None = 20) -> SuiteResult:
    if suite == "golden":
        result = run_golden(db, limit=limit)
    elif suite == "decisions":
        result = run_decisions(db)
    else:
        raise ValueError(f"Unknown suite: {suite}")
    return log_to_mlflow(result)
