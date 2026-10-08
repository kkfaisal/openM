import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Cable,
  Clock,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";
import { api } from "../api";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import { kindLabel } from "./Sources";
import type { ExtractedFact } from "../types";

const CATEGORY_COLORS: Record<string, string> = {
  description: "field",
  classification: "sev-HIGH",
  owner: "mode-INFORMATION_ONLY",
  domain: "mode-REQUIRE_APPROVAL",
  glossary: "status-RESOLVED",
  lineage: "field",
  general: "sev-MEDIUM",
};

export default function SourceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data, loading, error, reload } = useAsync(
    () => api.source(id ?? ""),
    [id]
  );
  const [busy, setBusy] = useState<"extract" | "delete" | "sync" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showDocs, setShowDocs] = useState(false);
  const [scheduleEnabled, setScheduleEnabled] = useState(data?.schedule_enabled ?? false);
  const [interval, setIntervalMin] = useState(data?.interval_minutes ?? 60);
  const [savingSchedule, setSavingSchedule] = useState(false);

  if (loading) return <Loading />;
  if (error || !data) return <EmptyState text={error ?? "Source not found"} />;

  const sourceId = data.id;
  const isApi = data.connection === "api";

  function errText(e: unknown): string {
    const raw = e instanceof Error ? e.message : String(e);
    const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
    return m ? m[1] : raw;
  }

  async function extract() {
    setBusy("extract");
    setActionError(null);
    try {
      await api.extractSource(sourceId);
      reload();
    } catch (e) {
      setActionError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  async function syncNow() {
    setBusy("sync");
    setActionError(null);
    try {
      await api.syncSource(sourceId);
      reload();
    } catch (e) {
      setActionError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  async function saveSchedule() {
    setSavingSchedule(true);
    setActionError(null);
    try {
      await api.setSourceSchedule(sourceId, scheduleEnabled, interval);
      reload();
    } catch (e) {
      setActionError(errText(e));
    } finally {
      setSavingSchedule(false);
    }
  }

  async function remove() {
    if (!confirm("Delete this source and its extracted facts?")) return;
    setBusy("delete");
    try {
      await api.deleteSource(sourceId);
      navigate("/sources");
    } catch (e) {
      setActionError(errText(e));
      setBusy(null);
    }
  }

  return (
    <div>
      <Link to="/sources" className="btn btn-sm" style={{ marginBottom: 12 }}>
        <ArrowLeft size={15} /> Back to ingestions
      </Link>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Cable size={20} color="#7b5fc7" />
          <div style={{ flex: 1, minWidth: 160 }}>
            <div className="card-title" style={{ fontSize: 17 }}>{data.name}</div>
            <div className="card-sub">
              <span className="badge field">{kindLabel(data.kind)}</span>{" "}
              <span className="badge sev-MEDIUM">{data.status}</span> ·{" "}
              {data.document_count} documents · {data.fact_count} facts
            </div>
          </div>
          {isApi && (
            <button className="btn btn-sm" onClick={syncNow} disabled={busy !== null}>
              {busy === "sync" ? <Loader2 size={15} className="spinner" /> : <RefreshCw size={15} />}
              Sync now
            </button>
          )}
          <button className="btn btn-sm" onClick={extract} disabled={busy !== null}>
            {busy === "extract" ? <Loader2 size={15} className="spinner" /> : <RefreshCw size={15} />}
            Re-extract
          </button>
          <button className="btn btn-sm" onClick={remove} disabled={busy !== null}>
            {busy === "delete" ? <Loader2 size={15} /> : <Trash2 size={15} />}
            Delete
          </button>
        </div>

        {data.error && (
          <div style={{ marginTop: 12, background: "#fbe8e6", border: "1px solid #eec9c6", borderRadius: 8, padding: "8px 10px", color: "#c14a43", fontSize: 12.5 }}>
            {data.error}
          </div>
        )}
        {actionError && (
          <div style={{ marginTop: 12, background: "#fbe8e6", border: "1px solid #eec9c6", borderRadius: 8, padding: "8px 10px", color: "#c14a43", fontSize: 12.5 }}>
            {actionError}
          </div>
        )}
      </div>

      {isApi && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <Clock size={17} color="#7b5fc7" />
            <div>
              <div className="card-title">CDC &amp; scheduling</div>
              <div className="card-sub">
                Pull only new messages since the last sync (change data capture)
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "8px 0 12px", fontSize: 12.5 }}>
            <span>
              <span className="muted">Last sync:</span>{" "}
              {data.last_sync_at ? new Date(data.last_sync_at).toLocaleString() : "never"}
            </span>
            {scheduleEnabled && (
              <span>
                <span className="muted">Next sync:</span>{" "}
                {data.next_sync_at ? new Date(data.next_sync_at).toLocaleString() : "—"}
              </span>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 600 }}>
              <input
                type="checkbox"
                checked={scheduleEnabled}
                onChange={(e) => setScheduleEnabled(e.target.checked)}
              />
              Schedule automatic syncs
            </label>
            <label className="muted" style={{ fontSize: 12.5 }}>
              every{" "}
              <input
                className="input"
                type="number"
                min={1}
                style={{ width: 72, display: "inline-block", margin: "0 4px" }}
                value={interval}
                onChange={(e) => setIntervalMin(Math.max(1, Number(e.target.value) || 60))}
                disabled={!scheduleEnabled}
              />{" "}
              minutes
            </label>
            <button className="btn btn-success btn-sm" onClick={saveSchedule} disabled={savingSchedule}>
              {savingSchedule ? <Loader2 size={15} className="spinner" /> : <Save size={15} />}
              Save schedule
            </button>
            {scheduleEnabled && (
              <span className="badge status-RESOLVED">Scheduled</span>
            )}
          </div>
          <p className="muted" style={{ fontSize: 12, margin: "10px 0 0" }}>
            Uses a stored cursor/watermark, so each scheduled run downloads only
            messages that are new since the previous sync.
          </p>
        </div>
      )}

      {data.summary && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <Sparkles size={17} color="#7b5fc7" />
            <div>
              <div className="card-title">AI summary</div>
              <div className="card-sub">What this source reveals about your metadata</div>
            </div>
          </div>
          <p style={{ fontSize: 13.5, margin: "8px 0" }}>{data.summary.summary}</p>
          {data.summary.key_points.length > 0 && (
            <>
              <div className="flag" style={{ margin: "8px 0 6px" }}>KEY POINTS</div>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {data.summary.key_points.map((k, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>{k}</li>
                ))}
              </ul>
            </>
          )}
          <div className="muted" style={{ fontSize: 11, marginTop: 8 }}>
            Generated by {data.summary.provider === "openai" ? "OpenAI" : "heuristic"} at{" "}
            {new Date(data.summary.generated_at).toLocaleString()}
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <Sparkles size={17} color="#d9a13f" />
          <div>
            <div className="card-title">Extracted metadata facts</div>
            <div className="card-sub">
              The structured knowledge fed into table &amp; column descriptions and classifications
            </div>
          </div>
        </div>
        {data.facts.length === 0 ? (
          <div className="muted" style={{ fontSize: 13 }}>No facts extracted yet — click "Re-extract".</div>
        ) : (
          data.facts.map((f) => <FactRow key={f.id} fact={f} />)
        )}
      </div>

      <div className="card">
        <button
          className="btn btn-sm"
          onClick={() => setShowDocs((v) => !v)}
          style={{ marginBottom: 8 }}
        >
          <FileText size={15} /> {showDocs ? "Hide" : "Show"} raw documents ({data.documents.length})
        </button>
        {showDocs && (
          <div>
            {data.documents.length === 0 ? (
              <div className="muted">No documents.</div>
            ) : (
              data.documents.map((d) => (
                <div key={d.id} style={{ borderTop: "1px dashed #e4dcf1", padding: "8px 0", fontSize: 12.5 }}>
                  <div className="muted" style={{ fontSize: 11 }}>
                    {d.author ?? "—"} · {d.channel ?? "—"} · {d.ts ? new Date(d.ts).toLocaleString() : ""}
                  </div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{d.content}</div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function FactRow({ fact }: { fact: ExtractedFact }) {
  return (
    <div style={{ borderTop: "1px dashed #e4dcf1", padding: "10px 0" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 4 }}>
        <span className={`badge ${CATEGORY_COLORS[fact.category] ?? "field"}`}>{fact.category}</span>
        {fact.entity && <span className="mono-chip">{fact.entity}</span>}
        <span className="muted" style={{ fontSize: 11 }}>
          confidence {Math.round(fact.confidence * 100)}%
        </span>
      </div>
      <div style={{ fontSize: 13 }}>{fact.statement}</div>
      {fact.evidence_text && (
        <div className="muted" style={{ fontSize: 12, marginTop: 4, fontStyle: "italic" }}>
          “…{fact.evidence_text}…”
        </div>
      )}
    </div>
  );
}
