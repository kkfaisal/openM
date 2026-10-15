"""Knowledge base (RAG) exploration endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MetadataSource
from ..services import rag
from ..services.llm import get_llm

router = APIRouter(prefix="/api/rag", tags=["rag"])


class AskRequest(BaseModel):
    question: str
    dataset_key: str | None = None
    source_id: str | None = None
    k: int = 6


def _unavailable(e: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Knowledge base unavailable: {e}")


@router.get("/status")
def status():
    return rag.status()


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    """Every ingested source with its indexed chunk count, grouped by dataset."""
    out: dict[str, dict] = {}
    try:
        ready = rag.status()["ready"]
    except Exception:  # noqa: BLE001
        ready = False
    for s in db.query(MetadataSource).order_by(MetadataSource.dataset_key, MetadataSource.name):
        ds = out.setdefault(s.dataset_key, {"dataset_key": s.dataset_key, "chunks": 0, "sources": []})
        chunks = docs = facts = 0
        if ready:
            try:
                docs = rag.count(source_id=s.id, kind="document")
                facts = rag.count(source_id=s.id, kind="fact")
                chunks = docs + facts
            except Exception:  # noqa: BLE001
                pass
        ds["chunks"] += chunks
        ds["sources"].append(
            {
                "id": s.id,
                "name": s.name,
                "kind": s.kind,
                "status": s.status,
                "document_count": s.document_count,
                "fact_count": s.fact_count,
                "chunks": chunks,
                "document_chunks": docs,
                "fact_chunks": facts,
                "index_error": ((s.config or {}).get("rag") or {}).get("error"),
                "updated_at": s.updated_at,
            }
        )
    return list(out.values())


@router.get("/search")
def search(
    q: str,
    dataset_key: str | None = None,
    source_id: str | None = None,
    kind: str | None = None,
    entity: str | None = None,
    k: int = 10,
    min_score: float = 0.0,
):
    try:
        hits = rag.search(
            q,
            dataset_key=dataset_key,
            source_id=source_id,
            kind=kind,
            entity=entity,
            k=min(max(k, 1), 50),
            min_score=min_score,
        )
    except Exception as e:  # noqa: BLE001
        raise _unavailable(e) from e
    return {"query": q, "hits": [h.as_dict() for h in hits], "min_score_default": rag.MIN_SCORE}


@router.get("/chunks")
def chunks(
    dataset_key: str | None = None,
    source_id: str | None = None,
    kind: str | None = None,
    entity: str | None = None,
    limit: int = 50,
    offset: str | None = None,
):
    try:
        hits, nxt = rag.browse(
            dataset_key=dataset_key,
            source_id=source_id,
            kind=kind,
            entity=entity,
            limit=min(max(limit, 1), 200),
            offset=offset,
        )
    except Exception as e:  # noqa: BLE001
        raise _unavailable(e) from e
    return {"items": [h.as_dict() for h in hits], "next_offset": nxt}


@router.post("/ask")
def ask(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Ask a question.")
    try:
        hits = rag.search(
            body.question,
            dataset_key=body.dataset_key,
            source_id=body.source_id,
            k=min(max(body.k, 1), 12),
        )
    except Exception as e:  # noqa: BLE001
        raise _unavailable(e) from e
    citations = [h.as_dict() for h in hits]
    try:
        answer = get_llm().answer_question(question=body.question, passages=citations)
        mode = "generative"
    except Exception as e:  # noqa: BLE001 — fall back to extractive
        from ..services.llm import LLMProvider

        answer = LLMProvider.answer_question(None, question=body.question, passages=citations)  # type: ignore[arg-type]
        mode = f"extractive ({e})"
    return {"question": body.question, "answer": answer, "citations": citations, "mode": mode}


@router.post("/reindex")
def reindex(dataset_key: str | None = None, db: Session = Depends(get_db)):
    try:
        result = rag.reindex_all(db, dataset_key)
    except Exception as e:  # noqa: BLE001
        raise _unavailable(e) from e
    return {"sources": len(result), "chunks": sum(result.values())}
