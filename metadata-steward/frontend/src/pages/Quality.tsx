import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, ExternalLink, FlaskConical, Loader2, Play, TriangleAlert } from "lucide-react";
import { api } from "../api";
import { useToast } from "../components/Toast";
import { EmptyState, Loading } from "../components/ui";
import { errorDetail, fieldLabel, fmtDate, relTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { EvalJob, EvalRun } from "../types";

// Validated two-series palette (app primary + accent). Gold is < 3:1 on white,
// so the chart always has a legend, tooltips and the table views below.
const C_ACCEPTED = "#7b5fc7";
const C_REJECTED = "#d9a13f";

const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);

/** Metrics worth surfacing per suite, in display order. */
const HEADLINE: Record<string, [string, string, "pct" | "num"][]> = {
  golden: [
    ["rag.description_similarity", "Description similarity (RAG)", "num"],
    ["rag_lift.description_similarity", "RAG lift: description", "num"],
    ["rag.label_exact_match", "Label accuracy (RAG)", "pct"],
    ["rag_lift.label_exact_match", "RAG lift: label", "num"],
    ["detection.recall", "Sensitive detection recall", "pct"],
  ],
  decisions: [
    ["acceptance_rate", "Acceptance", "pct"],
    ["edit_rate", "Edit rate", "pct"],
    ["brier_score", "Brier score", "num"],
    ["expected_calibration_error", "Calibration error", "num"],
  ],
};

function fmtMetric(v: number | undefined, kind: "pct" | "num") {
  if (v == null) return "—";
  return kind === "pct" ? pct(v) : v.toFixed(3);
}

