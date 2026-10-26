const CUTOFFS = ["06:00", "07:00", "08:00", "08:30", "09:00", "09:30", "10:00", "11:00", "12:00"];
const LEADS = [6, 12, 18, 24, 30, 36, 48];

export default function Controls({ mode, setMode, cutoff, setCutoff, lead, setLead }) {
  return (
    <div className="controls" role="group" aria-label="Forecast selection rule">
      <div className="seg" role="radiogroup" aria-label="Forecast selection mode">
        <button role="radio" aria-checked={mode === "cutoff"} className={mode === "cutoff" ? "on" : ""} onClick={() => setMode("cutoff")}>
          Latest before cutoff
        </button>
        <button role="radio" aria-checked={mode === "lead"} className={mode === "lead" ? "on" : ""} onClick={() => setMode("lead")}>
          Fixed lead time
        </button>
      </div>
      {mode === "cutoff" ? (
        <label className="field">
          <span>Day-ahead cutoff (UK time, day before)</span>
          <select value={cutoff} onChange={(e) => setCutoff(e.target.value)}>
            {CUTOFFS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="field">
          <span>Forecast made at least this far ahead</span>
          <select value={lead} onChange={(e) => setLead(Number(e.target.value))}>
            {LEADS.map((h) => (
              <option key={h} value={h}>
                {h} hours
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
