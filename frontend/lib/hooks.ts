"use client";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { getSessionSnapshot, subscribeSession } from "./session";

// Tiny data hook: loading / error / data + retry. Remount (key) to reset on id change.
export function useAsync<T>(fn: () => Promise<T>, key?: unknown) {
  const [state, setState] = useState<{
    data?: T;
    error?: Error;
    loading: boolean;
  }>({ loading: true });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    fn()
      .then((data) => alive && setState({ data, loading: false }))
      .catch((error: Error) => alive && setState({ error, loading: false }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, key]);

  const retry = useCallback(() => {
    setState((s) => ({ data: s.data, loading: true }));
    setTick((t) => t + 1);
  }, []);

  return { ...state, retry };
}

// localStorage-backed state. Always renders `initial` first (no hydration mismatch), then loads saved value.
export function usePersistedState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (raw !== null) setValue(JSON.parse(raw) as T);
    } catch {
      /* storage unavailable: keep initial */
    }
  }, [key]);

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved =
          typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        try {
          localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          /* ignore */
        }
        return resolved;
      });
    },
    [key],
  );

  return [value, set] as const;
}

// "unknown" on the server and during hydration, then "in" | "out".
export function useSession() {
  return useSyncExternalStore(
    subscribeSession,
    getSessionSnapshot,
    () => "unknown" as const,
  );
}
