"""Retrieval-augmented knowledge base over ingested metadata sources.

Every ingested document (Slack/Teams messages, spreadsheet rows, transcripts,
JSON exports) and every extracted fact is chunked, embedded and stored in
Qdrant with its provenance (dataset, source, author, timestamp, mentioned
catalog entities). Agents retrieve cited passages as evidence; the UI can
search, browse and ask questions over the index.

Storage:  QDRANT_URL (server, production) or QDRANT_PATH (embedded, dev).
Embeddings: fastembed (local ONNX, default BAAI/bge-small-en-v1.5) or OpenAI
(EMBEDDING_PROVIDER=openai). Changing the model needs a reindex; the
collection name includes the model so vectors never mix.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

    from ..models import ExtractedFact, MetadataSource, SourceDocument

from .. import config as _config  # noqa: F401  (loads backend/.env before reading env)

log = logging.getLogger(__name__)

_BASE = Path(__file__).resolve().parents[2]

ENABLED = os.getenv("RAG_ENABLED", "true").lower() in ("1", "true", "yes")
QDRANT_URL = os.getenv("QDRANT_URL") or None
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
QDRANT_PATH = os.getenv("QDRANT_PATH", str(_BASE / "data" / "qdrant"))
PROVIDER = os.getenv("EMBEDDING_PROVIDER", "fastembed").lower()
MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "text-embedding-3-small" if PROVIDER == "openai" else "BAAI/bge-small-en-v1.5",
)
CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", "800"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.55"))

_NS = uuid.UUID("6f1b8e8e-3d0e-4c55-9b8a-2a0f6b1d7c11")
_lock = threading.RLock()
_client = None
_embedder = None
_dim: int | None = None


class RagUnavailable(RuntimeError):
    pass


def collection_name() -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", MODEL.lower()).strip("_")
    return f"metalens_knowledge__{slug}"


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def _prepare_downloads() -> None:
    from .local_transcribe import _ca_bundle  # same corporate-CA handling

    os.environ.setdefault("SSL_CERT_FILE", _ca_bundle())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle())
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HOME", str(_BASE / ".hf_home"))


class _FastEmbed:
    def __init__(self) -> None:
        _prepare_downloads()
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=MODEL, cache_dir=str(_BASE / "models"))

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        if query and hasattr(self.model, "query_embed"):
            return [v.tolist() for v in self.model.query_embed(texts)]
        return [v.tolist() for v in self.model.embed(texts, batch_size=32)]


class _OpenAIEmbed:
    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:  # noqa: ARG002
        import httpx

        from ..config import openai_api_key, settings
        from .llm import _ca_bundle

        key = openai_api_key()
        if not key:
            raise RagUnavailable("EMBEDDING_PROVIDER=openai but no OpenAI key is configured.")
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            resp = httpx.post(
                f"{settings.openai_base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": MODEL, "input": texts[i : i + 96]},
                timeout=60,
                verify=_ca_bundle(),
            )
            resp.raise_for_status()
            out.extend(d["embedding"] for d in resp.json()["data"])
        return out


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = _OpenAIEmbed() if PROVIDER == "openai" else _FastEmbed()
    return _embedder


def embed(texts: list[str], *, query: bool = False) -> list[list[float]]:
    return _get_embedder().embed(texts, query=query)


# --------------------------------------------------------------------------- #
# Qdrant
# --------------------------------------------------------------------------- #
def _get_client():
    global _client, _dim
    if not ENABLED:
        raise RagUnavailable("RAG is disabled (RAG_ENABLED=false).")
    with _lock:
        if _client is not None:
            return _client
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm

        if QDRANT_URL:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=30)
        else:
            Path(QDRANT_PATH).mkdir(parents=True, exist_ok=True)
            client = QdrantClient(path=QDRANT_PATH)

        name = collection_name()
        if not client.collection_exists(name):
            _dim = len(embed(["dimension probe"])[0])
            client.create_collection(
                name,
                vectors_config=qm.VectorParams(size=_dim, distance=qm.Distance.COSINE),
            )
            for key in ("dataset_key", "source_id", "kind", "entities", "doc_id"):
                try:
                    client.create_payload_index(name, key, qm.PayloadSchemaType.KEYWORD)
                except Exception:  # noqa: BLE001 — embedded mode ignores indexes
                    pass
        _client = client
        return _client


def close() -> None:
    """Release the Qdrant client (embedded mode holds a file lock)."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:  # noqa: BLE001
                pass
            _client = None


