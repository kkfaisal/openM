import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Database,
  DatabaseZap,
  KeyRound,
  Loader2,
  Pencil,
  Plug,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { api } from "../api";
import ConnectToolWizard, { toolTypeLabel } from "../components/ConnectToolWizard";
import { useToast } from "../components/Toast";
import { EmptyState, Loading } from "../components/ui";
import { errorDetail, relTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { MetadataTool, ToolDataset } from "../types";

export { toolTypeLabel };

const STATUS_CLASS: Record<string, string> = {
  CONNECTED: "status-RESOLVED",
  SYNCED: "status-RESOLVED",
  ERROR: "status-REJECTED",
  UNVERIFIED: "sev-MEDIUM",
  PENDING: "sev-MEDIUM",
  DEMO: "mode-INFORMATION_ONLY",
};

function authLabel(t: MetadataTool): string {
  switch (t.auth.type) {
    case "jwt":
      return `Bot token ${t.auth.token_hint ?? ""}`.trim();
    case "basic":
      return `Login as ${t.auth.email}`;
    case "env":
      return "Credentials from server environment";
    default:
      return "No credentials";
  }
}

export default function Connections() {
  const toast = useToast();
  const { data, loading, error, reload } = useAsync(() => api.tools(), []);
  const [wizard, setWizard] = useState<null | { tool: MetadataTool | null; step: "connect" | "choose" }>(null);
  const [busy, setBusy] = useState<string | null>(null);

  if (loading && !data) return <Loading />;
  if (error) return <EmptyState text={error} />;
  const tools = data ?? [];

  async function run<T>(key: string, fn: () => Promise<T>, ok: (r: T) => [string, string?]) {
    setBusy(key);
    try {
      const r = await fn();
      const [title, detail] = ok(r);
      toast("success", title, detail);
      window.dispatchEvent(new Event("metalens:refresh-counts"));
      reload();
    } catch (e) {
      toast("error", "Something went wrong", errorDetail(e));
      reload();
    } finally {
      setBusy(null);
    }
  }

  function check(t: MetadataTool) {
    setBusy(`check-${t.id}`);
    api
      .checkTool(t.id)
      .then((r) => toast(r.ok ? "success" : "error", r.ok ? "Connection OK" : "Connection failed", r.message))
      .catch((e) => toast("error", "Connection failed", errorDetail(e)))
      .finally(() => {
        setBusy(null);
        reload();
      });
  }

  function removeTool(t: MetadataTool) {
    if (
      !confirm(
        `Remove "${t.name}"? MetaLens stops tracking its ${t.dataset_count} dataset(s). Nothing is deleted in ${toolTypeLabel(t.type)}.`
      )
    )
      return;
    run(`del-${t.id}`, () => api.deleteTool(t.id), () => [`Removed ${t.name}`]);
  }

  function removeDataset(t: MetadataTool, d: ToolDataset) {
    if (
      !confirm(
        `Stop tracking ${d.display_name || d.dataset_key}? Its open findings are closed. OpenMetadata and ingested sources are kept.`
      )
    )
      return;
    run(`dsdel-${d.id}`, () => api.removeToolDataset(t.id, d.id), () => [
      `Stopped tracking ${d.display_name || d.dataset_key}`,
    ]);
  }

  return (
    <div>
      <div className="page-intro">
        <p>
          Connect the metadata platforms your organization uses, then choose which databases
          MetaLens should steward. Credentials are tested before saving and stored encrypted.
        </p>
        <button className="btn btn-primary" onClick={() => setWizard({ tool: null, step: "connect" })}>
          <Plus size={17} /> Connect a tool
        </button>
      </div>

      {tools.length === 0 ? (
        <div className="card inbox-zero">
          <Plug size={30} color="var(--primary)" />
          <div className="inbox-zero-title" style={{ fontSize: 18, marginTop: 8 }}>
            No connections yet
          </div>
          <div className="muted">Connect OpenMetadata to start stewarding your catalog.</div>
        </div>
      ) : (
        tools.map((t) => {
          const live = t.type === "openmetadata";
          return (
            <div key={t.id} className="card tool-card">
              <div className="tool-head">
                <div className="attn-primary-icon" style={{ width: 42, height: 42 }}>
                  <Plug size={19} />
                </div>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div className="tool-title">
                    {t.name}
                    <span className="badge field">{toolTypeLabel(t.type)}</span>
                    <span className={`badge ${STATUS_CLASS[t.status] ?? "sev-MEDIUM"}`}>{t.status}</span>
                    {t.is_default && <span className="badge mode-INFORMATION_ONLY">Default</span>}
                  </div>
                  <div className="tool-meta">
                    <span className="mono">{t.host || "no host"}</span>
                    {live && (
                      <span>
                        <KeyRound size={12} /> {authLabel(t)}
                      </span>
                    )}
                    {t.last_checked_at && <span>Checked {relTime(t.last_checked_at)}</span>}
                  </div>
                </div>
                <div className="tool-actions">
                  {live && (
                    <>
                      <button
                        className="btn btn-sm"
                        disabled={busy !== null}
                        onClick={() => check(t)}
                      >
                        {busy === `check-${t.id}` ? <Loader2 size={14} className="spin" /> : <Plug size={14} />}
                        Test
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={() => setWizard({ tool: t, step: "connect" })}
                      >
                        <Pencil size={14} /> Edit
                      </button>
                      <button
                        className="btn btn-sm btn-primary"
                        disabled={t.status === "ERROR" || t.status === "UNVERIFIED"}
                        title={t.status !== "CONNECTED" ? "Fix the connection first" : undefined}
                        onClick={() => setWizard({ tool: t, step: "choose" })}
                      >
                        <DatabaseZap size={14} /> Import datasets
                      </button>
                    </>
                  )}
                  <button
                    className="btn btn-sm btn-ghost"
                    disabled={t.is_default || busy !== null}
                    title={t.is_default ? "The default connection comes from server settings" : "Remove"}
                    onClick={() => removeTool(t)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              {t.last_error && t.status !== "CONNECTED" && (
                <div className="tool-error">
                  <AlertTriangle size={15} />
                  <span>{t.last_error}</span>
                </div>
              )}

              {live && (
                <div className="tool-datasets">
                  {t.datasets.length === 0 ? (
                    <div className="muted" style={{ fontSize: 13, padding: "6px 2px" }}>
                      No datasets imported yet.{" "}
                      {t.status === "CONNECTED" && (
                        <button
                          className="link-btn"
                          onClick={() => setWizard({ tool: t, step: "choose" })}
                        >
                          Choose databases to import
                        </button>
                      )}
                    </div>
                  ) : (
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Dataset</th>
                          <th>Schemas</th>
                          <th>Tables</th>
                          <th>Status</th>
                          <th>Last sync</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {t.datasets.map((d) => (
                          <tr key={d.id}>
                            <td>
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <Database size={15} color="var(--muted)" />
                                <div>
                                  <div style={{ fontWeight: 600 }}>
                                    {d.display_name || d.database_name}
                                  </div>
                                  <div className="mono muted" style={{ fontSize: 11.5 }}>
                                    {d.dataset_key}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td>
                              {d.schemas.length === 0 ? (
                                <span className="muted">All</span>
                              ) : (
                                d.schemas.map((s) => (
                                  <span key={s} className="mono-chip" style={{ marginRight: 4 }}>
                                    {s}
                                  </span>
                                ))
                              )}
                            </td>
                            <td>{d.table_count}</td>
                            <td>
                              <span
                                className={`badge ${STATUS_CLASS[d.status] ?? "sev-MEDIUM"}`}
                                title={d.error ?? undefined}
                              >
                                {d.status}
                              </span>
                            </td>
                            <td className="muted">{d.last_synced_at ? relTime(d.last_synced_at) : "never"}</td>
                            <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                              <Link
                                to={`/findings?dataset=${encodeURIComponent(d.dataset_key)}`}
                                className="btn btn-sm btn-ghost"
                              >
                                Findings
                              </Link>
                              <button
                                className="btn btn-sm btn-ghost"
                                disabled={busy !== null}
                                onClick={() =>
                                  run(`sync-${d.id}`, () => api.syncToolDataset(t.id, d.id), (r) => [
                                    `Synced ${r.display_name || r.dataset_key}`,
                                    `${r.table_count} tables up to date`,
                                  ])
                                }
                              >
                                {busy === `sync-${d.id}` ? (
                                  <Loader2 size={14} className="spin" />
                                ) : (
                                  <RefreshCw size={14} />
                                )}
                                Sync
                              </button>
                              <button
                                className="btn btn-sm btn-ghost"
                                disabled={busy !== null}
                                onClick={() => removeDataset(t, d)}
                                title="Stop tracking this dataset"
                              >
                                <Trash2 size={14} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {t.datasets.some((d) => d.error) && (
                    <div className="tool-error" style={{ marginTop: 8 }}>
                      <AlertTriangle size={15} />
                      <span>{t.datasets.find((d) => d.error)?.error}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}

      {wizard && (
        <ConnectToolWizard
          tool={wizard.tool}
          startAt={wizard.step}
          onClose={() => setWizard(null)}
          onChanged={reload}
        />
      )}
    </div>
  );
}
