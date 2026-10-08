import { useState } from "react";
import { KeyRound, Save, SlidersHorizontal } from "lucide-react";
import { api } from "../api";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";

export default function Settings() {
  const { data, loading, error, reload } = useAsync(() => api.settings(), []);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [savingFlag, setSavingFlag] = useState(false);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const settings = data ?? [];
  const configured = settings.find((s) => s.key === "openai_configured")?.value
    ?.value;
  const promptEditing = Boolean(
    settings.find((s) => s.key === "enable_prompt_editing")?.value?.value
  );

  async function togglePromptEditing(next: boolean) {
    setSavingFlag(true);
    try {
      await api.saveSetting("enable_prompt_editing", { value: next });
      reload();
    } finally {
      setSavingFlag(false);
    }
  }

  async function saveKey() {
    setSaving(true);
    try {
      await api.saveOpenAIKey(apiKey);
      setApiKey("");
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      reload();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <div className="card">
          <div className="card-header">
            <KeyRound size={17} color="#7b5fc7" />
            <div>
              <div className="card-title">OpenAI API Key</div>
              <div className="card-sub">
                Used to generate table, column and dataset descriptions
              </div>
            </div>
          </div>
          <div style={{ marginBottom: 10 }}>
            {configured ? (
              <span className="badge status-RESOLVED">LLM active — OpenAI</span>
            ) : (
              <span className="badge sev-MEDIUM">
                No key — using deterministic fallback
              </span>
            )}
          </div>
          <input
            className="input"
            type="password"
            style={{ width: "100%", marginBottom: 10 }}
            placeholder="sk-..."
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoComplete="off"
          />
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              className="btn btn-success btn-sm"
              onClick={saveKey}
              disabled={saving || !apiKey.trim()}
            >
              <Save size={15} /> Save key
            </button>
            {saved && <span className="badge status-RESOLVED">Saved ✓</span>}
          </div>
          <p className="muted" style={{ margin: "12px 0 0", fontSize: 12 }}>
            The key is stored locally in the steward's database (not in source
            code) and applied immediately. You can also set{" "}
            <span className="mono-chip">OPENAI_API_KEY</span> as an environment
            variable instead.
          </p>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Configuration</div>
              <div className="card-sub">Runtime settings</div>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {settings
                .filter((s) => s.key !== "openai_configured")
                .map((s) => {
                  const val = s.value?.value ?? JSON.stringify(s.value);
                  return (
                    <tr key={s.key}>
                      <td className="mono" style={{ fontSize: 12.5 }}>{s.key}</td>
                      <td>
                        {typeof val === "boolean" ? (
                          <span className={`badge ${val ? "status-RESOLVED" : "sev-MEDIUM"}`}>
                            {String(val)}
                          </span>
                        ) : (
                          <span className="mono-chip">{String(val)}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <SlidersHorizontal size={17} color="#7b5fc7" />
          <div>
            <div className="card-title">Prompt editing</div>
            <div className="card-sub">
              Review and edit the system &amp; user prompts before generating
            </div>
          </div>
          <label
            style={{
              marginLeft: "auto",
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={promptEditing}
              disabled={savingFlag}
              onChange={(e) => togglePromptEditing(e.target.checked)}
            />
            {promptEditing ? (
              <span className="badge status-RESOLVED">Enabled</span>
            ) : (
              <span className="badge sev-MEDIUM">Disabled</span>
            )}
          </label>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          When enabled, the <strong>Generate</strong> / <strong>Regenerate</strong>{" "}
          and classification actions show an editable prompt dialog first. When
          disabled, generation uses the built-in prompts directly.
        </p>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">OpenMetadata</div>
            <div className="card-sub">System of record for this steward</div>
          </div>
        </div>
        <p className="muted" style={{ margin: "0 0 12px", fontSize: 13 }}>
          The steward reads and writes your OpenMetadata instance directly.
          Findings are generated from the live catalog, and approved
          recommendations are applied back to OpenMetadata. On first start it
          ingests a small demo catalog (the only dummy part) so the workflow
          has data to operate on.
        </p>
        <pre
          style={{
            fontSize: 12,
            background: "#f6f2fb",
            border: "1px solid #e4dcf1",
            borderRadius: 8,
            padding: 12,
            overflow: "auto",
          }}
        >
{`# Connect to your OpenMetadata instance
CATALOG_BACKEND=openmetadata
OPENMETADATA_HOST=http://127.0.0.1:8585
OPENMETADATA_EMAIL=admin@open-metadata.org
OPENMETADATA_PASSWORD=admin`}
        </pre>
        <p className="muted" style={{ margin: "12px 0 0", fontSize: 12.5 }}>
          Reset the ingested demo data at any time with{" "}
          <span className="mono-chip">python reset_openmetadata.py</span> in the
          backend directory.
        </p>
      </div>
    </div>
  );
}
