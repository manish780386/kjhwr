import { useEffect, useState } from "react";
import { api, useAsync } from "./api.js";
import Controls from "./components/Controls.jsx";
import DayBrief from "./components/DayBrief.jsx";
import Accuracy from "./components/Accuracy.jsx";
import { stamp } from "./format.js";

function useMeta() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let timer;
    api
      .meta()
      .then((m) => {
        setMeta(m);
        setError(null);
        if (m.status === "loading" || m.status === "empty") timer = setTimeout(() => setTick((t) => t + 1), 3000);
      })
      .catch((e) => setError(e));
    return () => clearTimeout(timer);
  }, [tick]);
  return { meta, error, reload: () => setTick((t) => t + 1) };
}

export default function App() {
  const { meta, error, reload } = useMeta();
  const [tab, setTab] = useState("brief");
  const [mode, setMode] = useState("cutoff");
  const [cutoff, setCutoff] = useState("09:00");
  const [lead, setLead] = useState(24);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (meta?.default_cutoff) setCutoff(meta.default_cutoff);
  }, [meta?.default_cutoff]);

  const ready = meta?.status === "ready";
  const params = { mode, cutoff, lead_hours: lead };
  const key = JSON.stringify(params);
  const latest = useAsync(() => api.latest(params), key, ready);
  const overall = useAsync(() => api.metrics(params), key, ready);

  useEffect(() => {
    if (latest.data?.days?.length && !latest.data.days.some((d) => d.date === selected)) {
      setSelected(latest.data.days[0].date);
    }
  }, [latest.data, selected]);

  return (
    <>
      <header className="top">
        <div className="wrap top-row">
          <div className="brand">
            <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
              <path d="M3 9h13a3.5 3.5 0 1 0-3.5-3.5M3 14.5h19a3.5 3.5 0 1 1-3.5 3.5M3 20h9a3 3 0 1 1-3 3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            <div>
              <strong>WindDesk</strong>
              <span>GB day-ahead wind briefing</span>
            </div>
          </div>
          {ready && (
            <p className="source">
              Elexon BMRS · FUELHH and WINDFOR
              {meta.fetched_at && <> · data fetched {stamp(meta.fetched_at)}</>}
            </p>
          )}
        </div>
        {ready && (
          <div className="wrap tabs-row">
            <nav className="tabs" aria-label="Sections">
              <button className={tab === "brief" ? "on" : ""} aria-current={tab === "brief"} onClick={() => setTab("brief")}>
                Day-ahead brief
              </button>
              <button className={tab === "accuracy" ? "on" : ""} aria-current={tab === "accuracy"} onClick={() => setTab("accuracy")}>
                Forecast accuracy
              </button>
            </nav>
          </div>
        )}
      </header>

      {meta?.source === "demo" && (
        <div className="banner" role="status">
          Demo data: these numbers are synthetic and only show how the tool looks. Run the fetch script to load real Elexon data.
        </div>
      )}

      <main className="wrap">
        {error && (
          <div className="state error">
            Cannot reach the API ({error.message}). Check the backend is running.
            <button className="ghost" onClick={reload}>Retry</button>
          </div>
        )}
        {!meta && !error && <p className="state">Loading…</p>}
        {meta && !ready && (
          <div className={`state ${meta.status === "error" ? "error" : ""}`}>
            {meta.status === "error" ? (
              <>
                Could not load Elexon data: {meta.error}
                {meta.can_refresh && (
                  <button className="ghost" onClick={() => api.refresh().then(reload)}>Try again</button>
                )}
              </>
            ) : (
              <>
                <span className="spinner" aria-hidden="true" />
                Fetching January 2026 wind data from Elexon. The first start takes a minute or two.
              </>
            )}
          </div>
        )}

        {ready && (
          <>
            <Controls mode={mode} setMode={setMode} cutoff={cutoff} setCutoff={setCutoff} lead={lead} setLead={setLead} />
            {latest.error && <p className="state error">{latest.error.message}</p>}
            {latest.loading && !latest.data && <p className="state">Loading forecasts…</p>}
            {latest.data && tab === "brief" && selected && (
              <DayBrief latest={latest.data} metrics={overall.data} mode={mode} cutoff={cutoff} lead={lead} selected={selected} setSelected={setSelected} />
            )}
            {latest.data && tab === "accuracy" && <Accuracy meta={meta} latest={latest.data} mode={mode} cutoff={cutoff} lead={lead} />}
          </>
        )}
      </main>

      <footer className="wrap foot">
        Pilot build. Error = forecast − actual. National wind only, purchase decisions taken in January 2026.
      </footer>
    </>
  );
}
