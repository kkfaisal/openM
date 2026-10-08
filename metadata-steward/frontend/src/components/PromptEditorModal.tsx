import { useEffect, useState } from "react";
import { Loader2, Sparkles, X } from "lucide-react";
import { api } from "../api";
import type { PromptPreview } from "../types";

function errText(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
  return m ? m[1] : raw;
}

export default function PromptEditorModal({
  kind,
  fqn,
  column,
  title,
  busy,
  onCancel,
  onSubmit,
}: {
  kind: string;
  fqn: string;
  column?: string;
  title: string;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (system: string, user: string) => void;
}) {
  const [preview, setPreview] = useState<PromptPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [system, setSystem] = useState("");
  const [user, setUser] = useState("");

  useEffect(() => {
    setPreview(null);
    setError(null);
    api
      .promptPreview({ kind, fqn, column })
      .then((p) => {
        setPreview(p);
        setSystem(p.system_prompt);
        setUser(p.user_prompt);
      })
      .catch((e) => setError(errText(e)));
  }, [kind, fqn, column]);

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        e.stopPropagation();
        onCancel();
      }}
    >
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="card-title" style={{ fontSize: 16 }}>
              Edit prompt
            </div>
            <div className="card-sub">
              {title} ·{" "}
              {preview ? `${preview.provider} / ${preview.model}` : "Loading…"}
            </div>
          </div>
          <button className="btn btn-sm" onClick={onCancel} disabled={busy}>
            <X size={15} /> Cancel
          </button>
        </div>

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

        <div className="flag" style={{ marginBottom: 4 }}>
          SYSTEM PROMPT
        </div>
        <textarea
          className="textarea"
          style={{ minHeight: 110, fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12 }}
          value={system}
          onChange={(e) => setSystem(e.target.value)}
        />

        <div className="flag" style={{ margin: "12px 0 4px" }}>
          USER PROMPT
        </div>
        <textarea
          className="textarea"
          style={{ minHeight: 200, fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12 }}
          value={user}
          onChange={(e) => setUser(e.target.value)}
        />

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn btn-sm" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onSubmit(system, user)}
            disabled={busy || !preview}
          >
            {busy ? (
              <Loader2 size={15} className="spinner" style={{ width: 15, height: 15 }} />
            ) : (
              <Sparkles size={15} />
            )}
            Generate with this prompt
          </button>
        </div>
      </div>
    </div>
  );
}
