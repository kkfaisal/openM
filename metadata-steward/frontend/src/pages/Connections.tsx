import { useState } from "react";
import { Database, Loader2, Plus, Plug, Trash2 } from "lucide-react";
import { api } from "../api";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import type { MetadataTool } from "../types";

const TOOL_TYPES: { label: string; value: string }[] = [
  { label: "OpenMetadata", value: "openmetadata" },
  { label: "Amundsen", value: "amundsen" },
  { label: "DataHub", value: "datahub" },
  { label: "Atlan", value: "atlan" },
  { label: "Collibra", value: "collibra" },
  { label: "Alation", value: "alation" },
  { label: "Unity Catalog", value: "unity_catalog" },
  { label: "Microsoft Purview", value: "purview" },
  { label: "AWS Glue", value: "glue" },
  { label: "Informatica", value: "informatica" },
  { label: "Custom", value: "custom" },
];

export function toolTypeLabel(value: string): string {
  return TOOL_TYPES.find((t) => t.value === value)?.label ?? value;
}

export default function Connections() {
  const { data, loading, error, reload } = useAsync(() => api.tools(), []);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("openmetadata");
  const [host, setHost] = useState("");
  const [seedDemo, setSeedDemo] = useState(true);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;
  const tools = data ?? [];

  function errText(e: unknown): string {
    const raw = e instanceof Error ? e.message : String(e);
    const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
    return m ? m[1] : raw;
  }

  async function create() {
    setBusy(true);
    setFormError(null);
    try {
      await api.createTool({ name, type, host: host || null, seed_demo: seedDemo });
      setName("");
      setHost("");
      setShowForm(false);
      reload();
    } catch (e) {
      setFormError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: MetadataTool) {
    if (!confirm(`Delete connection "${t.name}" and its datasets?`)) return;
    try {
      await api.deleteTool(t.id);
      reload();
    } catch (e) {
      alert(errText(e));
    }
  }

  return (
    <div>
      <p className="muted" style={{ marginTop: 0, marginBottom: 16, fontSize: 14 }}>
        Connect the metadata-management tools your organization uses. Datasets
        are grouped under the tool they came from.
      </p>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          <Plus size={17} /> Add tool
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <Plug size={18} color="#7b5fc7" />
            <div>
              <div className="card-title">Add metadata tool</div>
              <div className="card-sub">Connect a metadata platform</div>
            </div>
          </div>
          <div className="grid cols-2" style={{ alignItems: "end" }}>
            <div>
              <label className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>Name</label>
              <input className="input" style={{ width: "100%", marginTop: 4 }} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Amundsen Dev" />
            </div>
            <div>
              <label className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>Tool</label>
              <select className="select" style={{ width: "100%", marginTop: 4 }} value={type} onChange={(e) => setType(e.target.value)}>
                {TOOL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="muted" style={{ fontSize: 12.5, fontWeight: 600 }}>Host URL (optional)</label>
              <input className="input" style={{ width: "100%", marginTop: 4 }} value={host} onChange={(e) => setHost(e.target.value)} placeholder="https://tool.example.com" />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, height: 40 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 600 }}>
                <input type="checkbox" checked={seedDemo} onChange={(e) => setSeedDemo(e.target.checked)} />
                Seed sample datasets
              </label>
              <button className="btn btn-success" onClick={create} disabled={busy || !name.trim()}>
                {busy ? <Loader2 size={16} className="spinner" /> : <Plus size={16} />}
                Connect
              </button>
            </div>
          </div>
          {formError && (
            <div style={{ marginTop: 12, background: "#fbe8e6", border: "1px solid #eec9c6", borderRadius: 8, padding: "8px 10px", color: "#c14a43", fontSize: 12.5 }}>
              {formError}
            </div>
          )}
          <p className="muted" style={{ fontSize: 12.5, margin: "12px 0 0" }}>
            Live API sync is wired for OpenMetadata; other tools can be
            registered and seeded with sample datasets (per-tool sync adapters
            plug in here later).
          </p>
        </div>
      )}

      {tools.length === 0 ? (
        <EmptyState text="No connections yet." />
      ) : (
        tools.map((t) => (
          <div key={t.id} className="card" style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <Plug size={20} color="#7b5fc7" />
              <div style={{ flex: 1, minWidth: 180 }}>
                <div className="card-title" style={{ fontSize: 16 }}>{t.name}</div>
                <div className="card-sub mono" style={{ fontSize: 12 }}>{t.host || "no host"}</div>
              </div>
              <span className="badge field">{toolTypeLabel(t.type)}</span>
              <span className={`badge ${t.status === "CONNECTED" ? "status-RESOLVED" : "sev-MEDIUM"}`}>{t.status}</span>
              {t.is_default && <span className="badge mode-INFORMATION_ONLY">Default</span>}
              <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14 }}>
                <Database size={16} color="#8a80a6" /> {t.dataset_count} datasets
              </span>
              <button className="btn btn-sm" onClick={() => remove(t)} disabled={t.is_default}>
                <Trash2 size={15} /> Remove
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
