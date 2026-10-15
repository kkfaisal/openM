import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  BookOpen,
  Database,
  FileText,
  Layers,
  Lightbulb,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { EmptyState, Loading } from "../components/ui";
import { errorDetail, fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { RagAnswer, RagHit } from "../types";

type Mode = "ask" | "search" | "browse";
type Kind = "" | "document" | "fact";

const EXAMPLES = [
  "Which values can warehouse_code take?",
  "What does a negative quantity_on_hand mean?",
  "Which columns contain personal data?",
];

export default function Knowledge() {
  const toast = useToast();
  const status = useAsync(() => api.ragStatus(), []);
  const sources = useAsync(() => api.ragSources(), []);

  const [mode, setMode] = useState<Mode>("ask");
  const [dataset, setDataset] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [kind, setKind] = useState<Kind>("");
  const [entity, setEntity] = useState("");
  const [reindexing, setReindexing] = useState(false);

  const sourceName = useMemo(() => {
    for (const d of sources.data ?? []) for (const s of d.sources) if (s.id === sourceId) return s.name;
    return "";
  }, [sources.data, sourceId]);

  const filters: Record<string, string> = {
    ...(dataset && { dataset_key: dataset }),
    ...(sourceId && { source_id: sourceId }),
    ...(kind && { kind }),
    ...(entity && { entity }),
  };

  async function reindex() {
    setReindexing(true);
    try {
      const r = await api.ragReindex(dataset || undefined);
      toast("success", "Knowledge base re-indexed", `${r.chunks} chunks from ${r.sources} sources`);
      status.reload();
      sources.reload();
    } catch (e) {
      toast("error", "Re-index failed", errorDetail(e));
    } finally {
      setReindexing(false);
    }
  }

  if (status.loading && !status.data) return <Loading />;
  const st = status.data;

  return (
    <div className="kb">
      <div className="card kb-status">
        <div className={`kb-dot ${st?.ready ? "ok" : "bad"}`} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700 }}>
            {st?.ready ? "Knowledge base ready" : "Knowledge base unavailable"}
            <span className="muted" style={{ fontWeight: 500 }}>
              {" "}
              · {st?.total_chunks ?? 0} indexed chunks
            </span>
          </div>
          <div className="kb-status-meta">
            <span>{st?.backend}</span>
            <span className="mono">{st?.embedding_model}</span>
            <span>{st?.embedding_provider} embeddings</span>
            <span>relevance floor {st?.min_score}</span>
          </div>
          {st?.error && <div className="rec-error" style={{ marginTop: 8, marginBottom: 0 }}>{st.error}</div>}
        </div>
        <button className="btn btn-sm" onClick={reindex} disabled={reindexing}>
          {reindexing ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          Re-index{dataset ? " dataset" : " all"}
        </button>
      </div>

      <div className="kb-layout">
        <aside className="card kb-side">
          <div className="eyebrow">Sources</div>
          <button
            className={`kb-src${!dataset && !sourceId ? " on" : ""}`}
            onClick={() => {
              setDataset("");
              setSourceId("");
            }}
          >
            <Layers size={14} /> Everything
            <span className="kb-count">{st?.total_chunks ?? 0}</span>
          </button>
          {(sources.data ?? []).map((d) => (
            <div key={d.dataset_key} className="kb-ds">
              <button
                className={`kb-src kb-src-ds${dataset === d.dataset_key && !sourceId ? " on" : ""}`}
                onClick={() => {
                  setDataset(d.dataset_key);
                  setSourceId("");
                }}
              >
                <Database size={14} />
                <span className="kb-src-name">{d.dataset_key}</span>
                <span className="kb-count">{d.chunks}</span>
              </button>
              {d.sources.map((s) => (
                <button
                  key={s.id}
                  className={`kb-src kb-src-child${sourceId === s.id ? " on" : ""}`}
                  onClick={() => {
                    setDataset(d.dataset_key);
                    setSourceId(s.id);
                  }}
                  title={s.index_error ?? `${s.document_chunks} passages · ${s.fact_chunks} facts`}
                >
                  {s.index_error ? <AlertTriangle size={13} color="var(--red)" /> : <FileText size={13} />}
                  <span className="kb-src-name">{s.name}</span>
                  <span className="kb-count">{s.chunks}</span>
                </button>
              ))}
            </div>
          ))}
          {(sources.data ?? []).length === 0 && (
            <div className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
              Nothing ingested yet. <Link to="/sources">Add a metadata ingestion</Link>.
            </div>
          )}

          <div className="eyebrow" style={{ marginTop: 16 }}>Content</div>
          <div className="seg seg-sm">
            {(["", "document", "fact"] as Kind[]).map((k) => (
              <button key={k || "all"} className={kind === k ? "seg-on" : ""} onClick={() => setKind(k)}>
                {k === "" ? "All" : k === "document" ? "Passages" : "Facts"}
              </button>
            ))}
          </div>
        </aside>

        <section style={{ minWidth: 0 }}>
          <div className="kb-tabs">
            {(
              [
                ["ask", "Ask", MessageSquareText],
                ["search", "Search", Search],
                ["browse", "Browse", BookOpen],
              ] as const
            ).map(([m, label, Icon]) => (
              <button key={m} className={`kb-tab${mode === m ? " on" : ""}`} onClick={() => setMode(m)}>
                <Icon size={15} /> {label}
              </button>
            ))}
          </div>

          {(dataset || sourceId || entity || kind) && (
            <div className="kb-filters">
              Filtering:
              {dataset && <FilterChip label={dataset} onClear={() => { setDataset(""); setSourceId(""); }} />}
              {sourceId && <FilterChip label={sourceName || "source"} onClear={() => setSourceId("")} />}
              {kind && <FilterChip label={kind === "fact" ? "facts" : "passages"} onClear={() => setKind("")} />}
              {entity && <FilterChip label={`mentions ${entity}`} onClear={() => setEntity("")} />}
            </div>
          )}

          {!st?.ready ? (
            <EmptyState text="The knowledge base is not reachable. Check the Qdrant settings." />
          ) : mode === "ask" ? (
            <AskPanel filters={filters} onEntity={setEntity} />
          ) : mode === "search" ? (
            <SearchPanel filters={filters} onEntity={setEntity} />
          ) : (
            <BrowsePanel filters={filters} onEntity={setEntity} />
          )}
        </section>
      </div>
    </div>
  );
}

