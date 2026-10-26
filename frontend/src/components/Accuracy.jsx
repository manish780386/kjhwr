import { useMemo, useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, useAsync } from "../api.js";
import Tip from "./Tip.jsx";
import { dateKey, dateStrShort, dayShort, londonHM, mw, num, pct, signed } from "../format.js";

const axis = { fill: "var(--muted)", fontSize: 12 };

function Metric({ label, value, unit, hint }) {
  return (
    <div className="metric">
      <dt>{label}</dt>
      <dd>
        {value}
        {unit && <small> {unit}</small>}
      </dd>
      <p>{hint}</p>
    </div>
  );
}

export default function Accuracy({ meta, latest, mode, cutoff, lead }) {
  const [start, setStart] = useState(meta.delivery_start);
  const [end, setEnd] = useState(meta.delivery_end);
  const [dailyView, setDailyView] = useState("mae");
  const valid = start && end && start <= end;

  const params = { start, end, mode, cutoff, lead_hours: lead };
  const key = JSON.stringify(params);
  const metrics = useAsync(() => api.metrics(params), key, valid);
  const horizon = useAsync(() => api.horizon({ start, end }), `${start}|${end}`, valid);

  const rows = useMemo(
    () =>
      latest.points
        .filter((p) => {
          const k = dateKey(p.t);
          return k >= start && k <= end;
        })
        .map((p) => ({
          ts: new Date(p.t).getTime(),
          forecast: p.forecast_mw,
          actual: p.actual_mw,
          published: p.published,
          gap: p.forecast_mw != null && p.actual_mw != null ? [Math.min(p.forecast_mw, p.actual_mw), Math.max(p.forecast_mw, p.actual_mw)] : null,
        })),
    [latest, start, end]
  );

  const spanDays = Math.max(1, new Set(rows.map((r) => dateKey(r.ts))).size);
  const step = Math.ceil(spanDays / 8);
  const ticks = useMemo(() => {
    const out = [];
    let n = 0;
    for (const r of rows) {
      const { h, m } = londonHM(r.ts);
      if (h === 0 && m === 0) {
        if (n % step === 0) out.push(r.ts);
        n += 1;
      }
    }
    return out;
  }, [rows, step]);

  const m = metrics.data?.overall;
  const hasData = m && m.n > 0;

  return (
    <section aria-labelledby="acc-title">
      <div className="lede">
        <p className="kicker">Forecast accuracy</p>
        <h1 id="acc-title">
          {hasData ? `The forecast you could use was off by ${num(m.mae)} MW on average` : "How far off is the forecast?"}
        </h1>
        <p className="sub">
          Every half-hour in the chosen period, the forecast available at decision time is compared with what wind farms actually produced.
          Use the size of the misses to decide how much cover to hold.
        </p>
      </div>

      <div className="range">
        <label className="field">
          <span>From delivery day</span>
          <input type="date" value={start} min={meta.delivery_start} max={end} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="field">
          <span>To delivery day</span>
          <input type="date" value={end} min={start} max={meta.delivery_end} onChange={(e) => setEnd(e.target.value)} />
        </label>
        <button className="ghost" onClick={() => { setStart(meta.delivery_start); setEnd(meta.delivery_end); }}>
          Whole of January
        </button>
      </div>

      {!valid && <p className="state error">Pick a start date that is on or before the end date.</p>}
      {metrics.error && <p className="state error">{metrics.error.message}</p>}
      {metrics.loading && !metrics.data && <p className="state">Calculating…</p>}

      {hasData && (
        <>
          <dl className="metrics" aria-label="Accuracy metrics">
            <Metric label="Average miss (MAE)" value={num(m.mae)} unit="MW" hint={`${pct(m.nmae_pct)} of average output`} />
            <Metric label="RMSE" value={num(m.rmse)} unit="MW" hint="Punishes large misses more" />
            <Metric label="Bias" value={signed(m.bias)} unit="MW" hint={m.bias > 0 ? "Forecast runs high on average" : "Forecast runs low on average"} />
            <Metric label="MAPE" value={pct(m.mape_pct)} hint="Percent error, ignoring near-zero output" />
            <Metric label="9 in 10 within" value={num(m.p90_abs)} unit="MW" hint="90th percentile of absolute error" />
            <Metric label="99 in 100 within" value={num(m.p99_abs)} unit="MW" hint="99th percentile of absolute error" />
          </dl>

          <div className="grid acc-grid">
            <div className="panel insights">
              <h2>What this means for buying</h2>
              <ul>
                {metrics.data.insights.map((i) => (
                  <li key={i.title}>
                    <b>{i.title}</b>
                    <span>{i.text}</span>
                  </li>
                ))}
              </ul>
              <p className="note">
                Over-forecast = wind came in below the forecast, so you are short. Error = forecast − actual. {num(m.n)} half-hours compared.
              </p>
            </div>

            <div className="panel">
              <div className="panel-head">
                <div>
                  <h2>Forecast against actual</h2>
                  <p className="muted">The orange gap is the miss, half-hour by half-hour.</p>
                </div>
                <div className="legend">
                  <span><i className="sw sw-forecast" /> Forecast</span>
                  <span><i className="sw sw-actual" /> Actual</span>
                  <span><i className="sw sw-miss" /> Miss</span>
                </div>
              </div>
              <div className="chart tall">
                <ResponsiveContainer>
                  <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--line)" />
                    <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} ticks={ticks} tickFormatter={dayShort} tick={axis} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
                    <YAxis tickFormatter={(v) => num(v / 1000, 0) + "k"} tick={axis} tickLine={false} axisLine={false} width={40} />
                    <Tooltip content={<Tip showDate />} cursor={{ stroke: "var(--ink)", strokeDasharray: "3 3" }} />
                    <Area dataKey="gap" stroke="none" fill="var(--miss)" fillOpacity={0.35} isAnimationActive={false} activeDot={false} />
                    <Line dataKey="actual" stroke="var(--ink)" strokeWidth={1.4} dot={false} isAnimationActive={false} />
                    <Line dataKey="forecast" stroke="var(--forecast)" strokeWidth={1.6} dot={false} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="grid two">
            <div className="panel">
              <div className="panel-head">
                <div>
                  <h2>Day by day</h2>
                  <p className="muted">{dailyView === "mae" ? "Average miss per delivery day, MW" : "Average lean per delivery day, MW. Above zero = forecast too high"}</p>
                </div>
                <div className="seg small" role="radiogroup" aria-label="Daily chart metric">
                  <button role="radio" aria-checked={dailyView === "mae"} className={dailyView === "mae" ? "on" : ""} onClick={() => setDailyView("mae")}>Miss</button>
                  <button role="radio" aria-checked={dailyView === "bias"} className={dailyView === "bias" ? "on" : ""} onClick={() => setDailyView("bias")}>Lean</button>
                </div>
              </div>
              <div className="chart">
                <ResponsiveContainer>
                  <BarChart data={metrics.data.daily} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--line)" />
                    <XAxis dataKey="delivery_date" tickFormatter={(d) => Number(d.slice(8))} tick={axis} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={0} />
                    <YAxis tickFormatter={(v) => num(v)} tick={axis} tickLine={false} axisLine={false} width={44} />
                    <Tooltip formatter={(v) => [mw(v), dailyView === "mae" ? "Average miss" : "Average lean"]} labelFormatter={dateStrShort} cursor={{ fill: "rgba(14,34,48,.06)" }} />
                    {dailyView === "bias" && <ReferenceLine y={0} stroke="var(--ink)" />}
                    <Bar dataKey={dailyView} radius={[2, 2, 0, 0]} isAnimationActive={false}>
                      {metrics.data.daily.map((d) => (
                        <Cell key={d.delivery_date} fill={dailyView === "mae" ? "var(--forecast)" : d.bias > 0 ? "var(--miss)" : "var(--forecast)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <div>
                  <h2>How big are the misses?</h2>
                  <p className="muted">Number of half-hours by error size, MW</p>
                </div>
                <div className="legend">
                  <span><i className="sw sw-forecast" /> Too low</span>
                  <span><i className="sw sw-miss" /> Too high</span>
                </div>
              </div>
              <div className="chart">
                <ResponsiveContainer>
                  <BarChart data={metrics.data.histogram} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
                    <CartesianGrid vertical={false} stroke="var(--line)" />
                    <XAxis dataKey="mid" tickFormatter={(v) => signed(v / 1000, 1) + "k"} tick={axis} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval={3} />
                    <YAxis tick={axis} tickLine={false} axisLine={false} width={36} />
                    <Tooltip formatter={(v) => [num(v), "Half-hours"]} labelFormatter={(v) => `Error around ${signed(v)} MW`} cursor={{ fill: "rgba(14,34,48,.06)" }} />
                    <Bar dataKey="count" isAnimationActive={false}>
                      {metrics.data.histogram.map((b) => (
                        <Cell key={b.mid} fill={b.mid > 0 ? "var(--miss)" : "var(--forecast)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>Older forecasts are less accurate</h2>
                <p className="muted">Accuracy of every forecast version in the period, grouped by how far ahead it was issued, MW</p>
              </div>
              <div className="legend">
                <span><i className="sw sw-forecast" /> Average miss</span>
                <span><i className="sw sw-miss" /> 9 in 10 within</span>
              </div>
            </div>
            <div className="chart">
              {horizon.data?.length ? (
                <ResponsiveContainer>
                  <LineChart data={horizon.data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--line)" />
                    <XAxis dataKey="label" tick={axis} tickLine={false} axisLine={{ stroke: "var(--line)" }} interval="preserveStartEnd" minTickGap={16} />
                    <YAxis tickFormatter={(v) => num(v)} tick={axis} tickLine={false} axisLine={false} width={44} domain={[0, "auto"]} />
                    <Tooltip formatter={(v, name) => [mw(v), name]} labelFormatter={(l) => `Issued ${l} before delivery`} />
                    <Line name="Average miss" dataKey="mae" stroke="var(--forecast)" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                    <Line name="9 in 10 within" dataKey="p90_abs" stroke="var(--miss)" strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="state">{horizon.loading ? "Calculating…" : "No data for this period."}</p>
              )}
            </div>
          </div>
        </>
      )}
      {metrics.data && !hasData && <p className="state">No half-hours with both a forecast and an actual in this period.</p>}
    </section>
  );
}
