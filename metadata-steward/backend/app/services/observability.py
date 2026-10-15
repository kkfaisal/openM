"""Agent observability with MLflow (tracing, human feedback, evaluation).

* Every agent investigation is an MLflow trace: an AGENT span wrapping
  RETRIEVER spans (RAG) and CHAT_MODEL spans (each LLM call, with model,
  prompts, output and token usage).
* Human decisions in the approval inbox are logged back onto the trace as
  feedback assessments, so production quality (acceptance / edit rate) can
  be analysed per agent, prompt and model in MLflow.
* Offline evaluation runs (``app.evals``) are logged to the same tracking
  server.

Everything is best-effort: when ``MLFLOW_TRACKING_URI`` is unset or the
server is down, these helpers become no-ops and the app keeps working.
"""
from __future__ import annotations

import contextlib
import functools
import logging
import os
import threading
import time
from typing import Any, Callable, Iterator

from .. import config as _config  # noqa: F401  (loads backend/.env before reading env)

log = logging.getLogger(__name__)

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI") or None
# Browser-facing URL of the MLflow UI (may differ from the internal URI in Docker).
UI_URL = (os.getenv("MLFLOW_UI_URL") or TRACKING_URI or "").rstrip("/") or None
EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "MetaLens Agents")
EVAL_EXPERIMENT = os.getenv("MLFLOW_EVAL_EXPERIMENT", "MetaLens Evaluations")

_state = {"ready": False, "error": None, "experiment_id": None, "checked_at": 0.0}
_lock = threading.Lock()


def _mlflow():
    import mlflow

    return mlflow


def init(force: bool = False) -> bool:
    """Connect to MLflow once (re-tried at most every 60s after a failure)."""
    if not TRACKING_URI:
        _state["error"] = "MLFLOW_TRACKING_URI is not set"
        return False
    with _lock:
        if _state["ready"] and not force:
            return True
        if not force and time.time() - _state["checked_at"] < 60 and _state["error"]:
            return False
        _state["checked_at"] = time.time()
        try:
            os.environ.setdefault("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "true")
            os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
            os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
            mlflow = _mlflow()
            mlflow.set_tracking_uri(TRACKING_URI)
            exp = mlflow.set_experiment(EXPERIMENT)
            _state.update(ready=True, error=None, experiment_id=exp.experiment_id)
            log.info("MLflow tracing enabled at %s (experiment %s)", TRACKING_URI, EXPERIMENT)
            return True
        except Exception as e:  # noqa: BLE001
            _state.update(ready=False, error=str(e)[:500])
            log.warning("MLflow unavailable (%s); tracing disabled for now.", e)
            return False


def enabled() -> bool:
    return bool(TRACKING_URI) and init()


def status() -> dict:
    ok = enabled()
    return {
        "enabled": bool(TRACKING_URI),
        "ready": ok,
        "tracking_uri": TRACKING_URI,
        "ui_url": UI_URL,
        "experiment": EXPERIMENT,
        "experiment_id": _state["experiment_id"],
        "eval_experiment": EVAL_EXPERIMENT,
        "error": None if ok else _state["error"],
    }


def trace_url(trace_id: str | None) -> str | None:
    if not (UI_URL and trace_id and _state["experiment_id"]):
        return None
    return f"{UI_URL}/#/experiments/{_state['experiment_id']}/traces?selectedEvaluationId={trace_id}"


# --------------------------------------------------------------------------- #
# Spans
# --------------------------------------------------------------------------- #
class _NoSpan:
    trace_id = None

    def set_inputs(self, *_a: Any, **_k: Any) -> None: ...
    def set_outputs(self, *_a: Any, **_k: Any) -> None: ...
    def set_attribute(self, *_a: Any, **_k: Any) -> None: ...
    def set_attributes(self, *_a: Any, **_k: Any) -> None: ...


@contextlib.contextmanager
def span(name: str, span_type: str = "UNKNOWN", **attributes: Any) -> Iterator[Any]:
    """An MLflow span (nests under the current trace), or a no-op."""
    if not enabled():
        yield _NoSpan()
        return
    try:
        cm = _mlflow().start_span(name=name, span_type=span_type)
        s = cm.__enter__()
    except Exception as e:  # noqa: BLE001
        log.debug("Could not start span %s: %s", name, e)
        yield _NoSpan()
        return
    try:
        if attributes:
            s.set_attributes({k: v for k, v in attributes.items() if v is not None})
        yield s
    except BaseException as e:
        cm.__exit__(type(e), e, e.__traceback__)
        raise
    else:
        try:
            cm.__exit__(None, None, None)
        except Exception as e:  # noqa: BLE001
            log.debug("Could not close span %s: %s", name, e)


def tag_trace(**tags: Any) -> None:
    if not enabled():
        return
    try:
        _mlflow().update_current_trace(tags={k: str(v) for k, v in tags.items() if v is not None})
    except Exception as e:  # noqa: BLE001
        log.debug("Could not tag trace: %s", e)


def traced(name: str, span_type: str = "UNKNOWN") -> Callable:
    """Decorator form of :func:`span` that records inputs/outputs."""

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with span(name, span_type) as s:
                s.set_inputs({k: _safe(v) for k, v in kwargs.items()})
                out = fn(*args, **kwargs)
                s.set_outputs(_safe(out))
                return out

        return wrapper

    return deco


def _safe(value: Any) -> Any:
    """JSON-friendly, size-limited representation for span payloads."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 8000 else value[:8000] + "…"
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in list(value)[:50]]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in list(value.items())[:50]}
    if hasattr(value, "__dict__"):
        return {k: _safe(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)[:2000]


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #
def log_human_decision(
    *,
    trace_id: str | None,
    decision: str,
    decided_by: str,
    proposed: str | None,
    final: str | None,
    comment: str | None,
    confidence: float | None,
) -> None:
    """Attach the reviewer's decision to the agent trace as feedback."""
    if not (trace_id and enabled()):
        return
    try:
        from mlflow.entities import AssessmentSource, AssessmentSourceType

        mlflow = _mlflow()
        source = AssessmentSource(source_type=AssessmentSourceType.HUMAN, source_id=decided_by)
        accepted = decision in ("APPROVED", "MODIFIED")
        edited = accepted and final is not None and (final or "").strip() != (proposed or "").strip()
        mlflow.log_feedback(
            trace_id=trace_id,
            name="human_accepted",
            value=accepted,
            source=source,
            rationale=comment or None,
            metadata={"decision": decision, "agent_confidence": confidence},
        )
        if accepted:
            mlflow.log_feedback(
                trace_id=trace_id,
                name="human_edited",
                value=bool(edited),
                source=source,
                metadata={"final_value": (final or "")[:2000]} if edited else None,
            )
    except Exception as e:  # noqa: BLE001
        log.warning("Could not log feedback for trace %s: %s", trace_id, e)
