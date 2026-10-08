import { api } from "../api";
import { EmptyState, Loading } from "../components/ui";
import { fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export default function Activity() {
  const { data, loading, error } = useAsync(() => api.audit(), []);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const events = data ?? [];

  return (
    <div>
      {events.length === 0 ? (
        <EmptyState text="No audit events recorded." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Field</th>
                <th>Change</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="muted" style={{ whiteSpace: "nowrap" }}>
                    {fmtDate(e.timestamp)}
                  </td>
                  <td style={{ fontWeight: 600 }}>
                    {e.actor}
                    <div className="flag">{e.actor_type}</div>
                  </td>
                  <td>
                    <span className="badge field">{e.action.replace(/_/g, " ")}</span>
                  </td>
                  <td className="mono">{e.entity ?? "—"}</td>
                  <td className="muted">{e.field ?? "—"}</td>
                  <td style={{ fontSize: 12.5 }}>
                    {e.old_value || e.new_value ? (
                      <>
                        <span className="muted">{e.old_value ?? "(empty)"}</span>
                        {e.new_value ? (
                          <>
                            {" → "}
                            <span style={{ fontWeight: 600 }}>{e.new_value}</span>
                          </>
                        ) : null}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="muted" style={{ maxWidth: 320 }}>
                    {e.detail ?? (e.confidence != null ? `confidence ${e.confidence}` : "")}
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
