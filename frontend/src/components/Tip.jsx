import { mw, signed, time, dayShort, stamp } from "../format.js";

/** Tooltip for time-series charts. Expects payload rows built by `toRows`. */
export default function Tip({ active, payload, showDate }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const miss = r.forecast != null && r.actual != null ? r.forecast - r.actual : null;
  return (
    <div className="tip">
      <div className="tip-head">
        {showDate ? `${dayShort(r.ts)}, ` : ""}
        {time(r.ts)}
      </div>
      {r.forecast != null && (
        <div className="tip-row">
          <i className="sw sw-forecast" />
          Forecast <b>{mw(r.forecast)}</b>
        </div>
      )}
      {r.actual != null && (
        <div className="tip-row">
          <i className="sw sw-actual" />
          Actual <b>{mw(r.actual)}</b>
        </div>
      )}
      {miss != null && (
        <div className="tip-row tip-miss">
          {miss > 0 ? "Over-forecast by" : "Under-forecast by"} <b>{mw(Math.abs(miss))}</b>
        </div>
      )}
      {r.published && <div className="tip-foot">Forecast issued {stamp(r.published)}</div>}
    </div>
  );
}

export { signed };
