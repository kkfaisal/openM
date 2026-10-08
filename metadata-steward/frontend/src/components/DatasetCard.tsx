import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  Boxes,
  Cable,
  ChevronDown,
  ChevronRight,
  Compass,
  Cpu,
  Database,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  Globe,
  Loader2,
  MessageSquare,
  Mic,
  Package,
  Plug,
  Plus,
  Save,
  Server,
  ShieldCheck,
  Sparkles,
  Table2,
  Webhook,
} from "lucide-react";
import { api } from "../api";
import { omEntityUrl } from "../lib/openmetadata";
import { usePromptEditing } from "../lib/prompt";
import { ConnectModal } from "./ConnectModal";
import FindingModal from "./FindingModal";
import OpenMetadataModal from "./OpenMetadataModal";
import PromptEditorModal from "./PromptEditorModal";
import type { CatalogTable, Dataset, PromptOverride } from "../types";

function kindLabel(kind: string): string {
  const map: Record<string, string> = {
    slack: "Slack",
    teams: "Teams",
    csv: "CSV",
    excel: "Excel",
    json: "JSON",
    webhook: "Webhook",
    audio: "Audio",
    video: "Video",
  };
  return map[kind] ?? kind;
}

function statusClass(status: string): string {
  if (status === "EXTRACTED") return "status-RESOLVED";
  if (status === "ERROR") return "sev-HIGH";
  if (status === "INGESTED") return "mode-INFORMATION_ONLY";
  return "sev-MEDIUM";
}

