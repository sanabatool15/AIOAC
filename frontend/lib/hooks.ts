"use client";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { getRealUser, getSessionSnapshot, subscribeSession, type SessionUser } from "./session";

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

// "unknown" on the server and during hydration, then "in" | "out".
export function useSession() {
  return useSyncExternalStore(
    subscribeSession,
    getSessionSnapshot,
    () => "unknown" as const,
  );
}

// The signed-in user in real mode (null while unknown or signed out).
export function useRealUser(): SessionUser | null {
  return useSyncExternalStore(subscribeSession, getRealUser, () => null);
}
