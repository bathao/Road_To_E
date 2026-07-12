// Shared data-fetching hooks. Every tab used to hand-roll the same
// useState(data) + useState(error) + useEffect(load) scaffolding (13+ copies,
// each subtly different); these two hooks replace them:
//
// - useLoad(fn, deps): read path. Keeps { data, error, loading, reload }, guards
//   against out-of-order responses (rapid Prev/Prev clicks) with a sequence
//   counter, and never sets state after unmount.
// - useMutate(): write path. Wraps a mutation so a rejected promise becomes a
//   visible error instead of a silent unhandled rejection.
import { useCallback, useEffect, useRef, useState } from "react";

export function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function useLoad<T>(
  fn: () => Promise<T>,
  deps: readonly unknown[]
): {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  /** Replace the loaded data locally (e.g. with a mutation's response). */
  setData: (d: T | null) => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Bumping `tick` re-runs the effect; `seq` drops stale responses.
  const [tick, setTick] = useState(0);
  const seq = useRef(0);

  useEffect(() => {
    const mySeq = ++seq.current;
    let alive = true;
    setLoading(true);
    fn().then(
      (d) => {
        if (!alive || mySeq !== seq.current) return; // stale response
        setData(d);
        setError(null);
        setLoading(false);
      },
      (e) => {
        if (!alive || mySeq !== seq.current) return;
        setError(errMsg(e));
        setLoading(false);
      }
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, setData };
}

export function useMutate(): {
  /** Run a mutation; returns its result, or undefined when it failed
   *  (the error is captured in `error` for the UI). */
  run: <T>(fn: () => Promise<T>) => Promise<T | undefined>;
  error: string | null;
  busy: boolean;
  clearError: () => void;
} {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = useCallback(async <T,>(fn: () => Promise<T>) => {
    setBusy(true);
    try {
      const out = await fn();
      setError(null);
      return out;
    } catch (e) {
      setError(errMsg(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);
  return { run, error, busy, clearError };
}