export default function DatasetCard({
  dataset,
  onSaved,
}: {
  dataset: Dataset;
  onSaved: () => void | Promise<unknown>;
}) {
  const navigate = useNavigate();
  const sources = dataset.sources ?? [];
  const totalTables = dataset.schemas.reduce((n, s) => n + s.tables.length, 0);

  const [modalFindingId, setModalFindingId] = useState<string | null>(null);
  const [genKey, setGenKey] = useState<string | null>(null); // entity being generated
  const [genError, setGenError] = useState<string | null>(null);

  const [expanded, setExpanded] = useState(false);
  const [columnsVersion, setColumnsVersion] = useState(0);
  const [connectMode, setConnectMode] = useState<"upload" | "slack" | "teams" | null>(null);
  const [omModal, setOmModal] = useState<{ url: string; title: string } | null>(null);

  const promptEditing = usePromptEditing();
  const [promptEditor, setPromptEditor] = useState<{
    kind: string;
    fqn: string;
    column?: string;
    title: string;
  } | null>(null);
  const [genBusy, setGenBusy] = useState(false);

  // dataset description
  const [draft, setDraft] = useState(dataset.context?.description ?? "");
  const [savingDesc, setSavingDesc] = useState(false);
  const [saved, setSaved] = useState(false);

  function generate(fqn: string, column?: string) {
    if (promptEditing) {
      setPromptEditor({
        kind: column ? "column_description" : "table_description",
        fqn,
        column,
        title: column ? `Column: ${column}` : `Table: ${fqn}`,
      });
      return;
    }
    void doGenerate(fqn, column);
  }

  async function doGenerate(fqn: string, column?: string, promptOverride?: PromptOverride) {
    const key = column ? `${fqn}.${column}` : fqn;
    setGenKey(key);
    setGenError(null);
    try {
      const detail = await api.generateDescription(fqn, column, promptOverride);
      setModalFindingId(detail.id); // always open for review & approval
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
      setGenError(m ? m[1] : raw);
    } finally {
      setGenKey(null);
    }
  }

  async function submitPrompt(system: string, user: string) {
    if (!promptEditor) return;
    setGenBusy(true);
    try {
      await doGenerate(promptEditor.fqn, promptEditor.column, {
        system_prompt: system,
        user_prompt: user,
      });
      setPromptEditor(null);
    } finally {
      setGenBusy(false);
    }
  }

  function handleFindingChanged() {
    onSaved(); // refresh table descriptions + metrics
    setColumnsVersion((v) => v + 1); // refresh any expanded columns
  }

  function openOm(entityType: string, fqn: string, title: string) {
    setOmModal({ url: omEntityUrl(entityType, fqn), title });
  }

  async function saveDescription() {
    setSavingDesc(true);
    try {
      await api.saveDatasetContext(dataset.key, {
        description: draft,
        table_instructions: dataset.context?.table_instructions ?? "",
        column_instructions: dataset.context?.column_instructions ?? "",
        dataset_instructions: dataset.context?.dataset_instructions ?? "",
        source: "user",
      });
      onSaved();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSavingDesc(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 22 }}>
      {/* ---------- Header (folded) ---------- */}
      <div
        style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", cursor: "pointer" }}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? <ChevronDown size={18} color="#8a80a6" /> : <ChevronRight size={18} color="#8a80a6" />}
        <Database size={22} color="#7b5fc7" />
        <div style={{ flex: 1, minWidth: 180 }}>
          <div className="card-title" style={{ fontSize: 18 }}>{dataset.database}</div>
          <div className="card-sub mono" style={{ fontSize: 12.5 }}>{dataset.key}</div>
        </div>
        <ToolBadge type={dataset.tool_type} name={dataset.tool_name} />
        <MetricChip label="ingestions" value={sources.length} />
        <MetricChip
          label="tables described"
          value={`${dataset.metrics.described_tables}/${totalTables}`}
        />
        <MetricChip
          label="columns described"
          value={`${dataset.metrics.described_columns}/${dataset.metrics.columns}`}
        />
        <span className="badge mode-INFORMATION_ONLY">Health {dataset.metrics.health.toFixed(1)}%</span>
      </div>

      {expanded && (
        <>
          {/* 1. Description */}
          <SectionHeader icon={<FileText size={18} color="#7b5fc7" />} title="Description" />
          <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: 14 }}>
            <textarea
              className="textarea"
              style={{ minHeight: 90, fontSize: 14 }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Describe this dataset's business purpose — used to ground AI-generated table/column descriptions."
            />
            <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8 }}>
              <button className="btn btn-success" onClick={saveDescription} disabled={savingDesc}>
                {savingDesc ? <Loader2 size={16} className="spinner" /> : <Save size={16} />}
                Save description
              </button>
              {saved && <span className="badge status-RESOLVED">Saved ✓</span>}
            </div>
          </div>

          {genError && (
            <div style={{ marginTop: 12, background: "#fbe8e6", border: "1px solid #eec9c6", borderRadius: 10, padding: "10px 12px", color: "#c14a43", fontSize: 13 }}>
              {genError}
            </div>
          )}

          {/* 2. Metadata Ingestions (centered, prominent) */}
          <CenteredSectionHeader icon={<Cable size={18} color="#7b5fc7" />} title="Metadata Ingestions" count={sources.length} />

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
            <QuickAdd label="CSV / Excel" icon={<FileSpreadsheet size={16} />} color="#2e9e68" onClick={() => setConnectMode("upload")} />
            <QuickAdd label="JSON" icon={<FileText size={16} />} color="#c58a2e" onClick={() => setConnectMode("upload")} />
            <QuickAdd label="Slack" icon={<MessageSquare size={16} />} color="#2f8d8d" onClick={() => setConnectMode("slack")} />
            <QuickAdd label="Teams" icon={<MessageSquare size={16} />} color="#d9a13f" onClick={() => setConnectMode("teams")} />
            <QuickAdd label="Meeting (Audio/Video)" icon={<Mic size={16} />} color="#7b5fc7" onClick={() => setConnectMode("upload")} />
            <QuickAdd label="Webhook" icon={<Webhook size={16} />} color="#8a80a6" onClick={() => navigate("/sources")} />
          </div>

      {sources.length === 0 ? (
        <div className="muted" style={{ fontSize: 13.5, padding: "4px 0 12px" }}>
          No ingestions yet — add Slack, Teams, CSV, Excel, JSON or a webhook.
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Ingestion</th>
              <th>Kind</th>
              <th>Status</th>
              <th>Last extraction</th>
              <th>Docs</th>
              <th>Facts</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr
                key={s.id}
                className="row-link"
                onClick={() => navigate(`/sources/${s.id}`)}
              >
                <td style={{ fontWeight: 600 }}>{s.name}</td>
                <td><span className="badge field">{kindLabel(s.kind)}</span></td>
                <td>
                  <span className={`badge ${statusClass(s.status)}`}>{s.status}</span>
                  {s.schedule_enabled && <span className="badge status-RESOLVED" style={{ marginLeft: 6 }}>Scheduled</span>}
                </td>
                <td className="muted">
                  {s.last_sync_at ?? s.updated_at
                    ? new Date((s.last_sync_at ?? s.updated_at) as string).toLocaleString()
                    : "—"}
                </td>
                <td>{s.document_count}</td>
                <td>{s.fact_count}</td>
                <td><ChevronRight size={16} color="#b1a8c9" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ---------- Table catalog ---------- */}
      <CenteredSectionHeader icon={<Table2 size={18} color="#7b5fc7" />} title="Table Catalog" count={totalTables} />
      {dataset.schemas.map((schema) => (
        <div key={schema.name} style={{ marginBottom: 8 }}>
          <div className="flag" style={{ fontSize: 12, marginBottom: 6, fontWeight: 700 }}>
            SCHEMA · {schema.name}
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Table</th>
                <th>Columns</th>
                <th>Owner</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {schema.tables.map((t) => (
                <TableRow
                  key={t.fqn}
                  table={t}
                  generating={genKey === t.fqn}
                  onGenerate={() => generate(t.fqn)}
                  columnsVersion={columnsVersion}
                  onOpenFinding={(id) => setModalFindingId(id)}
                  onOpenOm={openOm}
                />
              ))}
            </tbody>
          </table>
        </div>
      ))}
        </>
      )}

      <FindingModal
        findingId={modalFindingId}
        onClose={() => setModalFindingId(null)}
        onChanged={handleFindingChanged}
      />

      {promptEditor && (
        <PromptEditorModal
          kind={promptEditor.kind}
          fqn={promptEditor.fqn}
          column={promptEditor.column}
          title={promptEditor.title}
          busy={genBusy}
          onCancel={() => setPromptEditor(null)}
          onSubmit={submitPrompt}
        />
      )}

      {connectMode && (
        <ConnectModal
          datasets={[dataset]}
          initialDataset={dataset}
          initialMode={connectMode}
          onClose={() => setConnectMode(null)}
          onDone={onSaved}
        />
      )}

      <OpenMetadataModal
        url={omModal?.url ?? null}
        title={omModal?.title ?? ""}
        onClose={() => setOmModal(null)}
      />
    </div>
  );
}

