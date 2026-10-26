import { useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Tip from "./Tip.jsx";
import { dateKey, dateStrShort, dayLong, humanDuration, londonHM, minutesBetween, mw, num, stamp, time, weekday } from "../format.js";

export default function DayBrief({ latest, metrics, mode, cutoff, lead, selected, setSelected }) {
  const [showRange, setShowRange] = useState(true);
  const [showActual, setShowActual] = useState(false);

  const days = latest.days;
  const day = days.find((d) => d.date === selected) || days[0];
  const buffer = metrics?.overall?.p90_abs ?? null;
  const maxMwh = Math.max(...days.map((d) => d.forecast_mwh));

  const rows = useMemo(() => {
    return latest.points
      .filter((p) => dateKey(p.t) === day.date)
      .map((p) => {
        const ts = new Date(p.t).getTime();
        const f = p.forecast_mw;
        return {
          ts,
          forecast: f,
          actual: showActual ? p.actual_mw : null,
          published: p.published,
          range: f != null && buffer != null ? [Math.max(0, f - buffer), f + buffer] : null,
        };
      });
  }, [latest, day.date, buffer, showActual]);

  const ticks = rows.filter((r) => {
    const { h, m } = londonHM(r.ts);
    return m === 0 && h % 3 === 0;
  }).map((r) => r.ts);

  const idx = days.findIndex((d) => d.date === day.date);
  const go = (delta) => days[idx + delta] && setSelected(days[idx + delta].date);
  const lateBy = day.cutoff_time && day.issued_last ? minutesBetween(day.issued_last, day.cutoff_time) : null;

  return (
    <section aria-labelledby="brief-title">
      <div className="lede">
        <p className="kicker">Delivery day</p>
        <h1 id="brief-title">
          Wind should deliver about {num(day.forecast_mwh / 1000, 0)} GWh on {dayLong(day.date)}
        </h1>
        <p className="sub">
          {mode === "cutoff"
            ? `Based on the newest forecast published before the ${cutoff} cutoff the day before, which is what you can see when placing the day-ahead order.`
            : `Based on the newest forecast that was issued at least ${lead} hours before each half-hour.`}
        </p>
      </div>

      <div className="strip" role="listbox" aria-label="Choose delivery day">
        {days.map((d) => (
          <button
            key={d.date}
            role="option"
            aria-selected={d.date === day.date}
            className={d.date === day.date ? "on" : ""}
            onClick={() => setSelected(d.date)}
            title={`${dayLong(d.date)}: ${num(d.forecast_mwh / 1000, 0)} GWh forecast`}
          >
            <span className="strip-bar" style={{ height: `${Math.max(5, (d.forecast_mwh / maxMwh) * 46)}px` }} />
            <span className="strip-dow">{weekday(d.date)}</span>
            <span className="strip-num">{Number(d.date.slice(8))}</span>
          </button>
        ))}
      </div>

      <div className="grid brief-grid">
        <div className="panel chart-panel">
          <div className="panel-head">
            <div>
              <h2>Half-hourly wind output</h2>
              <p className="muted">National total, MW. Times are UK local.</p>
            </div>
            <div className="toggles">
              <label className="check">
                <input type="checkbox" checked={showRange} onChange={(e) => setShowRange(e.target.checked)} />
                <i className="sw sw-range" /> Planning range
              </label>
              <label className="check">
                <input type="checkbox" checked={showActual} onChange={(e) => setShowActual(e.target.checked)} />
                <i className="sw sw-actual" /> Actual (known only afterwards)
              </label>
            </div>
          </div>
          <div className="chart tall">
            <ResponsiveContainer>
              <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--line)" />
                <XAxis dataKey="ts" type="number" scale="time" domain={["dataMin", "dataMax"]} ticks={ticks} tickFormatter={time} tick={{ fill: "var(--muted)", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "var(--line)" }} />
                <YAxis tickFormatter={(v) => num(v / 1000, 0) + "k"} tick={{ fill: "var(--muted)", fontSize: 12 }} tickLine={false} axisLine={false} width={40} domain={[0, "auto"]} />
                <Tooltip content={<Tip />} cursor={{ stroke: "var(--ink)", strokeDasharray: "3 3" }} />
                {showRange && buffer != null && <Area dataKey="range" stroke="none" fill="var(--forecast)" fillOpacity={0.16} isAnimationActive={false} activeDot={false} />}
                <Line dataKey="forecast" stroke="var(--forecast)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                {showActual && <Line dataKey="actual" stroke="var(--ink)" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {showRange && buffer != null && (
            <p className="note">
              The shaded band is the forecast ± {mw(buffer)}, the size that 9 in 10 half-hours stayed within across January.
            </p>
          )}
        </div>

        <aside className="panel facts" aria-label="Decision facts">
          <div className="day-nav">
            <button onClick={() => go(-1)} disabled={idx <= 0} aria-label="Previous day">
              ‹
            </button>
            <span>{dateStrShort(day.date)}</span>
            <button onClick={() => go(1)} disabled={idx >= days.length - 1} aria-label="Next day">
              ›
            </button>
          </div>
          <dl>
            <div>
              <dt>Expected wind energy</dt>
              <dd className="big">{num(day.forecast_mwh)} <small>MWh</small></dd>
            </div>
            <div>
              <dt>Average output</dt>
              <dd>{mw(day.forecast_mean_mw)}</dd>
            </div>
            <div>
              <dt>Peak</dt>
              <dd>{mw(day.peak_mw)} <small>at {time(day.peak_time)}</small></dd>
            </div>
            <div>
              <dt>Lowest</dt>
              <dd>{mw(day.low_mw)} <small>at {time(day.low_time)}</small></dd>
            </div>
            {buffer != null && (
              <div>
              <dt>Typical miss (9 in 10)</dt>
                <dd>± {mw(buffer)}</dd>
              </div>
            )}
            <div>
              <dt>{mode === "cutoff" ? "Forecast issued" : "Forecasts issued"}</dt>
              <dd>
                {mode === "cutoff" ? (
                  <>
                    {stamp(day.issued_last)}
                    {lateBy !== null && <small> {humanDuration(lateBy)} before cutoff</small>}
                  </>
                ) : (
                  <small>{lead}+ hours before each half-hour</small>
                )}
              </dd>
            </div>
            {showActual && day.actual_mwh != null && (
              <div className="after">
                <dt>What actually happened</dt>
                <dd>
                  {num(day.actual_mwh)} <small>MWh</small>
                  <small className={day.forecast_mwh > day.actual_mwh ? "bad" : "ok"}>
                    {" "}
                    forecast was {num(Math.abs(day.forecast_mwh - day.actual_mwh))} MWh {day.forecast_mwh > day.actual_mwh ? "too high" : "too low"}
                  </small>
                </dd>
              </div>
            )}
          </dl>
        </aside>
      </div>
    </section>
  );
}
