import { useMemo } from "react";
import { Inbox } from "lucide-react";
import { api } from "../api";
import RecommendationCard from "../components/RecommendationCard";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";
import type { Finding } from "../types";

export default function Approvals() {
  const { data, loading, error, reload } = useAsync(
    () => api.recommendations({ status: "PENDING" }),
    []
  );
  const { data: findings } = useAsync(() => api.findings(), []);

  const entityMap = useMemo(() => {
    const m = new Map<string, string>();
    (findings ?? []).forEach((f: Finding) => m.set(f.id, f.entity));
    return m;
  }, [findings]);

  if (loading && !data) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const pending = data ?? [];

  if (pending.length === 0) {
    return (
      <EmptyState text="Inbox zero — no recommendations awaiting approval." />
    );
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, padding: "14px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Inbox size={18} color="#7b5fc7" />
          <div>
            <div style={{ fontWeight: 700 }}>{pending.length} awaiting review</div>
            <div className="card-sub">
              Human-in-the-loop decisions. Changes are applied to the catalog
              only after approval.
            </div>
          </div>
        </div>
      </div>

      {pending.map((r) => (
        <RecommendationCard
          key={r.id}
          recommendation={r}
          entity={entityMap.get(r.finding_id) ?? r.finding_id}
          onChanged={reload}
        />
      ))}
    </div>
  );
}