function SectionHeader({ icon, title, count }: { icon: React.ReactNode; title: string; count?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "20px 0 10px" }}>
      {icon}
      <div style={{ fontWeight: 700, fontSize: 15 }}>{title}</div>
      {count !== undefined && <span className="hier-count" style={{ fontSize: 12 }}>{count}</span>}
      <div style={{ flex: 1, borderTop: "1px solid var(--border)" }} />
    </div>
  );
}

function CenteredSectionHeader({ icon, title, count }: { icon?: React.ReactNode; title: string; count?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, margin: "26px 0 14px" }}>
      <div style={{ flex: 1, borderTop: "2px solid var(--border-strong)" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 800, fontSize: 17 }}>
        {icon}
        {title}
        {count !== undefined && <span className="hier-count" style={{ fontSize: 12 }}>{count}</span>}
      </div>
      <div style={{ flex: 1, borderTop: "2px solid var(--border-strong)" }} />
    </div>
  );
}

function TableRow({
  table,
  generating,
  onGenerate,
  columnsVersion,
  onOpenFinding,
  onOpenOm,
}: {
  table: {
    fqn: string;
    name: string;
    description: string | null;
    owner: string | null;
    domain: string | null;
    column_count: number;
  };
  generating: boolean;
  onGenerate: () => void;
  columnsVersion: number;
  onOpenFinding: (id: string) => void;
  onOpenOm: (entityType: string, fqn: string, title: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [columns, setColumns] = useState<CatalogTable | null>(null);
  const [colGenKey, setColGenKey] = useState<string | null>(null);
  const [colClsKey, setColClsKey] = useState<string | null>(null);
  const [colError, setColError] = useState<string | null>(null);

  const promptEditing = usePromptEditing();
  const [promptEditor, setPromptEditor] = useState<{
    kind: string;
    fqn: string;
    column: string;
    title: string;
  } | null>(null);
  const [genBusy, setGenBusy] = useState(false);

  // When an approval is applied in the modal (columnsVersion bumps), refresh
  // this table's columns if it is currently expanded.
  useEffect(() => {
    if (!open) return;
    api.table(table.fqn).then(setColumns).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columnsVersion]);

  async function toggle() {
    if (!open && !columns) {
      try {
        setColumns(await api.table(table.fqn));
      } catch {
        /* ignore */
      }
    }
    setOpen((v) => !v);
  }

  function generateColumn(name: string) {
    if (promptEditing) {
      setPromptEditor({ kind: "column_description", fqn: table.fqn, column: name, title: `Column: ${name}` });
      return;
    }
    void doGenerateColumn(name);
  }

  async function doGenerateColumn(name: string, promptOverride?: PromptOverride) {
    setColGenKey(`${table.fqn}.${name}`);
    setColError(null);
    try {
      const detail = await api.generateDescription(table.fqn, name, promptOverride);
      onOpenFinding(detail.id); // always review & approve
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
      setColError(m ? m[1] : raw);
    } finally {
      setColGenKey(null);
    }
  }

  function generateClassification(name: string) {
    if (promptEditing) {
      setPromptEditor({ kind: "classification", fqn: table.fqn, column: name, title: `Classification: ${name}` });
      return;
    }
    void doGenerateClassification(name);
  }

  async function doGenerateClassification(name: string, promptOverride?: PromptOverride) {
    setColClsKey(`${table.fqn}.${name}`);
    setColError(null);
    try {
      const detail = await api.generateClassification(table.fqn, name, promptOverride);
      onOpenFinding(detail.id); // always review & approve
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const m = raw.match(/"detail"\s*:\s*"([^"]+)"/);
      setColError(m ? m[1] : raw);
    } finally {
      setColClsKey(null);
    }
  }

  async function submitPrompt(system: string, user: string) {
    if (!promptEditor) return;
    setGenBusy(true);
    try {
      const override: PromptOverride = { system_prompt: system, user_prompt: user };
      if (promptEditor.kind === "classification") {
        await doGenerateClassification(promptEditor.column, override);
      } else {
        await doGenerateColumn(promptEditor.column, override);
      }
      setPromptEditor(null);
    } finally {
      setGenBusy(false);
    }
  }

  return (
    <>
      <tr className="row-link" onClick={toggle}>
        <td style={{ fontWeight: 600 }}>
          {open ? <ChevronDown size={15} style={{ verticalAlign: -3, marginRight: 4 }} /> : <ChevronRight size={15} style={{ verticalAlign: -3, marginRight: 4 }} />}
          {table.name}
          <button
            className="btn btn-sm"
            style={{ padding: "2px 6px", marginLeft: 6 }}
            title="Open table in OpenMetadata"
            onClick={(e) => {
              e.stopPropagation();
              onOpenOm("table", table.fqn, table.name);
            }}
          >
            <ExternalLink size={13} />
          </button>
        </td>
        <td className="muted">{table.column_count}</td>
        <td>{table.owner ?? <span className="muted">—</span>}</td>
        <td style={{ maxWidth: 460 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "space-between", flexWrap: "wrap" }}>
            <span style={{ fontSize: 13.5 }}>
              {table.description ?? <span className="badge sev-MEDIUM">missing</span>}
            </span>
            <span onClick={(e) => e.stopPropagation()}>
              <GenerateButton loading={generating} has={!!table.description} onClick={onGenerate} />
            </span>
          </div>
        </td>
      </tr>

      {open && (
        <tr>
          <td colSpan={4} style={{ background: "#f6f2fb" }}>
            {colError && (
              <div style={{ background: "#fbe8e6", border: "1px solid #eec9c6", borderRadius: 8, padding: "8px 10px", color: "#c14a43", fontSize: 12.5, marginBottom: 8 }}>
                {colError}
              </div>
            )}
            {!columns ? (
              <div className="muted" style={{ padding: 10 }}>Loading columns…</div>
            ) : (
              <table className="table" style={{ background: "#fff", borderRadius: 8 }}>
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Classification</th>
                  </tr>
                </thead>
                <tbody>
                  {columns.columns.map((c) => (
                    <tr key={c.id}>
                      <td className="mono">
                        {c.name}
                        <button
                          className="btn btn-sm"
                          style={{ padding: "2px 6px", marginLeft: 6 }}
                          title="Open table in OpenMetadata"
                          onClick={() => onOpenOm("table", table.fqn, table.name)}
                        >
                          <ExternalLink size={13} />
                        </button>
                      </td>
                      <td className="muted">{c.data_type}</td>
                      <td style={{ maxWidth: 380 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between", flexWrap: "wrap" }}>
                          <span>{c.description ?? <span className="badge sev-LOW">missing</span>}</span>
                          <GenerateButton
                            loading={colGenKey === `${table.fqn}.${c.name}`}
                            has={!!c.description}
                            onClick={() => generateColumn(c.name)}
                          />
                        </div>
                      </td>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          {c.classification ? (
                            <span className="badge mode-INFORMATION_ONLY">{c.classification}</span>
                          ) : (
                            <span className="muted">—</span>
                          )}
                          <ClassifyButton
                            loading={colClsKey === `${table.fqn}.${c.name}`}
                            has={!!c.classification}
                            onClick={() => generateClassification(c.name)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </td>
        </tr>
      )}

      {promptEditor &&
        createPortal(
          <PromptEditorModal
            kind={promptEditor.kind}
            fqn={promptEditor.fqn}
            column={promptEditor.column}
            title={promptEditor.title}
            busy={genBusy}
            onCancel={() => setPromptEditor(null)}
            onSubmit={submitPrompt}
          />,
          document.body
        )}
    </>
  );
}

function GenerateButton({ loading, has, onClick }: { loading: boolean; has: boolean; onClick: () => void }) {
  return (
    <button
      className="btn btn-sm"
      onClick={onClick}
      disabled={loading}
      title={has ? "Regenerate description with AI" : "Generate description with AI"}
    >
      {loading ? (
        <Loader2 size={15} className="spinner" style={{ width: 15, height: 15 }} />
      ) : (
        <Sparkles size={15} />
      )}
      {has ? "Regenerate" : "Generate"}
    </button>
  );
}

function ClassifyButton({ loading, has, onClick }: { loading: boolean; has: boolean; onClick: () => void }) {
  return (
    <button
      className="btn btn-sm"
      onClick={onClick}
      disabled={loading}
      title={has ? "Reclassify with AI" : "Classify with AI"}
    >
      {loading ? (
        <Loader2 size={15} className="spinner" style={{ width: 15, height: 15 }} />
      ) : (
        <ShieldCheck size={15} />
      )}
      {has ? "Reclassify" : "Classify"}
    </button>
  );
}

function MetricChip({ label, value }: { label: string; value: number | string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 2,
        padding: "6px 14px",
        background: "var(--surface-2)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        minWidth: 96,
      }}
    >
      <div style={{ fontWeight: 800, fontSize: 16, lineHeight: 1 }}>{value}</div>
      <div className="muted" style={{ fontSize: 11, whiteSpace: "nowrap" }}>{label}</div>
    </div>
  );
}

const TOOL_META: Record<string, { label: string; icon: typeof Database }> = {
  openmetadata: { label: "OpenMetadata", icon: Database },
  amundsen: { label: "Amundsen", icon: BookOpen },
  datahub: { label: "DataHub", icon: Boxes },
  atlan: { label: "Atlan", icon: Globe },
  collibra: { label: "Collibra", icon: ShieldCheck },
  alation: { label: "Alation", icon: Compass },
  unity_catalog: { label: "Unity Catalog", icon: Package },
  purview: { label: "Purview", icon: ShieldCheck },
  glue: { label: "AWS Glue", icon: Cpu },
  informatica: { label: "Informatica", icon: Server },
  custom: { label: "Custom", icon: Plug },
};

function ToolBadge({ type, name }: { type: string | null; name: string | null }) {
  if (!name && !type) return null;
  const meta = TOOL_META[type ?? ""] ?? { label: type ?? "Unknown", icon: Plug };
  const Icon = meta.icon;
  return (
    <span
      className="badge"
      style={{ background: "var(--primary-soft)", color: "var(--primary-strong)", border: "1px solid var(--border)" }}
    >
      <Icon size={14} /> {name || meta.label}
    </span>
  );
}

function QuickAdd({
  label,
  icon,
  color,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      className="btn btn-sm"
      style={{ background: color, borderColor: color, color: "#fff", boxShadow: "0 4px 12px rgba(43, 36, 64, 0.22)" }}
      onClick={onClick}
    >
      {icon} {label}
    </button>
  );
}
