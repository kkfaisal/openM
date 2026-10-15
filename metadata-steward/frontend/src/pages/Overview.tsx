import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  Clock,
  Inbox,
  Layers,
  Lightbulb,
  Radar,
  ShieldAlert,
  Sparkles,
  UserX,
  XCircle,
} from "lucide-react";
import { api } from "../api";
import DatasetCard from "../components/DatasetCard";
import { useToast } from "../components/Toast";
import { EmptyState, EntityName, Loading } from "../components/ui";
import { errorDetail, findingLabel, humanAction, relTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { Finding, OverviewStats } from "../types";

const DIMENSIONS: { key: string; label: string; to: string }[] = [
  { key: "ownership", label: "Ownership", to: "/findings?type=MISSING_OWNER" },
  { key: "domain", label: "Domain", to: "/findings?type=MISSING_DOMAIN" },
  { key: "descriptions", label: "Table descriptions", to: "/findings?type=MISSING_DESCRIPTION" },
  {
    key: "column_documentation",
    label: "Column docs",
    to: "/findings?type=MISSING_COLUMN_DESCRIPTION",
  },
  {
    key: "classification",
    label: "Classification",
    to: "/findings?type=MISSING_CLASSIFICATION",
  },
];

function tone(v: number): "good" | "ok" | "bad" {
  return v >= 0.8 ? "good" : v >= 0.5 ? "ok" : "bad";
}

export default function Overview() {
  const overview = useAsync(() => api.overview(), []);
  const health = useAsync(() => api.health(), []);
  const findings = useAsync(() => api.findings(), []);
  const datasets = useAsync(() => api.datasets(), []);

  if (overview.loading && !overview.data) return <Loading />;
  if (overview.error) return <EmptyState text={overview.error} />;
  const o = overview.data!;

  const reloadAll = () => {
    overview.reload();
    health.reload();
    findings.reload();
    datasets.reload();
  };

  return (
    <div className="overview">
      <div className="ov-hero">
        <HealthCard o={o} dims={health.data?.dimensions ?? {}} />
        <AttentionCard o={o} findings={findings.data ?? []} onDone={reloadAll} />
      </div>

      <Pipeline o={o} findings={findings.data ?? []} />

      <div className="ov-split">
        <DomainCoverage o={o} />
        <RecentActivity o={o} />
      </div>

      <div className="section-title ov-section-title">
        <Layers size={20} color="var(--primary)" />
        Data Sets
        <span className="muted" style={{ fontWeight: 400, fontSize: 14 }}>
          — {datasets.data?.length ?? 0} total
        </span>
      </div>
      {datasets.loading && !datasets.data ? (
        <Loading />
      ) : (datasets.data ?? []).length === 0 ? (
        <EmptyState text="No datasets synced yet." />
      ) : (
        datasets.data!.map((d) => (
          <DatasetCard key={d.key} dataset={d} onSaved={datasets.reload} />
        ))
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Health */

function HealthRing({ value }: { value: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, value));
  return (
    <svg className="health-ring" viewBox="0 0 128 128" width={128} height={128}>
      <defs>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#8b6cd9" />
          <stop offset="100%" stopColor="#d9a13f" />
        </linearGradient>
      </defs>
      <circle cx="64" cy="64" r={r} fill="none" stroke="var(--primary-soft)" strokeWidth="12" />
      <circle
        className="health-ring-arc"
        cx="64"
        cy="64"
        r={r}
        fill="none"
        stroke="url(#ringGrad)"
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - v / 100)}
        transform="rotate(-90 64 64)"
        style={{ ["--ring-c" as string]: c }}
      />
      <text x="64" y="62" textAnchor="middle" className="health-ring-value">
        {Math.round(v)}
      </text>
      <text x="64" y="82" textAnchor="middle" className="health-ring-label">
        out of 100
      </text>
    </svg>
  );
}

function HealthCard({ o, dims }: { o: OverviewStats; dims: Record<string, number> }) {
  const trend = o.trend.slice(-30);
  const weakest = DIMENSIONS.filter((d) => d.key in dims).sort(
    (a, b) => dims[a.key] - dims[b.key]
  )[0];
  const grade =
    o.health >= 85 ? "Excellent" : o.health >= 70 ? "Good" : o.health >= 50 ? "Fair" : "Needs work";

  return (
    <div className="card ov-health">
      <div className="ov-health-top">
        <HealthRing value={o.health} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="eyebrow">Metadata health</div>
          <div className="ov-health-grade">{grade}</div>
          <div className="muted" style={{ fontSize: 13 }}>
            {o.total_tables} tables · {o.total_columns} columns monitored
          </div>
          {o.health_delta !== 0 && (
            <div className={`stat-delta ${o.health_delta > 0 ? "up" : "down"}`}>
              {o.health_delta > 0 ? "▲" : "▼"} {Math.abs(o.health_delta)} pts since last scan
            </div>
          )}
          {trend.length > 1 && (
            <div style={{ height: 52, marginTop: 8 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#7b5fc7" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#7b5fc7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={["dataMin - 5", "dataMax + 5"]} />
                  <Tooltip
                    formatter={(v: number) => [`${v}`, "Health"]}
                    labelFormatter={() => ""}
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="overall"
                    stroke="#7b5fc7"
                    strokeWidth={2}
                    fill="url(#trendFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      <div className="dim-list">
        {DIMENSIONS.filter((d) => d.key in dims).map((d) => {
          const v = dims[d.key];
          return (
            <Link key={d.key} to={d.to} className="dim-row">
              <span className="dim-label">{d.label}</span>
              <span className="dim-track">
                <span className={`dim-fill dim-${tone(v)}`} style={{ width: `${v * 100}%` }} />
              </span>
              <span className="dim-value">{Math.round(v * 100)}%</span>
            </Link>
          );
        })}
      </div>

      {weakest && dims[weakest.key] < 0.8 && (
        <Link to={weakest.to} className="insight">
          <Sparkles size={16} />
          <span>
            <strong>{weakest.label}</strong> is your biggest gap at{" "}
            {Math.round(dims[weakest.key] * 100)}%. Fixing it lifts overall health the most.
          </span>
          <ChevronRight size={16} style={{ marginLeft: "auto", flexShrink: 0 }} />
        </Link>
      )}
    </div>
  );
}

/* ------------------------------------------------------------- Attention */

function AttentionCard({
  o,
  findings,
  onDone,
}: {
  o: OverviewStats;
  findings: Finding[];
  onDone: () => void;
}) {
  const toast = useToast();
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const cancelled = useRef(false);

  const open = findings.filter((f) => f.status === "OPEN");
  const openBy = (type: string) => open.filter((f) => f.type === type).length;
  const sensitive = openBy("MISSING_CLASSIFICATION");
  const owners = openBy("MISSING_OWNER");
  const stale = openBy("STALE_ENTITY");

  async function investigateAll() {
    cancelled.current = false;
    const queue = [...open];
    let ok = 0;
    const failures: string[] = [];
    setProgress({ done: 0, total: queue.length });
    for (let i = 0; i < queue.length; i++) {
      if (cancelled.current) break;
      try {
        await api.investigate(queue[i].id);
        ok++;
      } catch (e) {
        failures.push(errorDetail(e));
      }
      setProgress({ done: i + 1, total: queue.length });
    }
    setProgress(null);
    if (ok > 0) {
      toast(
        "success",
        `Agents investigated ${ok} finding${ok === 1 ? "" : "s"}`,
        "New recommendations are waiting in your Approval inbox."
      );
    }
    if (failures.length > 0) {
      toast(
        "error",
        `${failures.length} finding${failures.length === 1 ? "" : "s"} could not be investigated`,
        failures[0] + (failures.length > 1 ? ` (and ${failures.length - 1} more)` : "")
      );
    }
    window.dispatchEvent(new Event("metalens:refresh-counts"));
    onDone();
  }

  const items = [
    {
      show: sensitive > 0,
      icon: ShieldAlert,
      tone: "red",
      title: `${sensitive} possibly sensitive column${sensitive === 1 ? "" : "s"} unclassified`,
      sub: "PII and sensitive data without a classification tag",
      to: "/findings?type=MISSING_CLASSIFICATION&status=OPEN",
    },
    {
      show: owners > 0,
      icon: UserX,
      tone: "amber",
      title: `${owners} table${owners === 1 ? "" : "s"} without an owner`,
      sub: "Nobody accountable for these datasets",
      to: "/findings?type=MISSING_OWNER&status=OPEN",
    },
    {
      show: stale > 0,
      icon: Clock,
      tone: "teal",
      title: `${stale} stale table${stale === 1 ? "" : "s"}`,
      sub: "No recent updates. Consider deprecating them",
      to: "/findings?type=STALE_ENTITY&status=OPEN",
    },
  ].filter((i) => i.show);

  return (
    <div className="card ov-attention">
      <div className="eyebrow">Needs your attention</div>

      {o.pending_approvals > 0 ? (
        <Link to="/approvals" className="attn-primary">
          <div className="attn-primary-icon">
            <Inbox size={22} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="attn-primary-value">{o.pending_approvals}</div>
            <div className="attn-primary-label">AI recommendations awaiting your review</div>
          </div>
          <span className="btn btn-primary btn-sm">
            Review <ArrowRight size={15} />
          </span>
        </Link>
      ) : (
        <div className="attn-primary attn-zero">
          <CheckCircle2 size={22} color="var(--green)" />
          <div>
            <div style={{ fontWeight: 700 }}>Inbox zero</div>
            <div className="muted" style={{ fontSize: 12.5 }}>
              Nothing waiting for approval.
            </div>
          </div>
        </div>
      )}

      {open.length > 0 && (
        <div className="attn-agent">
          <Bot size={18} color="var(--primary)" />
          <div style={{ flex: 1, minWidth: 0 }}>
            {progress ? (
              <>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  Agents investigating… {progress.done}/{progress.total}
                </div>
                <div className="progress-track" style={{ marginTop: 6 }}>
                  <div
                    className="progress-determinate"
                    style={{ width: `${(progress.done / progress.total) * 100}%` }}
                  />
                </div>
              </>
            ) : (
              <>
                <div style={{ fontWeight: 600, fontSize: 13 }}>
                  {open.length} gap{open.length === 1 ? "" : "s"} not yet investigated
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Agents gather evidence and draft a fix for each one.
                </div>
              </>
            )}
          </div>
          {progress ? (
            <button className="btn btn-sm" onClick={() => (cancelled.current = true)}>
              Stop
            </button>
          ) : (
            <button className="btn btn-sm" onClick={investigateAll}>
              <Sparkles size={15} /> Investigate all
            </button>
          )}
        </div>
      )}

      <div className="attn-list">
        {items.map((it) => (
          <Link key={it.to} to={it.to} className="attn-item">
            <span className={`attn-icon tone-${it.tone}`}>
              <it.icon size={16} />
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>
              <span className="attn-title">{it.title}</span>
              <span className="attn-sub">{it.sub}</span>
            </span>
            <ChevronRight size={16} className="muted" />
          </Link>
        ))}
        {items.length === 0 && open.length === 0 && o.pending_approvals === 0 && (
          <div className="muted" style={{ fontSize: 13, padding: "8px 2px" }}>
            All clear. Run a scan to look for new gaps.
          </div>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- Pipeline */

function Pipeline({ o, findings }: { o: OverviewStats; findings: Finding[] }) {
  const steps = [
    {
      icon: Radar,
      title: "Detect",
      value: findings.length || o.open_findings,
      unit: "gaps found",
      sub: "Rule-based scans of the catalog",
      to: "/findings",
    },
    {
      icon: Bot,
      title: "Investigate",
      value: o.agent_runs,
      unit: "agent runs",
      sub: "Agents gather evidence",
      to: "/agents",
    },
    {
      icon: Lightbulb,
      title: "Recommend",
      value: o.recommendations_total,
      unit: "suggestions",
      sub: "Scored for confidence",
      to: "/recommendations",
    },
    {
      icon: Inbox,
      title: "Review",
      value: o.pending_approvals,
      unit: "awaiting you",
      sub: "Policy decides what needs a human",
      to: "/approvals",
      highlight: o.pending_approvals > 0,
    },
    {
      icon: CheckCircle2,
      title: "Apply",
      value: o.auto_resolved,
      unit: "applied",
      sub: "Written to OpenMetadata and audited",
      to: "/changes",
    },
  ];

  return (
    <div className="card ov-pipeline">
      <div className="card-header" style={{ marginBottom: 16 }}>
        <div>
          <div className="card-title">How MetaLens keeps your metadata healthy</div>
          <div className="card-sub">
            The AI makes the recommendations. The platform and your approval decide what gets applied.
          </div>
        </div>
      </div>
      <div className="pipe">
        {steps.map((s, i) => (
          <div key={s.title} className="pipe-cell">
            <Link to={s.to} className={`pipe-step${s.highlight ? " pipe-hl" : ""}`}>
              <div className="pipe-head">
                <span className="pipe-num">{i + 1}</span>
                <s.icon size={16} />
                <span>{s.title}</span>
              </div>
              <div className="pipe-value">{s.value.toLocaleString()}</div>
              <div className="pipe-unit">{s.unit}</div>
              <div className="pipe-sub">{s.sub}</div>
            </Link>
            {i < steps.length - 1 && (
              <ChevronRight className="pipe-arrow" size={18} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- Domains */

function DomainCoverage({ o }: { o: OverviewStats }) {
  const rows = useMemo(
    () =>
      o.domains
        .filter((d) => d.tables > 0)
        .map((d) => {
          const gaps = d.missing_owner + d.missing_description;
          return { ...d, gaps, coverage: 1 - gaps / (2 * d.tables) };
        })
        .sort((a, b) => a.coverage - b.coverage),
    [o.domains]
  );

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Coverage by domain</div>
          <div className="card-sub">Ownership and descriptions at the table level</div>
        </div>
      </div>
      {rows.length === 0 ? (
        <div className="muted">No domains yet.</div>
      ) : (
        <div className="dim-list" style={{ marginTop: 0 }}>
          {rows.map((d) => (
            <Link
              key={d.name}
              to={`/findings?domain=${encodeURIComponent(d.name)}`}
              className="dim-row"
            >
              <span className="dim-label">
                {d.display_name || d.name}
                <span className="muted" style={{ fontWeight: 400 }}>
                  {" "}
                  · {d.tables}
                </span>
              </span>
              <span className="dim-track">
                <span
                  className={`dim-fill dim-${tone(d.coverage)}`}
                  style={{ width: `${d.coverage * 100}%` }}
                />
              </span>
              <span className="dim-value">
                {d.gaps === 0 ? "✓" : `${d.gaps} gap${d.gaps === 1 ? "" : "s"}`}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- Activity */

function activityIcon(action: string) {
  if (action.includes("REJECT")) return { Icon: XCircle, tone: "red" };
  if (action.includes("APPLY") || action.includes("APPROVE"))
    return { Icon: CheckCircle2, tone: "green" };
  if (action.includes("SCAN") || action.includes("INGEST")) return { Icon: Radar, tone: "teal" };
  return { Icon: Sparkles, tone: "purple" };
}

function RecentActivity({ o }: { o: OverviewStats }) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Recent activity</div>
          <div className="card-sub">The latest decisions and system events</div>
        </div>
        <Link to="/activity" className="btn btn-sm" style={{ marginLeft: "auto" }}>
          View all
        </Link>
      </div>
      {o.recent_actions.length === 0 ? (
        <div className="muted">No activity yet.</div>
      ) : (
        <ul className="feed">
          {o.recent_actions.slice(0, 7).map((a) => {
            const { Icon, tone: t } = activityIcon(a.action);
            return (
              <li key={a.id} className="feed-item">
                <span className={`attn-icon tone-${t}`}>
                  <Icon size={15} />
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="feed-title">
                    {humanAction(a.action)}
                    {a.field && <span className="muted"> · {findingLabel(a.field)}</span>}
                  </div>
                  {a.entity && (
                    <div className="feed-entity">
                      <EntityName fqn={a.entity} />
                    </div>
                  )}
                </div>
                <span className="feed-time">
                  {a.actor !== "system" && <span>{a.actor} · </span>}
                  {relTime(a.timestamp)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
