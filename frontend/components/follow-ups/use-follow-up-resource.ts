"use client";
import { useEffect, useState } from "react";

/** Retain the last successful response on refresh failures, never across query changes. */
export function useFollowUpResource<T>(
  key: string,
  revision: number,
  fetcher: (signal: AbortSignal) => Promise<T>,
  report: (caught: unknown) => string,
) {
  const [snapshot, setSnapshot] = useState<{ key: string; data: T } | null>(
    null,
  );
  const [state, setState] = useState<{
    key: string;
    loading: boolean;
    error: string;
  }>({ key, loading: !!key, error: "" });
  useEffect(() => {
    if (!key) return;
    const controller = new AbortController();
    setState({ key, loading: true, error: "" });
    void fetcher(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setSnapshot({ key, data });
      })
      .catch((caught) => {
        if (!controller.signal.aborted)
          setState({ key, loading: false, error: report(caught) });
      })
      .finally(() => {
        if (!controller.signal.aborted)
          setState((current) => ({ ...current, loading: false }));
      });
    return () => controller.abort();
    // The key contains every query input. Avoid reloading for inline function identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, revision]);
  return {
    data: snapshot?.key === key ? snapshot.data : null,
    loading: !!key && (state.key !== key || state.loading),
    error: state.key === key ? state.error : "",
  };
}
