import { api } from "../api";
import DatasetCard from "../components/DatasetCard";
import { EmptyState, Loading } from "../components/ui";
import { useAsync } from "../lib/useAsync";

export default function Catalog() {
  const { data, loading, error, reload } = useAsync(() => api.datasets(), []);

  if (loading) return <Loading />;
  if (error) return <EmptyState text={error} />;

  const datasets = data ?? [];

  return (
    <div>
      {datasets.length === 0 ? (
        <EmptyState text="No datasets synced yet." />
      ) : (
        datasets.map((ds) => (
          <DatasetCard key={ds.key} dataset={ds} onSaved={reload} />
        ))
      )}
    </div>
  );
}
