import { useCallback, useEffect, useRef, useState } from "react";

export interface Poll<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  refresh: () => void;
}

/**
 * Load now, then again every `intervalMs` (not at all if null), while the tab is visible. A new request never starts
 * before the last one has ended. The last good data stays on screen when a later request fails, with the error beside it.
 * Everything restarts when `deps` change.
 */
export function usePoll<T>(load: (signal: AbortSignal) => Promise<T>, intervalMs: number | null, deps: unknown[] = []): Poll<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const loader = useRef(load);
  loader.current = load;

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let first = true;

    const run = async () => {
      if (controller.signal.aborted) return;
      if (!document.hidden || first) {
        try {
          const result = await loader.current(controller.signal);
          if (controller.signal.aborted) return;
          setData(result);
          setError(undefined);
        } catch (e) {
          if (controller.signal.aborted || (e as Error).name === "AbortError") return;
          setError(e as Error);
        }
        first = false;
        setLoading(false);
      }
      if (intervalMs !== null && !controller.signal.aborted) timer = setTimeout(run, intervalMs);
    };
    setLoading(true);
    void run();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, tick, ...deps]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, refresh };
}
