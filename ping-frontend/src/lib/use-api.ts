"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

interface State<T> {
  data: T | undefined;
  error: ApiError | null;
  loading: boolean;
}

/**
 * Load data on mount and whenever `key` changes. `reload()` refetches without
 * clearing what is shown; `pollMs` refetches on an interval while it is set.
 * A 401 anywhere sends the user to the login page.
 */
export function useApi<T>(fetcher: () => Promise<T>, key: unknown[], pollMs?: number) {
  const [state, setState] = useState<State<T>>({ data: undefined, error: null, loading: true });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const seq = useRef(0);

  const run = useCallback(async () => {
    const id = ++seq.current;
    try {
      const data = await fetcherRef.current();
      if (id === seq.current) setState({ data, error: null, loading: false });
    } catch (e) {
      const error = e instanceof ApiError ? e : new ApiError(String(e), 0, "error");
      if (error.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (id === seq.current) setState((s) => ({ ...s, error, loading: false }));
    }
  }, []);

  const keyString = JSON.stringify(key);
  useEffect(() => {
    setState((s) => ({ ...s, loading: true }));
    run();
  }, [keyString, run]);

  useEffect(() => {
    if (!pollMs) return;
    // Don't poll a background tab; catch up as soon as it is visible again.
    const tick = () => {
      if (!document.hidden) run();
    };
    const t = setInterval(tick, pollMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [pollMs, run]);

  const setData = useCallback((update: T | ((prev: T | undefined) => T)) => {
    setState((s) => ({
      ...s,
      data: typeof update === "function" ? (update as (p: T | undefined) => T)(s.data) : update,
    }));
  }, []);

  return { ...state, reload: run, setData };
}

/** Run a mutation with a busy flag and a user-facing error message. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <R,>(fn: () => Promise<R>): Promise<R | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        window.location.href = "/login";
        return undefined;
      }
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, setError, run };
}
