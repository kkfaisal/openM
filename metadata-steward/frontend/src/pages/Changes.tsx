import { ArrowRight, CheckCircle2, RotateCcw } from "lucide-react";
import { api } from "../api";
import { EmptyState, FieldBadge, Loading } from "../components/ui";
import { fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Changes() {
  const { data, loading, error } = useAsync(() => api.changes(), []);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const changes = data ?? [];

  return (
    <div>
      {changes.length === 0 ? (
        <EmptyState text="No metadata changes applied yet." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Field</th>
                <th>Change</th>
                <th>Verified</th>
                <th>Applied by</th>
                <th>Time</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.id}>
                  <td className="mono">{c.entity}</td>
                  <td>
                    <FieldBadge field={c.field} />
                  </td>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <span className="muted" style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {c.old_value ?? "(empty)"}
                      </span>
                      <ArrowRight size={13} color="#b1a8c9" />
                      <span style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontWeight: 600 }}>
                        {c.new_value}
                      </span>
                    </span>
                  </td>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "#2e9e68", fontWeight: 600, fontSize: 12.5 }}>
                      <CheckCircle2 size={14} /> Verified
                    </span>
                  </td>
                  <td className="muted">{c.applied_by}</td>
                  <td className="muted">{fmtDate(c.applied_at)}</td>
                  <td>
                    {c.old_value != null && (
                      <span
                        className="btn btn-sm"
                        title="Rollback restores the previous value"
                        style={{ cursor: "default", pointerEvents: "none" }}
                      >
                        <RotateCcw size={14} /> Rollback
                      </span>
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
