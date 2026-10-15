import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  KeyRound,
  Loader2,
  Plug,
  Server,
  X,
} from "lucide-react";
import { api } from "../api";
import { errorDetail } from "../lib/format";
import type {
  BrowseSchema,
  BrowseService,
  DatasetImportResult,
  MetadataTool,
  ToolTestResult,
} from "../types";

export const TOOL_TYPES: { label: string; value: string; live: boolean }[] = [
  { label: "OpenMetadata", value: "openmetadata", live: true },
  { label: "Amundsen", value: "amundsen", live: false },
  { label: "DataHub", value: "datahub", live: false },
  { label: "Atlan", value: "atlan", live: false },
  { label: "Collibra", value: "collibra", live: false },
  { label: "Alation", value: "alation", live: false },
  { label: "Unity Catalog", value: "unity_catalog", live: false },
  { label: "Microsoft Purview", value: "purview", live: false },
  { label: "AWS Glue", value: "glue", live: false },
  { label: "Informatica", value: "informatica", live: false },
  { label: "Custom", value: "custom", live: false },
];

export function toolTypeLabel(value: string): string {
  return TOOL_TYPES.find((t) => t.value === value)?.label ?? value;
}

type Step = "connect" | "choose" | "done";

interface Selection {
  service: string;
  database: string;
  display_name: string;
  /** null = all schemas */
  schemas: string[] | null;
}

