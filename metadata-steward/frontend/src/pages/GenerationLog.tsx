import { useMemo } from "react";
import { api } from "../api";
import { EmptyState, Loading, StatusBadge } from "../components/ui";
import { fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { Finding } from "../types";

export default function GenerationLog() {
  const { data: runs, loading, error } = useAsync(() => api.agentRuns(), []);
  const { data: findings } = useAsync(() => api.findings(), []);

  const entityMap = useMemo(() => {
    const m = new Map<string, string>();
    (findings ?? []).forEach((f: Finding) => m.set(f.id, f.entity));
    return m;
  }, [findings]);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const log = (runs ?? []).filter((r) => r.agent_name !== "Error");

  return (
    <div>
      {log.length === 0 ? (
        <EmptyState text="No generations yet. Run a scan or regenerate." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Agent</th>
                <th>Entity</th>
                <th>Generated</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {log.map((r) => {
                const gen = r.steps.find((s) => s.step === "Generated candidate");
                return (
                  <tr key={r.id}>
                    <td className="muted" style={{ whiteSpace: "nowrap" }}>
                      {fmtDate(r.started_at)}
                    </td>
                    <td style={{ fontWeight: 600 }}>{r.agent_name}</td>
                    <td className="mono">{entityMap.get(r.finding_id ?? "") ?? r.finding_id ?? "—"}</td>
                    <td
                      style={{
                        maxWidth: 380,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={gen?.detail ?? r.summary ?? ""}
                    >
                      {gen?.detail ?? r.summary ?? "—"}
                    </td>
                    <td>
                      <StatusBadge status={r.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
