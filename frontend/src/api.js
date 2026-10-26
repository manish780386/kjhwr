import { useEffect, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE || "";

async function get(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString();
  const res = await fetch(`${BASE}/api${path}${query ? `?${query}` : ""}`);
  if (!res.ok) {
    let message = res.statusText;
    try {
      message = (await res.json()).detail || message;
    } catch {
      /* body was not JSON */
    }
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  meta: () => get("/meta"),
  latest: (p) => get("/forecast/latest", p),
  metrics: (p) => get("/metrics", p),
  horizon: (p) => get("/horizon-metrics", p),
  refresh: () => fetch(`${BASE}/api/refresh`, { method: "POST" }),
};

/** Runs `fn` whenever `key` changes and exposes { data, error, loading }. */
export function useAsync(fn, key, enabled = true) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled });
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => !cancelled && setState({ data, error: null, loading: false }))
      .catch((error) => !cancelled && setState({ data: null, error, loading: false }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);
  return state;
}