def _filter(
    *,
    dataset_key: str | None = None,
    source_id: str | None = None,
    kind: str | None = None,
    entity: str | None = None,
    exclude_source_ids: list[str] | None = None,
):
    from qdrant_client.http import models as qm

    must_not = [
        qm.FieldCondition(key="source_id", match=qm.MatchValue(value=sid))
        for sid in (exclude_source_ids or [])
    ]
    must = []
    for key, value in (
        ("dataset_key", dataset_key),
        ("source_id", source_id),
        ("kind", kind),
        ("entities", entity),
    ):
        if value:
            must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))
    return qm.Filter(must=must or None, must_not=must_not or None) if (must or must_not) else None


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #
def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split on paragraph/sentence boundaries into ~size-char windows."""
    text = re.sub(r"[ \t]+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= size:
        return [text]
    pieces = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    chunks: list[str] = []
    cur = ""
    for p in pieces:
        if not p:
            continue
        while len(p) > size:  # a single very long sentence
            head, p = p[:size], p[size - overlap :]
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(head)
        if len(cur) + len(p) + 1 > size and cur:
            chunks.append(cur)
            cur = cur[-overlap:] + " " + p if overlap else p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def _mentions(text: str, hints: list[str]) -> list[str]:
    low = text.lower()
    found = []
    for h in hints:
        if len(h) >= 3 and re.search(rf"(?<![a-z0-9_]){re.escape(h.lower())}(?![a-z0-9_])", low):
            found.append(h)
    return sorted(set(found))[:20]


# --------------------------------------------------------------------------- #
# Indexing
# --------------------------------------------------------------------------- #
@dataclass
class _Point:
    id: str
    text: str
    payload: dict = field(default_factory=dict)


def _doc_points(source: "MetadataSource", docs: Iterable["SourceDocument"], hints: list[str]) -> list[_Point]:
    pts: list[_Point] = []
    for d in docs:
        for i, chunk in enumerate(chunk_text(d.content)):
            pts.append(
                _Point(
                    id=str(uuid.uuid5(_NS, f"doc:{d.id}:{i}")),
                    text=chunk,
                    payload={
                        "kind": "document",
                        "dataset_key": source.dataset_key,
                        "source_id": source.id,
                        "source_name": source.name,
                        "source_kind": source.kind,
                        "doc_id": d.id,
                        "doc_kind": d.kind,
                        "author": d.author,
                        "channel": d.channel,
                        "ts": d.ts.isoformat() if d.ts else None,
                        "chunk_index": i,
                        "entities": _mentions(chunk, hints),
                        "text": chunk,
                    },
                )
            )
    return pts


def _fact_points(source: "MetadataSource", facts: Iterable["ExtractedFact"]) -> list[_Point]:
    pts = []
    for f in facts:
        text = f.statement if not f.entity else f"{f.entity}: {f.statement}"
        pts.append(
            _Point(
                id=str(uuid.uuid5(_NS, f"fact:{f.id}")),
                text=text,
                payload={
                    "kind": "fact",
                    "dataset_key": f.dataset_key,
                    "source_id": source.id,
                    "source_name": source.name,
                    "source_kind": source.kind,
                    "fact_id": f.id,
                    "category": f.category,
                    "confidence": f.confidence,
                    "entities": [f.entity] if f.entity else [],
                    "text": text,
                    "evidence_text": f.evidence_text,
                },
            )
        )
    return pts


def _upsert(points: list[_Point]) -> int:
    if not points:
        return 0
    from qdrant_client.http import models as qm

    client = _get_client()
    for i in range(0, len(points), 128):
        batch = points[i : i + 128]
        vectors = embed([p.text for p in batch])
        client.upsert(
            collection_name(),
            points=[
                qm.PointStruct(id=p.id, vector=v, payload=p.payload)
                for p, v in zip(batch, vectors)
            ],
        )
    return len(points)


def delete_source(source_id: str) -> None:
    from qdrant_client.http import models as qm

    with _lock:
        client = _get_client()
        client.delete(
            collection_name(),
            points_selector=qm.FilterSelector(filter=_filter(source_id=source_id)),
        )


def index_source(db: "Session", source: "MetadataSource") -> int:
    """(Re)build the index for one source: its documents and facts."""
    from ..models import ExtractedFact, SourceDocument
    from .sources import entity_hints

    hints = entity_hints(db, source.dataset_key)
    docs = db.query(SourceDocument).filter(SourceDocument.source_id == source.id).all()
    facts = db.query(ExtractedFact).filter(ExtractedFact.source_id == source.id).all()
    with _lock:
        delete_source(source.id)
        n = _upsert(_doc_points(source, docs, hints) + _fact_points(source, facts))
    meta = dict(source.config or {})
    meta["rag"] = {"chunks": n, "model": MODEL, "collection": collection_name()}
    source.config = meta
    return n


def reindex_all(db: "Session", dataset_key: str | None = None) -> dict[str, int]:
    from ..models import MetadataSource

    q = db.query(MetadataSource)
    if dataset_key:
        q = q.filter(MetadataSource.dataset_key == dataset_key)
    out = {}
    for s in q.all():
        out[s.id] = index_source(db, s)
    db.commit()
    return out


# --------------------------------------------------------------------------- #
# Retrieval / exploration
# --------------------------------------------------------------------------- #
@dataclass
class Hit:
    id: str
    score: float
    text: str
    payload: dict

    def as_dict(self) -> dict:
        return {"id": self.id, "score": round(self.score, 4), "text": self.text, **{
            k: v for k, v in self.payload.items() if k != "text"
        }}


def search(
    query: str,
    *,
    dataset_key: str | None = None,
    source_id: str | None = None,
    kind: str | None = None,
    entity: str | None = None,
    k: int = 8,
    min_score: float | None = None,
    exclude_source_ids: list[str] | None = None,
) -> list[Hit]:
    from . import observability as obs

    query = (query or "").strip()
    if not query:
        return []
    floor = MIN_SCORE if min_score is None else min_score
    with obs.span("rag.search", "RETRIEVER", dataset_key=dataset_key, kind=kind, k=k, min_score=floor) as span:
        span.set_inputs({"query": query})
        client = _get_client()
        vec = embed([query], query=True)[0]
        res = client.query_points(
            collection_name(),
            query=vec,
            query_filter=_filter(
                dataset_key=dataset_key,
                source_id=source_id,
                kind=kind,
                entity=entity,
                exclude_source_ids=exclude_source_ids,
            ),
            limit=k,
            with_payload=True,
        ).points
        hits = [
            Hit(id=str(p.id), score=float(p.score), text=(p.payload or {}).get("text", ""), payload=p.payload or {})
            for p in res
            if p.score >= floor
        ]
        span.set_outputs(
            [
                {
                    "id": h.id,
                    "page_content": h.text,
                    "metadata": {
                        "score": round(h.score, 4),
                        "source": h.payload.get("source_name"),
                        "kind": h.payload.get("kind"),
                    },
                }
                for h in hits
            ]
        )
    return hits


def browse(
    *,
    dataset_key: str | None = None,
    source_id: str | None = None,
    kind: str | None = None,
    entity: str | None = None,
    limit: int = 50,
    offset: str | None = None,
) -> tuple[list[Hit], str | None]:
    client = _get_client()
    pts, nxt = client.scroll(
        collection_name(),
        scroll_filter=_filter(dataset_key=dataset_key, source_id=source_id, kind=kind, entity=entity),
        limit=limit,
        offset=offset,
        with_payload=True,
        with_vectors=False,
    )
    hits = [Hit(id=str(p.id), score=1.0, text=(p.payload or {}).get("text", ""), payload=p.payload or {}) for p in pts]
    return hits, (str(nxt) if nxt is not None else None)


def count(**filters) -> int:  # noqa: ANN003
    client = _get_client()
    return int(client.count(collection_name(), count_filter=_filter(**filters), exact=True).count)


def status() -> dict:
    info = {
        "enabled": ENABLED,
        "backend": "qdrant-server" if QDRANT_URL else "qdrant-embedded",
        "location": QDRANT_URL or QDRANT_PATH,
        "embedding_provider": PROVIDER,
        "embedding_model": MODEL,
        "collection": collection_name(),
        "min_score": MIN_SCORE,
        "chunk_chars": CHUNK_CHARS,
        "ready": False,
        "error": None,
        "total_chunks": 0,
    }
    if not ENABLED:
        return info
    try:
        info["total_chunks"] = count()
        info["ready"] = True
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)
    return info


def retrieve_for_entity(
    *,
    dataset_key: str,
    table_name: str,
    column_name: str | None = None,
    k: int = 4,
) -> list[Hit]:
    """Passages that talk about a table/column, for agent evidence.

    Never raises: retrieval is best-effort context for agents.
    """
    if not ENABLED:
        return []
    subject = f"{table_name}.{column_name}" if column_name else table_name
    words = re.sub(r"[_\W]+", " ", subject).strip()
    query = (
        f"What does the {column_name} column in the {table_name} table mean? {words}"
        if column_name
        else f"What is the {table_name} table used for? {words}"
    )
    try:
        hits = search(query, dataset_key=dataset_key, kind="document", k=k * 2)
    except Exception as e:  # noqa: BLE001
        log.warning("RAG retrieval failed: %s", e)
        return []
    # Prefer passages that actually mention the entity.
    needle = (column_name or table_name).lower()
    hits.sort(key=lambda h: (needle in h.text.lower(), h.score), reverse=True)
    return hits[:k]
