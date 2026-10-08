import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { Link } from "react-router-dom";

export function SeverityBadge({ severity }: { severity: string }) {
  return <span className={`badge sev-${severity}`}>{severity}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge status-${status}`}>{status}</span>;
}

export function ActionModeBadge({ mode }: { mode: string }) {
  return <span className={`badge mode-${mode}`}>{mode.replace(/_/g, " ")}</span>;
}

export function FieldBadge({ field }: { field: string }) {
  return <span className="badge field">{field}</span>;
}

export function ConfidenceBar({ value }: { value: number }) {
  const pctv = Math.round(value * 100);
  return (
    <span className="conf-bar">
      <span className="conf-track">
        <span className="conf-fill" style={{ width: `${pctv}%` }} />
      </span>
      <span className="conf-value">{pctv}%</span>
    </span>
  );
}

export function StatCard({
  label,
  value,
  icon,
  iconClass,
  delta,
  to,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  iconClass: string;
  delta?: { value: string; up?: boolean };
  to?: string;
}) {
  const inner = (
    <>
      <div className="stat-icon" style={{ background: iconClass }}>
        {icon}
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {delta && (
        <div className={`stat-delta ${delta.up ? "up" : "down"}`}>
          {delta.value}
        </div>
      )}
    </>
  );

  if (to) {
    return (
      <Link to={to} className="card stat-card" style={{ color: "inherit" }}>
        {inner}
      </Link>
    );
  }
  return <div className="card stat-card">{inner}</div>;
}

export function Loading() {
  return (
    <div className="loading">
      <div className="spinner" />
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty">
      <Inbox />
      <div>{text}</div>
    </div>
  );
}
