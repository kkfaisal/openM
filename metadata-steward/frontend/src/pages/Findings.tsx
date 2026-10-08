import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { EmptyState, Loading, SeverityBadge, StatusBadge } from "../components/ui";
import { findingLabel, fmtDate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { Finding } from "../types";

export default function Findings() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [type, setType] = useState(params.get("type") ?? "");
  const [severity, setSeverity] = useState(params.get("severity") ?? "");
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [domain, setDomain] = useState(params.get("domain") ?? "");
  const [dataset, setDataset] = useState(params.get("dataset") ?? "");

  const { data, loading, error } = useAsync(
    () =>
      api.findings({
        ...(type && { type }),
        ...(severity && { severity }),
        ...(status && { status }),
        ...(domain && { domain }),
        ...(dataset && { dataset }),
      }),
    [type, severity, status, domain, dataset]
  );

  if (loading && !data) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const findings = data ?? [];

  return (
    <div>
      <div className="filters">
        <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {[...new Set((data ?? []).map((f) => f.type))].map((t) => (
            <option key={t} value={t}>
              {findingLabel(t)}
            </option>
          ))}
        </select>
        <select className="select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All severities</option>
          {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["OPEN", "INVESTIGATING", "RECOMMENDED", "RESOLVED", "REJECTED"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select className="select" value={domain} onChange={(e) => setDomain(e.target.value)}>
          <option value="">All domains</option>
          {[...new Set((data ?? []).map((f) => f.domain).filter(Boolean))].map((d) => (
            <option key={d as string}>{d}</option>
          ))}
        </select>
        <span className="toolbar-note">{findings.length} result(s)</span>
      </div>

      {findings.length === 0 ? (
        <EmptyState text="No findings match the current filters." />
      ) : (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Type</th>
                <th>Entity</th>
                <th>Domain</th>
                <th>Status</th>
                <th>Detected</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f: Finding) => (
                <tr
                  key={f.id}
                  className="row-link"
                  onClick={() => navigate(`/findings/${f.id}`)}
                >
                  <td>
                    <SeverityBadge severity={f.severity} />
                  </td>
                  <td style={{ fontWeight: 600 }}>{findingLabel(f.type)}</td>
                  <td className="mono">{f.entity}</td>
                  <td>{f.domain ?? <span className="muted">—</span>}</td>
                  <td>
                    <StatusBadge status={f.status} />
                  </td>
                  <td className="muted">{fmtDate(f.detected_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
