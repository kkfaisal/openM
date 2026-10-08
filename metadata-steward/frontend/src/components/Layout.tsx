import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Bot,
  Cable,
  ChevronDown,
  ChevronRight,
  Database,
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

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/findings", label: "Findings", icon: SearchCheck },
  { to: "/recommendations", label: "Recommendations", icon: Lightbulb },
  { to: "/approvals", label: "Approvals", icon: Inbox },
  { to: "/sources", label: "Metadata Ingestions", icon: Cable },
  { to: "/connections", label: "Metadata Tools", icon: Plug },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/history", label: "Generation Log", icon: History },
  { to: "/changes", label: "Changes", icon: Workflow },
  { to: "/policies", label: "Policies", icon: ShieldCheck },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
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
  "/agents": { title: "Agent Runs", sub: "Observable agent executions" },
  "/history": { title: "Generation Log", sub: "History of AI generations" },
  "/changes": { title: "Changes", sub: "Applied catalog writes with rollback" },
  "/policies": { title: "Policies", sub: "Deterministic guardrails for actions" },
  "/activity": { title: "Activity", sub: "Complete audit trail" },
  "/settings": { title: "Settings", sub: "System configuration" },
  "/catalog": { title: "Catalog", sub: "The metadata system of record" },
};

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [pending, setPending] = useState<number | null>(null);
  const [scanning, setScanning] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [openDs, setOpenDs] = useState<string | null>(null);

  useEffect(() => {
    api
      .overview()
      .then((o) => setPending(o.pending_approvals))
      .catch(() => setPending(null));
    api
      .datasets()
      .then(setDatasets)
      .catch(() => setDatasets([]));
  }, [location.pathname]);

  const meta =
    TITLES[location.pathname] ??
    (location.pathname.startsWith("/sources/")
      ? { title: "Source Detail", sub: "Connected metadata channel" }
      : TITLES["/"]);

  async function runScan() {
    setScanning(true);
    try {
      await api.scan();
      setPending((p) => (p === null ? p : p));
      // refresh badge
      const o = await api.overview();
      setPending(o.pending_approvals);
    } catch {
      /* ignore */
    } finally {
      setScanning(false);
      navigate(0); // refresh current view
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
          <div className="nav-label">Workspace</div>
          {NAV.map((item) => (
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
            </NavLink>
          ))}
          <div className="nav-label">System of Record</div>
          <NavLink
            to="/catalog"
            className={({ isActive }) =>
              `nav-item${isActive ? " active" : ""}`
            }
          >
            <Database />
            <span>Catalog</span>
          </NavLink>

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
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

