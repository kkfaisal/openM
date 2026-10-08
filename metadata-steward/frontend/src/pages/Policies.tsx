import { useState } from "react";
import { ShieldCheck, ToggleLeft, ToggleRight } from "lucide-react";
import { api } from "../api";
import { ActionModeBadge, EmptyState, FieldBadge, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import type { Policy } from "../types";

export default function Policies() {
  const { data, loading, error, reload } = useAsync(() => api.policies(), []);
  const [busyId, setBusyId] = useState<string | null>(null);

  if (loading && !data) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const policies = data ?? [];

  async function toggle(p: Policy) {
    setBusyId(p.id);
    try {
      await api.updatePolicy(p.id, { enabled: !p.enabled });
      reload();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, padding: "14px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <ShieldCheck size={18} color="#7b5fc7" />
          <div>
            <div style={{ fontWeight: 700 }}>Deterministic guardrails</div>
            <div className="card-sub">
              Every proposed change passes through these policies before any
              action. First match by priority wins; safe defaults apply when
              nothing matches.
            </div>
          </div>
        </div>
      </div>

      {policies.length === 0 ? (
        <EmptyState text="No policies defined." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Priority</th>
                <th>Policy</th>
                <th>Field</th>
                <th>Conditions</th>
                <th>Action</th>
                <th>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 700, color: "#7b5fc7" }}>{p.priority}</td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{p.name}</div>
                    {p.description && (
                      <div className="muted" style={{ fontSize: 12, maxWidth: 380 }}>
                        {p.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <FieldBadge field={p.field} />
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>
                    {Object.entries(p.conditions).length
                      ? Object.entries(p.conditions)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(", ")
                      : "(always)"}
                  </td>
                  <td>
                    <ActionModeBadge mode={p.action_mode} />
                  </td>
                  <td>
                    <button
                      className="btn btn-sm"
                      onClick={() => toggle(p)}
                      disabled={busyId === p.id}
                      style={{ color: p.enabled ? "#2e9e68" : "#b1a8c9" }}
                    >
                      {p.enabled ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                      {p.enabled ? "On" : "Off"}
                    </button>
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
