import { Layers } from "lucide-react";
import { api } from "../api";
import DatasetCard from "../components/DatasetCard";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";

export default function Overview() {
  const { data: datasets, loading, error, reload } = useAsync(
    () => api.datasets(),
    []
  );

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const ds = datasets ?? [];

  return (
    <div>
      <div
        className="section-title"
        style={{ marginTop: 0, display: "flex", alignItems: "center", gap: 10 }}
      >
        <Layers size={22} color="#7b5fc7" />
        Data Sets
        <span className="muted" style={{ fontWeight: 400, fontSize: 14 }}>
          — {ds.length} total
        </span>
      </div>

      {ds.length === 0 ? (
        <EmptyState text="No datasets synced yet." />
      ) : (
        ds.map((d) => <DatasetCard key={d.key} dataset={d} onSaved={reload} />)
      )}
    </div>
  );
}
