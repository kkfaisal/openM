import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  BookOpen,
  Bot,
  Cable,
  ChevronDown,
  ChevronRight,
  Database,
  Gauge,
  History,
  Inbox,
  LayoutDashboard,
  Lightbulb,
  Play,
  Plug,
  SearchCheck,
  Settings,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { api } from "../api";
import type { Dataset } from "../types";
import { useToast } from "./Toast";

type NavEntry = { to: string; label: string; icon: typeof Activity; end?: boolean };

const NAV_GROUPS: { label: string | null; items: NavEntry[] }[] = [
  {
    label: null,
    items: [{ to: "/", label: "Overview", icon: LayoutDashboard, end: true }],
  },
  {
    label: "Review",
    items: [
      { to: "/approvals", label: "Approvals", icon: Inbox },
      { to: "/findings", label: "Findings", icon: SearchCheck },
      { to: "/recommendations", label: "Recommendations", icon: Lightbulb },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { to: "/sources", label: "Metadata Ingestions", icon: Cable },
      { to: "/knowledge", label: "Knowledge Base", icon: BookOpen },
      { to: "/catalog", label: "Catalog", icon: Database },
      { to: "/connections", label: "Metadata Tools", icon: Plug },
    ],
  },
  {
    label: "Audit trail",
    items: [
      { to: "/changes", label: "Changes", icon: Workflow },
      { to: "/quality", label: "Agent Quality", icon: Gauge },
      { to: "/agents", label: "Agent Runs", icon: Bot },
      { to: "/history", label: "Generation Log", icon: History },
      { to: "/activity", label: "Activity", icon: Activity },
    ],
  },
  {
    label: "Govern",
    items: [
      { to: "/policies", label: "Policies", icon: ShieldCheck },
      { to: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const TITLES: Record<string, { title: string; sub: string }> = {
  "/": {
    title: "Overview",
    sub: "Your AI metadata operations at a glance",
  },
  "/findings": { title: "Findings", sub: "Detected metadata gaps and issues" },
  "/recommendations": {
    title: "Recommendations",
    sub: "Proposed metadata corrections with evidence",
  },
  "/approvals": {
    title: "Approval Inbox",
    sub: "Human-in-the-loop decisions awaiting review",
  },
  "/sources": {
    title: "Metadata Ingestions",
    sub: "Ingest Slack, Teams, files and webhooks; extract with AI",
  },
  "/connections": {
    title: "Metadata Tools",
    sub: "OpenMetadata, Amundsen, DataHub and more",
  },
  "/agents": { title: "Agent Runs", sub: "Every agent investigation, step by step" },
  "/history": { title: "Generation Log", sub: "History of AI generations" },
  "/changes": { title: "Changes", sub: "Applied catalog writes with rollback" },
  "/policies": { title: "Policies", sub: "Deterministic guardrails for actions" },
  "/activity": { title: "Activity", sub: "Complete audit trail" },
  "/settings": { title: "Settings", sub: "System configuration" },
  "/catalog": { title: "Catalog", sub: "The metadata system of record" },
  "/quality": {
    title: "Agent Quality",
    sub: "Monitoring and evaluation of the AI agents, traced in MLflow",
  },
  "/knowledge": {
    title: "Knowledge Base",
    sub: "Search, browse and ask questions over everything you ingested",
  },
};

export default function Layout() {
  const location = useLocation();
  const toast = useToast();
  const [pending, setPending] = useState<number | null>(null);
  const [openFindings, setOpenFindings] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [openDs, setOpenDs] = useState<string | null>(null);

  useEffect(() => {
    api
      .overview()
      .then((o) => {
        setPending(o.pending_approvals);
        setOpenFindings(o.open_findings);
      })
      .catch(() => setPending(null));
    api
      .datasets()
      .then(setDatasets)
      .catch(() => setDatasets([]));
  }, [location.pathname, refreshKey]);

  // Cards elsewhere fire this after a decision so the nav badges stay current.
  useEffect(() => {
    function refreshCounts() {
      api
        .overview()
        .then((o) => {
          setPending(o.pending_approvals);
          setOpenFindings(o.open_findings);
        })
        .catch(() => {});
    }
    window.addEventListener("metalens:refresh-counts", refreshCounts);
    return () => window.removeEventListener("metalens:refresh-counts", refreshCounts);
  }, []);

  const meta =
    TITLES[location.pathname] ??
    (location.pathname.startsWith("/sources/")
      ? { title: "Source Detail", sub: "Connected metadata channel" }
      : location.pathname.startsWith("/findings/")
      ? { title: "Finding", sub: "Evidence, recommendations and decision history" }
      : TITLES["/"]);

  async function runScan() {
    setScanning(true);
    try {
      const res = await api.scan();
      const n = res.findings_created;
      toast(
        "success",
        "Scan complete",
        n > 0
          ? `${n} new finding${n === 1 ? "" : "s"} detected — agents can now investigate.`
          : "No new gaps found. Your catalog is up to date."
      );
    } catch (e) {
      toast("error", "Scan failed", e instanceof Error ? e.message : String(e));
    } finally {
      setScanning(false);
      // Remount the current page so it refetches, without a full reload.
      setRefreshKey((k) => k + 1);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={20} />
          </div>
          <div>
            <div className="brand-title">MetaLens</div>
            <div className="brand-sub">AI Metadata Ops</div>
          </div>
        </div>

        <nav className="nav">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} className="nav-group">
              {group.label && <div className="nav-label">{group.label}</div>}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `nav-item${isActive ? " active" : ""}`
                  }
                >
                  <item.icon />
                  <span>{item.label}</span>
                  {item.to === "/approvals" && pending ? (
                    <span className="nav-badge">{pending}</span>
                  ) : null}
                  {item.to === "/findings" && openFindings ? (
                    <span className="nav-badge nav-badge-soft">{openFindings}</span>
                  ) : null}
                </NavLink>
              ))}
            </div>
          ))}

          <div className="nav-label">Datasets</div>
          {datasets.length === 0 ? (
            <div className="muted" style={{ padding: "2px 10px 8px", fontSize: 12 }}>
              No datasets synced
            </div>
          ) : (
            <div className="hier">
              {datasets.map((ds) => {
                const total = ds.schemas.reduce((n, s) => n + s.tables.length, 0);
                const open = openDs === ds.key;
                return (
                  <div key={ds.key}>
                    <div
                      className="hier-dataset"
                      onClick={() => setOpenDs(open ? null : ds.key)}
                    >
                      {open ? <ChevronDown /> : <ChevronRight />}
                      <span>{ds.database}</span>
                      <span className="hier-count">{total}</span>
                    </div>
                    {open &&
                      ds.schemas.map((s) => (
                        <div key={s.name}>
                          <div className="hier-schema">{s.name}</div>
                          {s.tables.map((t) => (
                            <NavLink key={t.fqn} to="/catalog" className="hier-table">
                              {t.name}
                            </NavLink>
                          ))}
                        </div>
                      ))}
                  </div>
                );
              })}
            </div>
          )}
        </nav>

        <div className="sidebar-foot">
          <span className="dot" />
          Demo catalog connected
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div>
            <h1>{meta.title}</h1>
            <div className="subtitle">{meta.sub}</div>
          </div>
          <div className="topbar-actions">
            <button className="btn btn-primary" onClick={runScan} disabled={scanning}>
              <Play size={16} />
              {scanning ? "Scanning…" : "Run scan"}
            </button>
          </div>
          {scanning && (
            <div className="topbar-progress">
              <div className="progress-fill" />
            </div>
          )}
        </header>
        <main className="content">
          <Outlet key={refreshKey} />
        </main>
      </div>
    </div>
  );
}

