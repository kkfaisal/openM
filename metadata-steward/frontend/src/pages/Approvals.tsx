import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCheck, Inbox, Keyboard, PartyPopper } from "lucide-react";
import { api } from "../api";
import RecommendationCard from "../components/RecommendationCard";
import { useToast } from "../components/Toast";
import { EmptyState, Loading } from "../components/ui";
import { errorDetail, fieldLabel } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import type { Finding, Recommendation } from "../types";

const BULK_THRESHOLD = 0.95;

export default function Approvals() {
  const toast = useToast();
  const { data, loading, error } = useAsync(
    () => api.recommendations({ status: "PENDING" }),
    []
  );
  const { data: findings } = useAsync(() => api.findings(), []);

  // Decided cards are removed locally so the queue stays snappy.
  const [decided, setDecided] = useState<Set<string>>(new Set());
  const [field, setField] = useState<string>("");
  const [sort, setSort] = useState<"confidence" | "newest">("confidence");
  const [active, setActive] = useState(0);
  const [bulk, setBulk] = useState<null | "confirm" | { done: number; total: number }>(null);
  const [sessionCount, setSessionCount] = useState(0);

  const entityMap = useMemo(() => {
    const m = new Map<string, string>();
    (findings ?? []).forEach((f: Finding) => m.set(f.id, f.entity));
    return m;
  }, [findings]);

  const all = useMemo(
    () => (data ?? []).filter((r) => !decided.has(r.id)),
    [data, decided]
  );

  const fieldCounts = useMemo(() => {
    const c = new Map<string, number>();
    all.forEach((r) => c.set(r.field, (c.get(r.field) ?? 0) + 1));
    return [...c.entries()].sort((a, b) => b[1] - a[1]);
  }, [all]);

  const queue = useMemo(() => {
    const xs = all.filter((r) => !field || r.field === field);
    return [...xs].sort((a, b) =>
      sort === "confidence"
        ? b.confidence - a.confidence
        : b.created_at.localeCompare(a.created_at)
    );
  }, [all, field, sort]);

  const highConf = queue.filter((r) => r.confidence >= BULK_THRESHOLD);

  useEffect(() => {
    if (active >= queue.length) setActive(Math.max(0, queue.length - 1));
  }, [queue.length, active]);

  // J / K to move through the queue.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.tagName === "SELECT") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setActive((i) => Math.min(queue.length - 1, i + 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setActive((i) => Math.max(0, i - 1));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [queue.length]);

  function markDecided(id: string) {
    setDecided((s) => new Set(s).add(id));
    setSessionCount((n) => n + 1);
  }

  async function approveHighConfidence() {
    const items: Recommendation[] = [...highConf];
    let ok = 0;
    let firstError = "";
    setBulk({ done: 0, total: items.length });
    for (let i = 0; i < items.length; i++) {
      try {
        await api.recommendApprove(items[i].id, {
          comment: `Bulk-approved (confidence ≥ ${Math.round(BULK_THRESHOLD * 100)}%)`,
          decided_by: "Demo Steward",
          modified_value: items[i].new_value ?? "",
        });
        ok++;
        markDecided(items[i].id);
      } catch (e) {
        // Leave it in the queue for manual review.
        firstError ||= errorDetail(e);
      }
      setBulk({ done: i + 1, total: items.length });
    }
    setBulk(null);
    window.dispatchEvent(new Event("metalens:refresh-counts"));
    toast(
      ok === items.length ? "success" : "error",
      `Applied ${ok} of ${items.length} high-confidence recommendations`,
      ok === items.length
        ? "Every change was written to the catalog and audited."
        : `Failed ones stay in the queue. First error: ${firstError}`
    );
  }

  if (loading && !data) return <Loading />;
  if (error) return <EmptyState text={error} />;

  if (all.length === 0) {
    return (
      <div className="card inbox-zero">
        <div className="inbox-zero-icon">
          <PartyPopper size={30} />
        </div>
        <div className="inbox-zero-title">Inbox zero</div>
        <div className="muted" style={{ maxWidth: 420, margin: "0 auto" }}>
          {sessionCount > 0
            ? `You reviewed ${sessionCount} recommendation${sessionCount === 1 ? "" : "s"} this session. Every decision is recorded in the audit trail.`
            : "No recommendations are waiting for approval."}
        </div>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 18 }}>
          <Link to="/" className="btn btn-primary btn-sm">
            Back to overview
          </Link>
          <Link to="/changes" className="btn btn-sm">
            See applied changes
          </Link>
        </div>
      </div>
    );
  }

  const total = (data ?? []).length;
  const progressPct = total ? (decided.size / total) * 100 : 0;

  return (
    <div className="approvals">
      <div className="card approvals-head">
        <div className="approvals-head-top">
          <div className="attn-primary-icon" style={{ width: 40, height: 40 }}>
            <Inbox size={19} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 800, fontSize: 18 }}>
              {all.length} awaiting review
              {sessionCount > 0 && (
                <span className="muted" style={{ fontWeight: 500, fontSize: 13 }}>
                  {" "}
                  · {sessionCount} done this session
                </span>
              )}
            </div>
            <div className="card-sub">
              Policies flagged these for a human decision. Nothing reaches the catalog until you approve it.
            </div>
          </div>

          {highConf.length > 0 &&
            (bulk === null ? (
              <button className="btn btn-sm" onClick={() => setBulk("confirm")}>
                <CheckCheck size={15} /> Approve {highConf.length} at ≥{" "}
                {Math.round(BULK_THRESHOLD * 100)}% confidence
              </button>
            ) : bulk === "confirm" ? (
              <div className="bulk-confirm">
                <span>
                  Apply <strong>{highConf.length}</strong> changes?
                </span>
                <button className="btn btn-success btn-sm" onClick={approveHighConfidence}>
                  Yes, apply
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => setBulk(null)}>
                  Cancel
                </button>
              </div>
            ) : (
              <div className="bulk-confirm">
                <span>
                  Applying {bulk.done}/{bulk.total}…
                </span>
              </div>
            ))}
        </div>

        {decided.size > 0 && (
          <div className="progress-track" style={{ marginTop: 14, height: 6 }}>
            <div className="progress-determinate" style={{ width: `${progressPct}%` }} />
          </div>
        )}

        <div className="approvals-filters">
          <button
            className={`chip${field === "" ? " chip-on" : ""}`}
            onClick={() => setField("")}
          >
            All <span className="chip-count">{all.length}</span>
          </button>
          {fieldCounts.map(([f, n]) => (
            <button
              key={f}
              className={`chip${field === f ? " chip-on" : ""}`}
              onClick={() => setField(f)}
            >
              {fieldLabel(f)} <span className="chip-count">{n}</span>
            </button>
          ))}
          <select
            className="select"
            style={{ marginLeft: "auto" }}
            value={sort}
            onChange={(e) => setSort(e.target.value as "confidence" | "newest")}
          >
            <option value="confidence">Highest confidence first</option>
            <option value="newest">Newest first</option>
          </select>
        </div>
      </div>

      <div className="kbd-hint">
        <Keyboard size={14} />
        <span>
          <kbd>J</kbd>/<kbd>K</kbd> move · <kbd>A</kbd> approve · <kbd>R</kbd> reject ·{" "}
          <kbd>E</kbd> edit · <kbd>Enter</kbd> show evidence
        </span>
      </div>

      {queue.map((r, i) => (
        <RecommendationCard
          key={r.id}
          recommendation={r}
          entity={entityMap.get(r.finding_id) ?? r.finding_id}
          active={i === active}
          onActivate={() => setActive(i)}
          onChanged={() => markDecided(r.id)}
        />
      ))}

      {queue.length === 0 && (
        <EmptyState text="Nothing in this category. Pick another filter." />
      )}
    </div>
  );
}
