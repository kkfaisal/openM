import { useEffect, useState } from "react";
import { BrainCircuit, Loader2, RefreshCw, X } from "lucide-react";
import { api } from "../api";
import type { FindingDetail, PromptOverride } from "../types";
import { findingLabel } from "../lib/format";
import { promptTargetForFinding, usePromptEditing } from "../lib/prompt";
import PromptEditorModal from "./PromptEditorModal";
import RecommendationCard from "./RecommendationCard";
import { EmptyState, Loading, SeverityBadge, StatusBadge } from "./ui";

export default function FindingModal({
  findingId,
  onClose,
  onChanged,
}: {
  findingId: string | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [data, setData] = useState<FindingDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const promptEditing = usePromptEditing();
  const [promptEditor, setPromptEditor] = useState(false);

  useEffect(() => {
    if (!findingId) {
      setData(null);
      return;
    }
    setLoading(true);
    api
      .finding(findingId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [findingId, reloadKey]);

  if (!findingId) return null;

  function handleChanged() {
    setReloadKey((k) => k + 1); // refresh this finding in the modal
    onChanged(); // refresh the parent dataset
  }

  function regenerate() {
    if (promptEditing && data) {
      setPromptEditor(true);
      return;
    }
    void doRegenerate();
  }

  async function doRegenerate(promptOverride?: PromptOverride) {
    setRegenerating(true);
    setError(null);
    try {
      await api.regenerateFinding(findingId!, promptOverride);
      handleChanged();
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
      setError(m ? m[1] : raw);
    } finally {
      setRegenerating(false);
    }
  }

  async function submitPrompt(system: string, user: string) {
    setPromptEditor(false);
    await doRegenerate({ system_prompt: system, user_prompt: user });
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="card-title" style={{ fontSize: 16 }}>
              Recommended action
            </div>
            <div className="card-sub">
              {loading ? "Loading…" : data ? findingLabel(data.type) : ""}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-sm"
              onClick={regenerate}
              disabled={regenerating}
              title="Regenerate this description with the latest dataset context"
            >
              {regenerating ? (
                <Loader2 size={15} className="spinner" style={{ width: 15, height: 15 }} />
              ) : (
                <RefreshCw size={15} />
              )}
              Regenerate
            </button>
            <button className="btn btn-sm" onClick={onClose}>
              <X size={15} /> Close
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

        {error && (
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
            {error}
          </div>
        )}

        {loading ? (
          <Loading />
        ) : !data ? (
          <EmptyState text="Finding not found." />
        ) : (
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                flexWrap: "wrap",
                marginBottom: 10,
              }}
            >
              <SeverityBadge severity={data.severity} />
              <StatusBadge status={data.status} />
              <span className="badge field">{findingLabel(data.type)}</span>
              {data.agent && (
                <span className="badge mode-INFORMATION_ONLY">
                  <BrainCircuit size={12} style={{ verticalAlign: -2 }} /> {data.agent}
                </span>
              )}
            </div>
            <div className="mono" style={{ color: "#433a63", fontSize: 13, marginBottom: 8 }}>
              {data.entity}
            </div>
            {data.summary && (
              <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>
                {data.summary}
              </div>
            )}

            {data.recommendations.length === 0 ? (
              <EmptyState text="No recommendation yet." />
            ) : (() => {
              const sorted = [...data.recommendations].sort((a, b) => b.version - a.version);
              const current = sorted.find((r) => r.status === "PENDING") ?? sorted[0];
              if (!current) return null;
              const history = sorted.filter((r) => r.id !== current.id);
              return (
                <RecommendationCard
                  key={current.id}
                  recommendation={current}
                  history={history}
                  entity={data.entity}
                  onChanged={handleChanged}
                  onDecided={onClose}
                />
              );
            })()}
          </div>
        )}
      </div>

      {promptEditor && data && (
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
