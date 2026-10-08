import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    // Do not flip `loading` back to true on reload — only the initial load
    // shows a spinner, so in-place refreshes keep the component tree mounted
    // (fold/expand state is preserved). Returns the promise so callers can
    // await the refresh.
    setError(null);
    return fn()
      .then(setData)
      .catch((e) => setError(e?.message ?? String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload };
}