export default function ConnectToolWizard({
  tool,
  startAt = "connect",
  onClose,
  onChanged,
}: {
  /** Existing tool: edit credentials, or jump straight to "choose". */
  tool?: MetadataTool | null;
  startAt?: Step;
  onClose: () => void;
  onChanged: () => void;
}) {
  const editing = !!tool;
  const [step, setStep] = useState<Step>(startAt);
  const [saved, setSaved] = useState<MetadataTool | null>(tool ?? null);
  const [importResult, setImportResult] = useState<DatasetImportResult | null>(null);

  // ---- connect form ----
  const [name, setName] = useState(tool?.name ?? "");
  const [type, setType] = useState(tool?.type ?? "openmetadata");
  const [host, setHost] = useState(tool?.host ?? "http://localhost:8585");
  const [authType, setAuthType] = useState<"jwt" | "basic">(
    tool?.auth.type === "basic" ? "basic" : "jwt"
  );
  const [token, setToken] = useState("");
  const [email, setEmail] = useState(tool?.auth.email ?? "");
  const [password, setPassword] = useState("");
  const [verifySsl, setVerifySsl] = useState(tool?.verify_ssl ?? true);
  const [seedDemo, setSeedDemo] = useState(false);
  const [test, setTest] = useState<ToolTestResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const live = TOOL_TYPES.find((t) => t.value === type)?.live ?? false;
  const hasStoredSecret = !!tool?.auth.has_secret && tool.auth.type === authType;

  const authBody = () =>
    authType === "jwt"
      ? { type: "jwt", token: token.trim() || undefined }
      : { type: "basic", email: email.trim(), password: password || undefined };

  // Any edit invalidates a previous test result.
  useEffect(() => setTest(null), [host, authType, token, email, password, verifySsl, type]);

  async function runTest() {
    setBusy("test");
    setError(null);
    try {
      setTest(
        await api.testTool({
          type,
          host,
          auth: authBody(),
          verify_ssl: verifySsl,
          tool_id: tool?.id,
        })
      );
    } catch (e) {
      setTest({ ok: false, version: null, services: null, message: errorDetail(e) });
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy("save");
    setError(null);
    try {
      let t: MetadataTool;
      if (editing && tool) {
        t = await api.updateTool(tool.id, {
          name,
          ...(live ? { host, auth: authBody(), verify_ssl: verifySsl } : {}),
        });
      } else {
        t = await api.createTool({
          name,
          type,
          host,
          ...(live ? { auth: authBody(), verify_ssl: verifySsl } : { seed_demo: seedDemo }),
        });
      }
      setSaved(t);
      onChanged();
      if (live) setStep("choose");
      else onClose();
    } catch (e) {
      setError(errorDetail(e));
    } finally {
      setBusy(null);
    }
  }

  const canTest =
    live &&
    host.trim() &&
    (authType === "jwt" ? token.trim() || hasStoredSecret : email.trim() && (password || hasStoredSecret));
  const canSave = name.trim() && (!live || test?.ok);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wizard" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <div className="card-title" style={{ fontSize: 17 }}>
              {editing && step === "connect" ? `Edit ${tool!.name}` : "Connect a metadata tool"}
            </div>
            <div className="card-sub">
              {step === "connect" && "Credentials are tested before saving and stored encrypted."}
              {step === "choose" && `Pick the databases from ${saved?.name} that MetaLens should steward.`}
              {step === "done" && "Import finished."}
            </div>
          </div>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        {live && (
          <ol className="wizard-steps">
            {(["connect", "choose", "done"] as Step[]).map((s, i) => {
              const order = ["connect", "choose", "done"].indexOf(step);
              const state = i < order ? "done" : i === order ? "current" : "todo";
              return (
                <li key={s} className={`wizard-step ws-${state}`}>
                  <span className="ws-dot">{state === "done" ? <Check size={12} /> : i + 1}</span>
                  {s === "connect" ? "Connect" : s === "choose" ? "Choose datasets" : "Import"}
                </li>
              );
            })}
          </ol>
        )}

        {step === "connect" && (
          <div className="wizard-body">
            <div className="form-grid">
              <label className="field">
                <span>Connection name</span>
                <input
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. OpenMetadata Prod"
                  autoFocus
                />
              </label>
              <label className="field">
                <span>Tool</span>
                <select
                  className="select"
                  value={type}
                  disabled={editing}
                  onChange={(e) => setType(e.target.value)}
                >
                  {TOOL_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                      {t.live ? "" : " (no live connector yet)"}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field field-wide">
                <span>Server URL</span>
                <input
                  className="input mono"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  placeholder="https://openmetadata.company.com"
                />
              </label>
            </div>

            {live ? (
              <>
                <div className="field-label">Authentication</div>
                <div className="seg">
                  <button
                    className={authType === "jwt" ? "seg-on" : ""}
                    onClick={() => setAuthType("jwt")}
                  >
                    <KeyRound size={14} /> Bot token (recommended)
                  </button>
                  <button
                    className={authType === "basic" ? "seg-on" : ""}
                    onClick={() => setAuthType("basic")}
                  >
                    <Server size={14} /> Email &amp; password
                  </button>
                </div>

                {authType === "jwt" ? (
                  <label className="field">
                    <span>
                      JWT token{" "}
                      <span className="muted" style={{ fontWeight: 400 }}>
                        Settings → Bots → ingestion-bot → token in OpenMetadata
                      </span>
                    </span>
                    <textarea
                      className="textarea mono"
                      style={{ minHeight: 64, fontSize: 12 }}
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder={
                        hasStoredSecret
                          ? `Stored (${tool?.auth.token_hint}). Leave blank to keep it.`
                          : "eyJraWQiOi…"
                      }
                    />
                  </label>
                ) : (
                  <div className="form-grid">
                    <label className="field">
                      <span>Email</span>
                      <input
                        className="input"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="admin@open-metadata.org"
                      />
                    </label>
                    <label className="field">
                      <span>Password</span>
                      <input
                        className="input"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder={hasStoredSecret ? "Leave blank to keep the stored one" : ""}
                      />
                    </label>
                  </div>
                )}

                <label className="check">
                  <input
                    type="checkbox"
                    checked={verifySsl}
                    onChange={(e) => setVerifySsl(e.target.checked)}
                  />
                  Verify TLS certificate
                </label>

                {test && (
                  <div className={`test-result ${test.ok ? "test-ok" : "test-bad"}`}>
                    {test.ok ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
                    <span>{test.message}</span>
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="test-result test-info">
                  <Plug size={17} />
                  <span>
                    {toolTypeLabel(type)} has no live connector yet. You can register it now and
                    sync it once the connector ships.
                  </span>
                </div>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={seedDemo}
                    onChange={(e) => setSeedDemo(e.target.checked)}
                  />
                  Load sample datasets (demo only, not real data)
                </label>
              </>
            )}

            {error && <div className="rec-error">{error}</div>}

            <div className="wizard-foot">
              {live && (
                <button className="btn" onClick={runTest} disabled={!canTest || busy !== null}>
                  {busy === "test" ? <Loader2 size={15} className="spin" /> : <Plug size={15} />}
                  Test connection
                </button>
              )}
              <button
                className="btn btn-primary"
                onClick={save}
                disabled={!canSave || busy !== null}
                title={live && !test?.ok ? "Test the connection first" : undefined}
              >
                {busy === "save" && <Loader2 size={15} className="spin" />}
                {editing ? "Save changes" : live ? "Save & choose datasets" : "Register tool"}
              </button>
            </div>
          </div>
        )}

        {step === "choose" && saved && (
          <ChooseDatasets
            tool={saved}
            onBack={editing ? undefined : () => setStep("connect")}
            onImported={() => {
              onChanged();
              setStep("done");
            }}
            setResult={setImportResult}
          />
        )}

        {step === "done" && <ImportDone result={importResult} onClose={onClose} />}
      </div>
    </div>
  );
}

function ChooseDatasets({
  tool,
  onBack,
  onImported,
  setResult,
}: {
  tool: MetadataTool;
  onBack?: () => void;
  onImported: () => void;
  setResult: (r: DatasetImportResult) => void;
}) {
  const [services, setServices] = useState<BrowseService[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<Record<string, Selection>>({});
  const [expanded, setExpanded] = useState<string | null>(null);
  const [schemas, setSchemas] = useState<Record<string, BrowseSchema[] | "loading" | string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .browseTool(tool.id)
      .then(setServices)
      .catch((e) => setLoadError(errorDetail(e)));
  }, [tool.id]);

  async function loadSchemas(fqn: string) {
    if (schemas[fqn]) return;
    setSchemas((s) => ({ ...s, [fqn]: "loading" }));
    try {
      const list = await api.browseSchemas(tool.id, fqn);
      setSchemas((s) => ({ ...s, [fqn]: list }));
    } catch (e) {
      setSchemas((s) => ({ ...s, [fqn]: errorDetail(e) }));
    }
  }

  function toggleDb(service: string, database: string, fqn: string) {
    setSelected((sel) => {
      const next = { ...sel };
      if (next[fqn]) delete next[fqn];
      else next[fqn] = { service, database, display_name: "", schemas: null };
      return next;
    });
  }

  function toggleSchema(fqn: string, schema: string, all: string[]) {
    setSelected((sel) => {
      const cur = sel[fqn];
      if (!cur) return sel;
      const current = cur.schemas ?? all;
      const nextSchemas = current.includes(schema)
        ? current.filter((s) => s !== schema)
        : [...current, schema];
      return {
        ...sel,
        [fqn]: { ...cur, schemas: nextSchemas.length === all.length ? null : nextSchemas },
      };
    });
  }

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!services) return [];
    if (!q) return services;
    return services
      .map((s) => ({
        ...s,
        databases: s.databases.filter(
          (d) => d.fqn.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
        ),
      }))
      .filter((s) => s.databases.length > 0);
  }, [services, filter]);

  const chosen = Object.values(selected);
  const invalid = chosen.some((c) => c.schemas !== null && c.schemas.length === 0);

  async function doImport() {
    setBusy(true);
    setError(null);
    try {
      const result = await api.importDatasets(
        tool.id,
        chosen.map((c) => ({
          service: c.service,
          database: c.database,
          display_name: c.display_name || undefined,
          schemas: c.schemas ?? [],
        }))
      );
      setResult(result);
      window.dispatchEvent(new Event("metalens:refresh-counts"));
      onImported();
    } catch (e) {
      setError(errorDetail(e));
    } finally {
      setBusy(false);
    }
  }

  if (loadError)
    return (
      <div className="wizard-body">
        <div className="test-result test-bad">
          <AlertTriangle size={17} />
          <span>Could not browse {tool.name}: {loadError}</span>
        </div>
      </div>
    );
  if (!services)
    return (
      <div className="wizard-body loading">
        <div className="spinner" />
      </div>
    );

  return (
    <div className="wizard-body">
      <input
        className="input"
        placeholder="Filter services and databases…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        style={{ width: "100%", marginBottom: 10 }}
      />
      <div className="browse-tree">
        {visible.length === 0 && (
          <div className="muted" style={{ padding: 16 }}>
            No database services found in {tool.name}.
          </div>
        )}
        {visible.map((svc) => (
          <div key={svc.name} className="bt-service">
            <div className="bt-service-head">
              <Server size={15} />
              <strong>{svc.name}</strong>
              {svc.service_type && <span className="badge field">{svc.service_type}</span>}
            </div>
            {svc.databases.map((d) => {
              const sel = selected[d.fqn];
              const taken = !!d.imported_by;
              const sch = schemas[d.fqn];
              const open = expanded === d.fqn;
              return (
                <div key={d.fqn} className={`bt-db${sel ? " bt-db-on" : ""}${taken ? " bt-db-taken" : ""}`}>
                  <div className="bt-db-row">
                    <input
                      type="checkbox"
                      checked={!!sel || d.imported_here}
                      disabled={taken}
                      onChange={() => toggleDb(svc.name, d.name, d.fqn)}
                    />
                    <Database size={15} />
                    <span className="mono" style={{ fontWeight: 600 }}>{d.name}</span>
                    {taken && (
                      <span className="badge status-RESOLVED">
                        {d.imported_here ? "Already imported" : `Imported via ${d.imported_by}`}
                      </span>
                    )}
                    {!taken && (
                      <button
                        className="btn btn-sm btn-ghost"
                        style={{ marginLeft: "auto" }}
                        onClick={() => {
                          setExpanded(open ? null : d.fqn);
                          loadSchemas(d.fqn);
                        }}
                      >
                        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        Schemas
                        {sel?.schemas ? ` (${sel.schemas.length} selected)` : sel ? " (all)" : ""}
                      </button>
                    )}
                  </div>
                  {d.description && <div className="bt-desc">{d.description}</div>}

                  {sel && (
                    <div className="bt-db-opts">
                      <label className="field" style={{ margin: 0 }}>
                        <span>Display name (optional)</span>
                        <input
                          className="input"
                          value={sel.display_name}
                          placeholder={d.name}
                          onChange={(e) =>
                            setSelected((s) => ({
                              ...s,
                              [d.fqn]: { ...sel, display_name: e.target.value },
                            }))
                          }
                        />
                      </label>
                    </div>
                  )}

                  {open && (
                    <div className="bt-schemas">
                      {sch === "loading" && <div className="muted">Loading schemas…</div>}
                      {typeof sch === "string" && sch !== "loading" && (
                        <div className="rec-error">{sch}</div>
                      )}
                      {Array.isArray(sch) &&
                        sch.map((s) => {
                          const all = sch.map((x) => x.name);
                          const on = sel ? (sel.schemas ?? all).includes(s.name) : false;
                          return (
                            <label key={s.fqn} className="bt-schema">
                              <input
                                type="checkbox"
                                disabled={!sel}
                                checked={on}
                                onChange={() => toggleSchema(d.fqn, s.name, all)}
                              />
                              <span className="mono">{s.name}</span>
                              <span className="muted">{s.table_count} tables</span>
                            </label>
                          );
                        })}
                      {Array.isArray(sch) && !sel && (
                        <div className="muted" style={{ fontSize: 12 }}>
                          Tick the database to choose schemas.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {error && <div className="rec-error" style={{ marginTop: 10 }}>{error}</div>}

      <div className="wizard-foot">
        {onBack && (
          <button className="btn btn-ghost" onClick={onBack} disabled={busy}>
            Back
          </button>
        )}
        <span className="muted" style={{ marginRight: "auto", fontSize: 13 }}>
          {chosen.length} database{chosen.length === 1 ? "" : "s"} selected
        </span>
        <button
          className="btn btn-primary"
          disabled={chosen.length === 0 || invalid || busy}
          onClick={doImport}
        >
          {busy && <Loader2 size={15} className="spin" />}
          {busy ? "Importing & scanning…" : `Import ${chosen.length || ""}`.trim()}
        </button>
      </div>
    </div>
  );
}

function ImportDone({
  result,
  onClose,
}: {
  result: DatasetImportResult | null;
  onClose: () => void;
}) {
  const tables = (result?.imported ?? []).reduce((n, d) => n + d.table_count, 0);
  const errs = Object.entries(result?.errors ?? {});
  return (
    <div className="wizard-body" style={{ textAlign: "center" }}>
      {result && result.imported.length > 0 && (
        <>
          <div className="inbox-zero-icon" style={{ width: 56, height: 56 }}>
            <CheckCircle2 size={28} />
          </div>
          <div className="inbox-zero-title" style={{ fontSize: 19 }}>
            Imported {result.imported.length} dataset{result.imported.length === 1 ? "" : "s"}
          </div>
          <div className="muted">
            {tables} tables synced · {result.findings_created} new metadata gaps detected
          </div>
        </>
      )}
      {errs.length > 0 && (
        <div style={{ textAlign: "left", marginTop: 14 }}>
          {errs.map(([k, v]) => (
            <div key={k} className="rec-error">
              <strong className="mono">{k}</strong>: {v}
            </div>
          ))}
        </div>
      )}
      <div className="wizard-foot" style={{ justifyContent: "center" }}>
        <button className="btn btn-primary" onClick={onClose}>
          Done
        </button>
      </div>
    </div>
  );
}
