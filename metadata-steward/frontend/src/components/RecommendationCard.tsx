import { useEffect, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronRight,
  History,
  MessageSquare,
  Pencil,
  RotateCcw,
  X,
} from "lucide-react";
import { api } from "../api";
import type { Recommendation } from "../types";
import { similarity, wordDiff } from "../lib/diff";
import { errorDetail, fieldLabel, fmtDate } from "../lib/format";
import { ActionModeBadge, EntityName, FieldBadge, StatusBadge } from "./ui";
import { useToast } from "./Toast";

function confTone(v: number) {
  return v >= 0.9 ? "high" : v >= 0.75 ? "mid" : "low";
}

export function ConfidencePill({ value }: { value: number }) {
  const p = Math.round(value * 100);
  return (
    <span className={`conf-pill conf-${confTone(value)}`} title="Confidence: agent score combined with evidence quality">
      <span className="conf-pill-dot" />
      {p}% confident
    </span>
  );
}

export default function RecommendationCard({
  recommendation,
  history,
  entity,
  onChanged,
  onDecided,
  active = false,
  onActivate,
  defaultExpanded,
}: {
  recommendation: Recommendation;
  history?: Recommendation[];
  entity: string;
  onChanged: () => void;
  onDecided?: () => void;
  /** Keyboard focus in a review queue: enables A / R / E shortcuts. */
  active?: boolean;
  onActivate?: () => void;
  defaultExpanded?: boolean;
}) {
  const toast = useToast();
  const rec = recommendation;
  const pending = rec.status === "PENDING";
  const [busy, setBusy] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);
  const [modified, setModified] = useState(rec.new_value ?? "");
  const [editing, setEditing] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded ?? !!history);
  const [leaving, setLeaving] = useState<null | "approved" | "rejected">(null);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const edited = modified !== (rec.new_value ?? "");

  async function act(kind: "approve" | "reject") {
    if (busy) return;
    setBusy(kind);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        comment,
        decided_by: "Demo Steward",
        modified_value: modified,
      };
      if (kind === "approve") await api.recommendApprove(rec.id, body);
      else await api.recommendReject(rec.id, body);
      const tail = entity.split(".").slice(-2).join(".");
      toast(
        kind === "approve" ? "success" : "info",
        kind === "approve" ? "Approved and applied to the catalog" : "Recommendation rejected",
        `${fieldLabel(rec.field)} · ${tail}${edited && kind === "approve" ? " (with your edits)" : ""}`
      );
      window.dispatchEvent(new Event("metalens:refresh-counts"));
      setLeaving(kind === "approve" ? "approved" : "rejected");
      // Let the exit animation play before the parent removes the card.
      setTimeout(() => {
        onChanged();
        onDecided?.();
      }, 320);
    } catch (e) {
      setError(errorDetail(e));
      toast("error", `Could not ${kind}`, errorDetail(e));
      setBusy(null);
    }
  }

  async function useVersion(id: string) {
    setBusy("select");
    setError(null);
    try {
      await api.recommendSelect(id);
      onChanged();
      onDecided?.();
    } catch (e) {
      setError(errorDetail(e));
    } finally {
      setBusy(null);
    }
  }

  // Keyboard shortcuts when this card is the active one in a queue.
  useEffect(() => {
    if (!active || !pending) return;
    rootRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || e.metaKey || e.ctrlKey) {
        if (e.key === "Escape") (t as HTMLElement).blur();
        return;
      }
      if (e.key === "a") {
        e.preventDefault();
        act("approve");
      } else if (e.key === "r") {
        e.preventDefault();
        act("reject");
      } else if (e.key === "e") {
        e.preventDefault();
        setEditing(true);
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setExpanded((x) => !x);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, pending, modified, comment, busy]);

  const historySorted = [...(history ?? [])].sort((a, b) => b.version - a.version);
  const shownValue = pending ? modified : rec.new_value ?? "";
  const rawDiff = rec.old_value && !editing ? wordDiff(rec.old_value, shownValue) : null;
  // Mostly-rewritten text reads better as before/after than as an inline diff.
  const diff = rawDiff && similarity(rawDiff) >= 0.5 ? rawDiff : null;
  const beforeAfter = rawDiff && !diff;

  return (
    <div
      ref={rootRef}
      className={`rec-card${active ? " rec-active" : ""}${leaving ? ` rec-leaving rec-${leaving}` : ""}`}
      onMouseDown={onActivate}
    >
      <div className="rec-head">
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="rec-meta">
            <FieldBadge field={fieldLabel(rec.field)} />
            {rec.version > 1 && <span className="badge mode-INFORMATION_ONLY">v{rec.version}</span>}
            {!pending && <StatusBadge status={rec.status} />}
            {rec.action_mode !== "REQUIRE_APPROVAL" && <ActionModeBadge mode={rec.action_mode} />}
          </div>
          <div className="rec-entity">
            <EntityName fqn={entity} />
          </div>
        </div>
        <ConfidencePill value={rec.confidence} />
      </div>

      {/* Proposed change */}
      <div className="rec-change">
        {editing && pending ? (
          <>
            <div className="rec-change-label">Your edit</div>
            <textarea
              className="textarea"
              autoFocus
              style={{ minHeight: 76, fontSize: 13.5, background: "#fff" }}
              value={modified}
              onChange={(e) => setModified(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setEditing(false);
              }}
            />
          </>
        ) : beforeAfter ? (
          <div className="rec-ba">
            <div className="rec-change-label">Before</div>
            <div className="rec-before">{rec.old_value}</div>
            <div className="rec-change-label" style={{ marginTop: 10 }}>
              After
              {edited && <span className="rec-edited">edited</span>}
            </div>
            <div className="rec-suggested">{shownValue}</div>
          </div>
        ) : diff ? (
          <>
            <div className="rec-change-label">
              Proposed change
              {edited && <span className="rec-edited">edited</span>}
            </div>
            <div className="rec-diff">
              {diff.map((p, i) => (
                <span key={i} className={`diff-${p.kind}`}>
                  {p.text}
                </span>
              ))}
            </div>
          </>
        ) : (
          <>
            <div className="rec-change-label">
              {rec.old_value ? "Proposed value" : "Currently empty · suggested"}
              {edited && <span className="rec-edited">edited</span>}
            </div>
            <div className="rec-suggested">{shownValue || <em className="muted">(empty)</em>}</div>
          </>
        )}
      </div>

      {/* Why — reasoning + evidence */}
      {(rec.reasoning_summary || rec.evidence.length > 0 || historySorted.length > 0) && (
        <button className="rec-why-toggle" onClick={() => setExpanded((x) => !x)}>
          {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          Why this suggestion?
          {rec.evidence.length > 0 && (
            <span className="rec-why-count">
              {rec.evidence.length} evidence item{rec.evidence.length === 1 ? "" : "s"}
            </span>
          )}
          {historySorted.length > 0 && (
            <span className="rec-why-count">{historySorted.length} versions</span>
          )}
        </button>
      )}

      {expanded && (
        <div className="rec-why">
          {rec.reasoning_summary && <p className="rec-reasoning">{rec.reasoning_summary}</p>}
          {rec.evidence.length > 0 && (
            <ul className="evidence-list">
              {rec.evidence.map((ev) => (
                <li key={ev.id}>
                  <span className="evidence-type">{ev.type.replace(/_/g, " ")}</span>
                  <span style={{ minWidth: 0, overflowWrap: "anywhere" }}>{ev.value}</span>
                </li>
              ))}
            </ul>
          )}

          {historySorted.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div
                className="flag"
                style={{ marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}
              >
                <History size={13} /> VERSION HISTORY
              </div>
              <ul className="evidence-list">
                {historySorted.map((h) => (
                  <li key={h.id} style={{ alignItems: "flex-start" }}>
                    <span className="evidence-type">
                      v{h.version} · {h.status.replace(/_/g, " ")}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5 }}>{h.new_value}</div>
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        {fmtDate(h.created_at)}
                        {h.context_snapshot ? (
                          <>
                            {" "}
                            · context: {(h.context_snapshot || "").slice(0, 90)}
                            {h.context_snapshot.length > 90 ? "…" : ""}
                          </>
                        ) : null}
                      </div>
                    </div>
                    {pending && h.status === "SUPERSEDED" && (
                      <button
                        className="btn btn-sm"
                        disabled={busy !== null}
                        onClick={() => useVersion(h.id)}
                      >
                        Use this version
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {pending && (
        <div className="rec-actions">
          {showComment && (
            <input
              className="input"
              autoFocus
              placeholder="Add a note for the audit trail (optional)"
              style={{ width: "100%", marginBottom: 10 }}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          )}
          {error && <div className="rec-error">{error}</div>}
          <div className="rec-buttons">
            <button
              className="btn btn-success btn-sm"
              disabled={busy !== null}
              onClick={() => act("approve")}
            >
              <Check size={15} /> {busy === "approve" ? "Applying…" : "Approve & apply"}
              {active && <kbd>A</kbd>}
            </button>
            <button
              className="btn btn-danger btn-sm"
              disabled={busy !== null}
              onClick={() => act("reject")}
            >
              <X size={15} /> Reject
              {active && <kbd>R</kbd>}
            </button>
            {editing ? (
              <button className="btn btn-sm" onClick={() => setEditing(false)}>
                <Check size={15} /> Done editing
              </button>
            ) : (
              <button className="btn btn-sm" disabled={busy !== null} onClick={() => setEditing(true)}>
                <Pencil size={14} /> Edit
                {active && <kbd>E</kbd>}
              </button>
            )}
            {edited && (
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => setModified(rec.new_value ?? "")}
                title="Discard your edits"
              >
                <RotateCcw size={14} /> Reset
              </button>
            )}
            <button
              className="btn btn-sm btn-ghost"
              style={{ marginLeft: "auto" }}
              onClick={() => setShowComment((x) => !x)}
            >
              <MessageSquare size={14} /> {showComment ? "Hide note" : "Add note"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