function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="kb-chip">
      {label}
      <button onClick={onClear} aria-label="Clear filter">
        <X size={12} />
      </button>
    </span>
  );
}

function highlight(text: string, query: string) {
  const terms = query
    .toLowerCase()
    .split(/[^a-z0-9_]+/)
    .filter((t) => t.length > 2);
  if (terms.length === 0) return text;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(re).map((part, i) =>
    terms.includes(part.toLowerCase()) ? <mark key={i}>{part}</mark> : part
  );
}

function HitCard({
  hit,
  index,
  query = "",
  showScore = true,
  onEntity,
}: {
  hit: RagHit;
  index?: number;
  query?: string;
  showScore?: boolean;
  onEntity: (e: string) => void;
}) {
  const pct = Math.round(hit.score * 100);
  return (
    <div className="kb-hit" id={index ? `cite-${index}` : undefined}>
      <div className="kb-hit-head">
        {index && <span className="kb-cite-num">{index}</span>}
        <span className={`badge ${hit.kind === "fact" ? "mode-AUTO_APPLY" : "field"}`}>
          {hit.kind === "fact" ? (
            <>
              <Lightbulb size={11} /> fact · {hit.category}
            </>
          ) : (
            hit.doc_kind ?? "passage"
          )}
        </span>
        <Link to={`/sources/${hit.source_id}`} className="kb-hit-src">
          {hit.source_name}
        </Link>
        {hit.author && <span className="muted">· {hit.author}</span>}
        {hit.ts && <span className="muted">· {fmtDate(hit.ts)}</span>}
        {showScore && (
          <span className="kb-score" title="Cosine similarity">
            <span className="kb-score-track">
              <span className="kb-score-fill" style={{ width: `${Math.max(4, pct)}%` }} />
            </span>
            {hit.score.toFixed(2)}
          </span>
        )}
      </div>
      <div className="kb-hit-text">{highlight(hit.text, query)}</div>
      {hit.entities.length > 0 && (
        <div className="kb-hit-ents">
          {hit.entities.map((e) => (
            <button key={e} className="mono-chip kb-ent" onClick={() => onEntity(e)} title="Filter by this entity">
              {e}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function AskPanel({
  filters,
  onEntity,
}: {
  filters: Record<string, string>;
  onEntity: (e: string) => void;
}) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(question = q) {
    if (!question.trim()) return;
    setQ(question);
    setBusy(true);
    setError(null);
    try {
      setAnswer(
        await api.ragAsk({
          question,
          dataset_key: filters.dataset_key,
          source_id: filters.source_id,
        })
      );
    } catch (e) {
      setError(errorDetail(e));
    } finally {
      setBusy(false);
    }
  }

  // Turn "[1]" / "[2][3]" into links to the cited passages.
  const rendered = answer?.answer.split(/(\[\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    return m ? (
      <a key={i} href={`#cite-${m[1]}`} className="kb-cite-link">
        {m[1]}
      </a>
    ) : (
      part
    );
  });

  return (
    <div>
      <form
        className="kb-query"
        onSubmit={(e) => {
          e.preventDefault();
          ask();
        }}
      >
        <Sparkles size={17} color="var(--primary)" />
        <input
          className="kb-input"
          placeholder="Ask anything about your ingested meetings, chats and documents…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button className="btn btn-primary btn-sm" disabled={busy || !q.trim()}>
          {busy ? <Loader2 size={14} className="spin" /> : "Ask"}
        </button>
      </form>
      {!answer && !busy && (
        <div className="kb-examples">
          {EXAMPLES.map((e) => (
            <button key={e} className="chip" onClick={() => ask(e)}>
              {e}
            </button>
          ))}
        </div>
      )}
      {error && <div className="rec-error">{error}</div>}
      {answer && (
        <>
          <div className="card kb-answer">
            <div className="eyebrow">
              Answer{" "}
              <span style={{ textTransform: "none", letterSpacing: 0, fontWeight: 500 }}>
                · grounded in {answer.citations.length} passage{answer.citations.length === 1 ? "" : "s"}
                {answer.mode !== "generative" ? " · extractive (no LLM)" : ""}
              </span>
            </div>
            <div className="kb-answer-text">{rendered}</div>
          </div>
          <div className="eyebrow" style={{ margin: "16px 2px 8px" }}>Sources</div>
          {answer.citations.map((h, i) => (
            <HitCard key={h.id} hit={h} index={i + 1} query={answer.question} onEntity={onEntity} />
          ))}
        </>
      )}
    </div>
  );
}

function SearchPanel({
  filters,
  onEntity,
}: {
  filters: Record<string, string>;
  onEntity: (e: string) => void;
}) {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [minScore, setMinScore] = useState(0.3);
  const [hits, setHits] = useState<RagHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(filters);

  useEffect(() => {
    if (!submitted) return;
    setBusy(true);
    setError(null);
    api
      .ragSearch({ q: submitted, k: "20", min_score: String(minScore), ...filters })
      .then((r) => setHits(r.hits))
      .catch((e) => setError(errorDetail(e)))
      .finally(() => setBusy(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submitted, minScore, key]);

  return (
    <div>
      <form
        className="kb-query"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(q.trim());
        }}
      >
        <Search size={17} color="var(--primary)" />
        <input
          className="kb-input"
          placeholder="Semantic search, e.g. “backorder policy”"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button className="btn btn-primary btn-sm" disabled={!q.trim()}>
          Search
        </button>
      </form>
      <div className="kb-slider">
        <span className="muted">Minimum similarity</span>
        <input
          type="range"
          min={0}
          max={0.9}
          step={0.05}
          value={minScore}
          onChange={(e) => setMinScore(Number(e.target.value))}
        />
        <span className="mono">{minScore.toFixed(2)}</span>
      </div>
      {busy && <Loading />}
      {error && <div className="rec-error">{error}</div>}
      {!busy && hits && hits.length === 0 && <EmptyState text="No passages above this similarity." />}
      {!busy &&
        hits?.map((h) => <HitCard key={h.id} hit={h} query={submitted} onEntity={onEntity} />)}
    </div>
  );
}

function BrowsePanel({
  filters,
  onEntity,
}: {
  filters: Record<string, string>;
  onEntity: (e: string) => void;
}) {
  const [items, setItems] = useState<RagHit[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = JSON.stringify(filters);

  function load(offset?: string) {
    setBusy(true);
    api
      .ragChunks({ limit: "40", ...filters, ...(offset ? { offset } : {}) })
      .then((r) => {
        setItems((xs) => (offset ? [...xs, ...r.items] : r.items));
        setNext(r.next_offset);
      })
      .catch((e) => setError(errorDetail(e)))
      .finally(() => setBusy(false));
  }

  useEffect(() => {
    setItems([]);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return (
    <div>
      {error && <div className="rec-error">{error}</div>}
      {items.map((h) => (
        <HitCard key={h.id} hit={h} showScore={false} onEntity={onEntity} />
      ))}
      {!busy && items.length === 0 && <EmptyState text="Nothing indexed for this filter." />}
      {busy && <Loading />}
      {next && !busy && (
        <div style={{ textAlign: "center", marginTop: 8 }}>
          <button className="btn btn-sm" onClick={() => load(next)}>
            Load more
          </button>
        </div>
      )}
    </div>
  );
}
