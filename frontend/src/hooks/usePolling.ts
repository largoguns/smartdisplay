import { useEffect, useState } from 'react';

const RETRY_WITHOUT_DATA_MS = 5_000;

export interface PollState<T> {
  data: T | null;
  /** Último error de red/HTTP; los datos previos se conservan. */
  error: string | null;
}

export function usePolling<T>(url: string, intervalMs: number): PollState<T> {
  const [state, setState] = useState<PollState<T>>({ data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let controller: AbortController | undefined;
    let hasData = false;

    const tick = async () => {
      controller = new AbortController();
      let failed = false;
      try {
        const res = await fetch(url, { signal: controller.signal, cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as T;
        hasData = true;
        if (!cancelled) setState({ data, error: null });
      } catch (err) {
        failed = true;
        if (cancelled) return;
        const error = err instanceof Error ? err.message : String(err);
        setState((prev) => ({ data: prev.data, error }));
      } finally {
        // Sin datos que mostrar (p. ej. backend reiniciándose) se reintenta pronto.
        const delay = failed && !hasData ? Math.min(intervalMs, RETRY_WITHOUT_DATA_MS) : intervalMs;
        if (!cancelled) timer = window.setTimeout(tick, delay);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      controller?.abort();
      window.clearTimeout(timer);
    };
  }, [url, intervalMs]);

  return state;
}

/** Hay que avisar de datos antiguos si el backend lo indica o si no responde. */
export function isStale(state: PollState<{ status: string }>): boolean {
  return state.error !== null || state.data?.status === 'stale';
}
