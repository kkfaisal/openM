import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, X } from "lucide-react";
import { api } from "../api";
import {
  ActionModeBadge,
  ConfidenceBar,
  EmptyState,
  FieldBadge,
  Loading,
  StatusBadge,
} from "../components/ui";
import { fieldLabel, fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { Finding } from "../types";

const FIELDS = ["description", "column_description", "owner", "domain", "classification"];

export default function Recommendations() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [field, setField] = useState(params.get("field") ?? "");
  const [busy, setBusy] = useState<string | null>(null);

  const { data, loading, error, reload } = useAsync(
    () => api.recommendations({ ...(status && { status }), ...(field && { field }) }),
    [status, field]
  );
  const { data: findings } = useAsync(() => api.findings(), []);

  const entityMap = useMemo(() => {
    const m = new Map<string, string>();
    (findings ?? []).forEach((f: Finding) => m.set(f.id, f.entity));
    return m;
  }, [findings]);

  if (loading && !data) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const recs = data ?? [];

  async function act(id: string, kind: "approve" | "reject") {
    setBusy(id);
    try {
      const body = { decided_by: "Demo Steward" };
      if (kind === "approve") await api.recommendApprove(id, body);
      else await api.recommendReject(id, body);
      reload();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="filters">
        <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["PENDING", "APPLIED", "REJECTED"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select className="select" value={field} onChange={(e) => setField(e.target.value)}>
          <option value="">All fields</option>
          {FIELDS.map((f) => (
            <option key={f} value={f}>
              {fieldLabel(f)}
            </option>
          ))}
        </select>
        <span className="toolbar-note">{recs.length} recommendation(s)</span>
      </div>

      {recs.length === 0 ? (
        <EmptyState text="No recommendations match the current filters." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Entity</th>
                <th>Suggested value</th>
                <th>Confidence</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {recs.map((r) => (
                <tr key={r.id}>
                  <td>
                    <FieldBadge field={fieldLabel(r.field)} />
                  </td>
                  <td className="mono">{entityMap.get(r.finding_id) ?? r.finding_id}</td>
                  <td style={{ maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.new_value}
                  </td>
                  <td>
                    <ConfidenceBar value={r.confidence} />
                  </td>
                  <td>
                    <ActionModeBadge mode={r.action_mode} />
                  </td>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="muted">{fmtDate(r.created_at)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {r.status === "PENDING" ? (
                      <div style={{ display: "flex", gap: 6 }}>
                        <button
                          className="btn btn-success btn-sm"
                          disabled={busy !== null}
                          onClick={() => act(r.id, "approve")}
                        >
                          <Check size={14} /> Approve
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          disabled={busy !== null}
                          onClick={() => act(r.id, "reject")}
                        >
                          <X size={14} /> Reject
                        </button>
                      </div>
                    ) : (
                      <button
                        className="btn btn-sm"
                        onClick={() => navigate(`/findings/${r.finding_id}`)}
                      >
                        View →
                      </button>
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
