import { Fragment, useState } from "react";
import { Bot, CheckCircle2, Circle } from "lucide-react";
import { api } from "../api";
import { EmptyState, Loading } from "../components/ui";
import { fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { AgentRun } from "../types";

export default function Agents() {
  const { data, loading, error } = useAsync(() => api.agentRuns(), []);
  const [openId, setOpenId] = useState<string | null>(null);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const runs = data ?? [];

  return (
    <div>
      {runs.length === 0 ? (
        <EmptyState text="No agent runs recorded yet." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Finding</th>
                <th>Status</th>
                <th>Started</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run: AgentRun) => (
                <Fragment key={run.id}>
                  <tr
                    className="row-link"
                    onClick={() => setOpenId(openId === run.id ? null : run.id)}
                  >
                    <td style={{ fontWeight: 600 }}>
                      <Bot size={14} style={{ verticalAlign: -2, marginRight: 6, color: "#7b5fc7" }} />
                      {run.agent_name}
                    </td>
                    <td className="mono">{run.finding_id?.slice(0, 12) ?? "—"}</td>
                    <td>
                      <span className={`badge status-${run.status}`}>{run.status}</span>
                    </td>
                    <td className="muted">{fmtDate(run.started_at)}</td>
                    <td className="muted" style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {run.summary ?? ""}
                    </td>
                  </tr>
                  {openId === run.id && (
                    <tr>
                      <td colSpan={5} style={{ background: "#f6f2fb" }}>
                        <div style={{ padding: "6px 8px" }}>
                          <div className="flag" style={{ marginBottom: 8 }}>
                            OBSERVABLE STEPS (tool calls & summarized decisions)
                          </div>
                          <ul className="evidence-list">
                            {run.steps.map((s, i) => (
                              <li key={i}>
                                {s.ok ? (
                                  <CheckCircle2 size={16} color="#2e9e68" style={{ marginTop: 2 }} />
                                ) : (
                                  <Circle size={16} color="#b1a8c9" style={{ marginTop: 2 }} />
                                )}
                                <div>
                                  <div style={{ fontWeight: 600 }}>{s.step}</div>
                                  <div className="muted" style={{ fontSize: 12.5 }}>{s.detail}</div>
                                </div>
                              </li>
                            ))}
                          </ul>
                          {run.result_json && (
                            <div style={{ marginTop: 10 }}>
                              <div className="flag">RESULT</div>
                              <pre style={{ fontSize: 12, background: "#fff", border: "1px solid #e4dcf1", borderRadius: 8, padding: 10, overflow: "auto" }}>
                                {JSON.stringify(run.result_json, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
