import { useState } from "react";
import { useParams } from "react-router-dom";
import { ArrowLeft, BrainCircuit, Loader2, RefreshCw, Search } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import PromptEditorModal from "../components/PromptEditorModal";
import RecommendationCard from "../components/RecommendationCard";
import { EmptyState, Loading, SeverityBadge, StatusBadge } from "../components/ui";
import { findingLabel, fmtDate } from "../lib/format";
import { promptTargetForFinding, usePromptEditing } from "../lib/prompt";
import { useAsync } from "../lib/useAsync";
import type { PromptOverride } from "../types";

export default function FindingDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [regenerating, setRegenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const promptEditing = usePromptEditing();
  const [promptEditor, setPromptEditor] = useState(false);
  const location = useLocation();
  const canGoBack = location.key !== "default";
  const { data, loading, error, reload } = useAsync(
    () => api.finding(id!),
    [id]
  );

  if (loading) return <Loading />;
  if (error || !data)
    return <EmptyState text={error ?? "Finding not found."} />;

  async function investigate() {
    await api.investigate(data!.id);
    reload();
  }

  function regenerate() {
    if (promptEditing) {
      setPromptEditor(true);
      return;
    }
    void doRegenerate();
  }

  async function doRegenerate(promptOverride?: PromptOverride) {
    setRegenerating(true);
    setGenError(null);
    try {
      await api.regenerateFinding(data!.id, promptOverride);
      reload();
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
      setGenError(m ? m[1] : raw);
    } finally {
      setRegenerating(false);
    }
  }

  async function submitPrompt(system: string, user: string) {
    setPromptEditor(false);
    await doRegenerate({ system_prompt: system, user_prompt: user });
  }

  function goBack() {
    if (canGoBack) navigate(-1);
    else navigate("/findings");
  }

  const sortedRecs = [...data.recommendations].sort((a, b) => b.version - a.version);
  const currentRec = sortedRecs.find((r) => r.status === "PENDING") ?? sortedRecs[0];
  const historyRecs = currentRec ? sortedRecs.filter((r) => r.id !== currentRec.id) : [];

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
        <button className="btn btn-sm" onClick={goBack}>
          <ArrowLeft size={15} /> Back
        </button>
        <Link to="/findings" className="btn btn-sm">
          All findings
        </Link>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
            marginBottom: 12,
          }}
        >
          <SeverityBadge severity={data.severity} />
          <StatusBadge status={data.status} />
          <span className="badge field">{findingLabel(data.type)}</span>
          {data.agent && (
            <span className="badge mode-INFORMATION_ONLY">
              <BrainCircuit size={12} /> {data.agent}
            </span>
          )}
        </div>
        <h2 style={{ margin: "0 0 6px", fontSize: 18, letterSpacing: -0.01 }}>
          {findingLabel(data.type)} — <span className="mono">{data.entity}</span>
        </h2>
        {data.summary && <div className="muted">{data.summary}</div>}
        <dl className="kv" style={{ marginTop: 16 }}>
          <dt>Entity</dt>
          <dd className="mono">{data.entity}</dd>
          <dt>Entity type</dt>
          <dd>{data.entity_type}</dd>
          <dt>Domain</dt>
          <dd>{data.domain ?? "—"}</dd>
          <dt>Detected</dt>
          <dd>{fmtDate(data.detected_at)}</dd>
          <dt>Resolved</dt>
          <dd>{fmtDate(data.resolved_at)}</dd>
        </dl>
      </div>

      {data.evidence.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <Search size={16} color="#7b5fc7" />
            <div className="card-title">Evidence</div>
          </div>
          <ul className="evidence-list">
            {data.evidence.map((ev) => (
              <li key={ev.id}>
                <span className="evidence-type">{ev.type.replace(/_/g, " ")}</span>
                <span>{ev.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          margin: "20px 0 12px",
        }}
      >
        <div className="section-title" style={{ margin: 0 }}>
          Recommendations
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {data.status === "OPEN" && (
            <button className="btn btn-primary btn-sm" onClick={investigate}>
              <BrainCircuit size={15} /> Investigate
            </button>
          )}
          <button
            className="btn btn-sm"
            onClick={regenerate}
            disabled={regenerating}
            title="Regenerate this description with the latest dataset context"
          >
            {regenerating ? <Loader2 size={15} className="spinner" style={{ width: 15, height: 15 }} /> : <RefreshCw size={15} />}
            Regenerate
          </button>
        </div>
      </div>

      {regenerating && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "#efe9f8",
            border: "1px solid #d3c8e8",
            borderRadius: 8,
            padding: "10px 12px",
            marginBottom: 12,
          }}
        >
          <Loader2 size={16} className="spinner" />
          <div style={{ fontSize: 13, fontWeight: 600, color: "#5b3e9d" }}>
            Regenerating with AI…
          </div>
        </div>
      )}

      {genError && (
        <div
          style={{
            background: "#fbe8e6",
            border: "1px solid #eec9c6",
            borderRadius: 8,
            padding: "8px 10px",
            color: "#c14a43",
            fontSize: 12.5,
            marginBottom: 12,
          }}
        >
          {genError}
        </div>
      )}

      {data.recommendations.length === 0 ? (
        <EmptyState text="No recommendations yet. Run an investigation." />
      ) : currentRec ? (
        <RecommendationCard
          key={currentRec.id}
          recommendation={currentRec}
          history={historyRecs}
          entity={data.entity}
          onChanged={reload}
        />
      ) : null}

      {promptEditor && (
        <PromptEditorModal
          kind={promptTargetForFinding(data).kind}
          fqn={promptTargetForFinding(data).fqn}
          column={promptTargetForFinding(data).column}
          title={data.entity}
          busy={regenerating}
          onCancel={() => setPromptEditor(false)}
          onSubmit={submitPrompt}
        />
      )}
    </div>
  );
}
