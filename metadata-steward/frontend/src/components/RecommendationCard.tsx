import { useState } from "react";
import { Check, History, RotateCcw, X } from "lucide-react";
import { api } from "../api";
import type { Recommendation } from "../types";
import { fieldLabel, fmtDate } from "../lib/format";
import {
  ActionModeBadge,
  ConfidenceBar,
  FieldBadge,
  StatusBadge,
} from "./ui";

export default function RecommendationCard({
  recommendation,
  history,
  entity,
  onChanged,
  onDecided,
}: {
  recommendation: Recommendation;
  history?: Recommendation[];
  entity: string;
  onChanged: () => void;
  onDecided?: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [modified, setModified] = useState(recommendation.new_value ?? "");
  const [error, setError] = useState<string | null>(null);

  function errText(e: unknown): string {
    const raw = e instanceof Error ? e.message : String(e);
    const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
    return m ? m[1] : raw;
  }

  async function act(kind: "approve" | "reject") {
    setBusy(kind);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        comment,
        decided_by: "Demo Steward",
        modified_value: modified,
      };
      if (kind === "approve") await api.recommendApprove(recommendation.id, body);
      else await api.recommendReject(recommendation.id, body);
      onChanged();
      onDecided?.();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  async function useVersion(id: string) {
    setBusy("select");
    setError(null);
    try {
      await api.recommendSelect(id);
      onChanged();
      onDecided?.();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(null);
    }
  }

  const historySorted = [...(history ?? [])].sort((a, b) => b.version - a.version);

  return (
    <div
      className="card"
      style={{
        borderLeft: "3px solid #7b5fc7",
        marginBottom: 14,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          flexWrap: "wrap",
          marginBottom: 12,
        }}
      >
        <FieldBadge field={fieldLabel(recommendation.field)} />
        <span className="badge mode-INFORMATION_ONLY">v{recommendation.version}</span>
        <StatusBadge status={recommendation.status} />
        <ActionModeBadge mode={recommendation.action_mode} />
        <span style={{ marginLeft: "auto" }}>
          <ConfidenceBar value={recommendation.confidence} />
        </span>
      </div>

      <div className="mono" style={{ color: "#433a63", fontSize: 13, marginBottom: 12 }}>
        {entity}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
          marginBottom: 12,
        }}
      >
        <div
          style={{
            background: "#f6f2fb",
            border: "1px solid #e4dcf1",
            borderRadius: 9,
            padding: 10,
          }}
        >
          <div className="flag" style={{ marginBottom: 4 }}>
            CURRENT
          </div>
          <div style={{ fontSize: 13 }}>
            {recommendation.old_value ?? <em className="muted">(empty)</em>}
          </div>
        </div>
        <div
          style={{
            background: "#efe9f8",
            border: "1px solid #d3c8e8",
            borderRadius: 9,
            padding: 10,
          }}
        >
          <div className="flag" style={{ marginBottom: 4 }}>
            SUGGESTED v{recommendation.version} — editable
          </div>
          {recommendation.status === "PENDING" ? (
            <textarea
              className="textarea"
              style={{ minHeight: 70, fontSize: 13, background: "#fff" }}
              value={modified}
              onChange={(e) => setModified(e.target.value)}
            />
          ) : (
            <div style={{ fontSize: 13 }}>{recommendation.new_value}</div>
          )}
        </div>
      </div>

      {recommendation.reasoning_summary && (
        <div style={{ fontSize: 12.5, color: "#433a63", marginBottom: 10 }}>
          <strong>Reasoning:</strong> {recommendation.reasoning_summary}
        </div>
      )}

      {recommendation.evidence.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div className="flag" style={{ marginBottom: 4 }}>
            EVIDENCE
          </div>
          <ul className="evidence-list">
            {recommendation.evidence.map((ev) => (
              <li key={ev.id}>
                <span className="evidence-type">{ev.type.replace(/_/g, " ")}</span>
                <span>{ev.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Version history — old vs new suggestions */}
      {historySorted.length > 0 && (
        <div style={{ marginBottom: 10 }}>
          <div className="flag" style={{ marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
            <History size={13} /> VERSION HISTORY
          </div>
          <ul className="evidence-list">
            {historySorted.map((h) => (
              <li key={h.id} style={{ alignItems: "flex-start" }}>
                <span className="evidence-type">
                  v{h.version} · {h.status.replace(/_/g, " ")}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5 }}>{h.new_value}</div>
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    {fmtDate(h.created_at)}
                    {h.context_snapshot ? (
                      <> · context: {(h.context_snapshot || "").slice(0, 90)}{h.context_snapshot.length > 90 ? "…" : ""}</>
                    ) : null}
                  </div>
                </div>
                {recommendation.status === "PENDING" && h.status === "SUPERSEDED" && (
                  <button
                    className="btn btn-sm"
                    disabled={busy !== null}
                    onClick={() => useVersion(h.id)}
                  >
                    Use this version
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recommendation.status === "PENDING" ? (
        <div
          style={{
            borderTop: "1px solid #e4dcf1",
            paddingTop: 12,
            marginTop: 4,
          }}
        >
          <input
            className="input"
            placeholder="Add a comment (optional)"
            style={{ width: "100%", marginBottom: 10 }}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          {error && (
            <div
              style={{
                background: "#fbe8e6",
                border: "1px solid #eec9c6",
                borderRadius: 8,
                padding: "8px 10px",
                color: "#c14a43",
                fontSize: 12.5,
                marginBottom: 10,
              }}
            >
              {error}
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="btn btn-success btn-sm"
              disabled={busy !== null}
              onClick={() => act("approve")}
            >
              <Check size={15} /> Approve & Apply
            </button>
            <button
              className="btn btn-sm"
              disabled={busy !== null}
              onClick={() => setModified(recommendation.new_value ?? "")}
            >
              <RotateCcw size={15} /> Reset
            </button>
            <button
              className="btn btn-danger btn-sm"
              disabled={busy !== null}
              onClick={() => act("reject")}
            >
              <X size={15} /> Reject
            </button>
            {busy && (
              <span className="muted" style={{ alignSelf: "center" }}>
                Working…
              </span>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