export default function Quality() {
  const toast = useToast();
  const [days, setDays] = useState(30);
  const q = useAsync(() => api.quality(days), [days]);
  const runs = useAsync(() => api.evalRuns(), []);
  const [jobs, setJobs] = useState<EvalJob[]>([]);

  const running = jobs.some((j) => j.status === "RUNNING");
  useEffect(() => {
    api.evalJobs().then(setJobs).catch(() => {});
  }, []);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      const js = await api.evalJobs().catch(() => jobs);
      setJobs(js);
      if (!js.some((j) => j.status === "RUNNING")) {
        const last = js[0];
        toast(
          last?.status === "SUCCEEDED" ? "success" : "error",
          last?.status === "SUCCEEDED" ? `Evaluation "${last.suite}" finished` : "Evaluation failed",
          last?.error ?? "Results are logged to MLflow."
        );
        runs.reload();
      }
    }, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running]);

  async function start(suite: "golden" | "decisions") {
    try {
      const job = await api.runEval(suite, suite === "golden" ? 20 : 0);
      setJobs((js) => [job, ...js]);
    } catch (e) {
      toast("error", "Could not start the evaluation", errorDetail(e));
    }
  }

  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <EmptyState text={q.error} />;
  const d = q.data!;
  const ml = d.mlflow;
  const t = d.totals;

  return (
    <div className="quality">
      <div className={`card ml-banner ${ml.ready ? "" : "ml-off"}`}>
        <Activity size={18} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700 }}>
            {ml.ready ? "MLflow tracing on" : ml.enabled ? "MLflow unreachable" : "MLflow not configured"}
          </div>
          <div className="muted" style={{ fontSize: 12.5 }}>
            {ml.ready
              ? `Every agent run is traced to "${ml.experiment}". Reviewer decisions are attached as feedback.`
              : ml.error ?? "Set MLFLOW_TRACKING_URI to enable tracing. Live metrics below still work."}
          </div>
        </div>
        <select className="select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
        {ml.ready && ml.ui_url && (
          <a className="btn btn-sm" href={`${ml.ui_url}/#/experiments/${ml.experiment_id}/traces`} target="_blank" rel="noreferrer">
            <ExternalLink size={14} /> Open MLflow
          </a>
        )}
      </div>

      <div className="q-kpis">
        <Kpi label="Agent runs" value={t.agent_runs.toLocaleString()} />
        <Kpi
          label="Failure rate"
          value={pct(t.failure_rate)}
          warn={t.failure_rate > 0.1}
          hint="Runs that errored (LLM, catalog or connector failures)"
        />
        <Kpi label="Accepted by reviewers" value={pct(t.acceptance_rate)} hint={`${t.reviewed} reviewed`} />
        <Kpi label="Edited before approval" value={pct(t.edit_rate)} hint="Share of accepted suggestions a human changed" />
        <Kpi
          label="Calibration error"
          value={t.calibration_error == null ? "—" : t.calibration_error.toFixed(3)}
          hint="Gap between confidence and actual acceptance (lower is better)"
        />
      </div>

      <div className="q-grid">
        <div className="card">
          <div className="card-title">Reviewer decisions per day</div>
          <div className="card-sub" style={{ marginBottom: 10 }}>
            Accepted vs rejected recommendations
          </div>
          <div className="q-legend">
            <span><i style={{ background: C_ACCEPTED }} /> Accepted</span>
            <span><i style={{ background: C_REJECTED }} /> Rejected</span>
          </div>
          <div style={{ height: 210 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d.trend} margin={{ top: 8, right: 4, left: -18, bottom: 0 }} barCategoryGap={3}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="day"
                  tickFormatter={(v: string) => v.slice(5)}
                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                  minTickGap={24}
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--muted)" }} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: "rgba(123,95,199,0.06)" }}
                  contentStyle={{ borderRadius: 10, fontSize: 12, border: "1px solid var(--border)" }}
                />
                <Bar dataKey="accepted" name="Accepted" stackId="d" fill={C_ACCEPTED} stroke="#fff" strokeWidth={1} />
                <Bar dataKey="rejected" name="Rejected" stackId="d" fill={C_REJECTED} stroke="#fff" strokeWidth={1} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-title">Is confidence trustworthy?</div>
          <div className="card-sub" style={{ marginBottom: 12 }}>
            Mean confidence vs actual acceptance, by confidence bucket
          </div>
          {d.calibration.length === 0 ? (
            <div className="muted">No reviewed recommendations yet.</div>
          ) : (
            <table className="table q-calib">
              <thead>
                <tr>
                  <th>Confidence</th>
                  <th>Reviewed</th>
                  <th>Predicted vs accepted</th>
                </tr>
              </thead>
              <tbody>
                {d.calibration.map((b) => (
                  <tr key={b.bucket}>
                    <td className="mono">{b.bucket}</td>
                    <td>{b.count}</td>
                    <td>
                      <div className="q-pair">
                        <span className="q-pair-row">
                          <span className="q-pair-track">
                            <span style={{ width: `${b.mean_confidence * 100}%`, background: "var(--muted-2)" }} />
                          </span>
                          {pct(b.mean_confidence)} predicted
                        </span>
                        <span className="q-pair-row">
                          <span className="q-pair-track">
                            <span style={{ width: `${b.acceptance_rate * 100}%`, background: C_ACCEPTED }} />
                          </span>
                          {pct(b.acceptance_rate)} accepted
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {t.brier_score != null && (
            <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              Brier score {t.brier_score.toFixed(3)} (0 = perfect).
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title" style={{ marginBottom: 10 }}>Agents</div>
        <table className="table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Runs</th>
              <th>Failure rate</th>
              <th>Latency p50</th>
              <th>Latency p95</th>
              <th>Traced</th>
            </tr>
          </thead>
          <tbody>
            {d.agents.map((a) => (
              <tr key={a.agent}>
                <td style={{ fontWeight: 600 }}>{a.agent}</td>
                <td>{a.runs}</td>
                <td>
                  {a.failure_rate > 0.1 && <TriangleAlert size={13} color="var(--red)" style={{ verticalAlign: -2, marginRight: 4 }} />}
                  {pct(a.failure_rate)}
                </td>
                <td>{a.latency_p50_s == null ? "—" : `${a.latency_p50_s}s`}</td>
                <td>{a.latency_p95_s == null ? "—" : `${a.latency_p95_s}s`}</td>
                <td>{a.traced}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-title" style={{ marginBottom: 10 }}>By metadata field</div>
        <table className="table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Suggestions</th>
              <th>Auto-applied</th>
              <th>Pending</th>
              <th>Reviewed</th>
              <th>Accepted</th>
              <th>Edited</th>
              <th>Avg confidence</th>
            </tr>
          </thead>
          <tbody>
            {d.fields.map((f) => (
              <tr key={f.field}>
                <td style={{ fontWeight: 600 }}>{fieldLabel(f.field)}</td>
                <td>{f.recommendations}</td>
                <td>{f.auto_applied}</td>
                <td>{f.pending}</td>
                <td>{f.reviewed}</td>
                <td>{pct(f.acceptance_rate)}</td>
                <td>{pct(f.edit_rate)}</td>
                <td>{pct(f.avg_confidence)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header">
          <FlaskConical size={18} color="var(--primary)" />
          <div style={{ flex: 1 }}>
            <div className="card-title">Evaluations</div>
            <div className="card-sub">
              <strong>Golden</strong>: accuracy against a labelled data dictionary, with and without RAG.{" "}
              <strong>Decisions</strong>: acceptance and calibration from real reviews.
            </div>
          </div>
          <button className="btn btn-sm" disabled={running || !ml.ready} onClick={() => start("decisions")}>
            <Play size={14} /> Run decisions
          </button>
          <button className="btn btn-sm btn-primary" disabled={running || !ml.ready} onClick={() => start("golden")}>
            {running ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
            {running ? "Running…" : "Run golden set"}
          </button>
        </div>

        {jobs.filter((j) => j.status !== "SUCCEEDED").map((j) => (
          <div key={j.id} className={j.status === "FAILED" ? "rec-error" : "test-result test-info"} style={{ marginBottom: 8 }}>
            {j.status === "RUNNING" ? <Loader2 size={15} className="spin" /> : <TriangleAlert size={15} />}
            <span>
              {j.suite}: {j.status.toLowerCase()} · started {relTime(j.started_at)}
              {j.error ? `: ${j.error}` : ""}
            </span>
          </div>
        ))}

        {!runs.data?.available ? (
          <div className="muted" style={{ fontSize: 13 }}>
            Evaluation history needs MLflow. {runs.data?.error}
          </div>
        ) : runs.data.runs.length === 0 ? (
          <div className="muted" style={{ fontSize: 13 }}>No evaluation runs yet.</div>
        ) : (
          <div className="q-runs">
            {runs.data.runs.map((r) => (
              <EvalRunRow key={r.run_id} run={r} />
            ))}
          </div>
        )}
      </div>

      {d.recent_traces.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-title" style={{ marginBottom: 10 }}>Recent traces</div>
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Status</th>
                <th>Latency</th>
                <th>When</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.recent_traces.map((r) => (
                <tr key={r.trace_id}>
                  <td style={{ fontWeight: 600 }}>{r.agent}</td>
                  <td><span className={`badge status-${r.status}`}>{r.status}</span></td>
                  <td>{r.latency_s == null ? "—" : `${r.latency_s}s`}</td>
                  <td className="muted">{fmtDate(r.started_at)}</td>
                  <td style={{ textAlign: "right" }}>
                    {r.trace_url && (
                      <a className="btn btn-sm btn-ghost" href={r.trace_url} target="_blank" rel="noreferrer">
                        <ExternalLink size={13} /> Trace
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, hint, warn }: { label: string; value: string; hint?: string; warn?: boolean }) {
  return (
    <div className="card q-kpi" title={hint}>
      <div className="q-kpi-value">
        {warn && <TriangleAlert size={16} color="var(--red)" style={{ marginRight: 6 }} />}
        {value}
      </div>
      <div className="q-kpi-label">{label}</div>
      {hint && <div className="q-kpi-hint">{hint}</div>}
    </div>
  );
}

function EvalRunRow({ run }: { run: EvalRun }) {
  const items = HEADLINE[run.suite ?? ""] ?? [];
  return (
    <div className="q-run">
      <div className="q-run-head">
        <span className="badge field">{run.suite}</span>
        <span className="mono" style={{ fontSize: 12 }}>{run.name}</span>
        <span className="muted" style={{ fontSize: 12 }}>{relTime(new Date(run.start_time).toISOString())}</span>
        {run.params.llm_model && <span className="muted" style={{ fontSize: 12 }}>· {run.params.llm_model}</span>}
        {run.url && (
          <a href={run.url} target="_blank" rel="noreferrer" className="btn btn-sm btn-ghost" style={{ marginLeft: "auto" }}>
            <ExternalLink size={13} /> MLflow
          </a>
        )}
      </div>
      <div className="q-run-metrics">
        {items.map(([key, label, kind]) => {
          const v = run.metrics[key];
          const lift = key.startsWith("rag_lift");
          return (
            <div key={key} className="q-metric">
              <div className={`q-metric-v${lift && v != null ? (v >= 0 ? " up" : " down") : ""}`}>
                {lift && v != null && v > 0 ? "+" : ""}
                {fmtMetric(v, kind)}
              </div>
              <div className="q-metric-l">{label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
