const TZ = "Europe/London";

export const mw = (x, digits = 0) =>
  x === null || x === undefined ? "–" : `${Number(x).toLocaleString("en-GB", { maximumFractionDigits: digits })} MW`;

export const num = (x, digits = 0) =>
  x === null || x === undefined ? "–" : Number(x).toLocaleString("en-GB", { maximumFractionDigits: digits });

export const signed = (x, digits = 0) =>
  x === null || x === undefined ? "–" : `${x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toLocaleString("en-GB", { maximumFractionDigits: digits })}`;

export const pct = (x, digits = 1) => (x === null || x === undefined ? "–" : `${Number(x).toFixed(digits)}%`);

const fmt = (opts) => new Intl.DateTimeFormat("en-GB", { timeZone: TZ, ...opts });
const fTime = fmt({ hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const fDay = fmt({ weekday: "short", day: "numeric", month: "short" });
const fDayLong = fmt({ weekday: "long", day: "numeric", month: "long", year: "numeric" });
const fDayShort = fmt({ day: "numeric", month: "short" });
const fStamp = fmt({ day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

export const time = (iso) => fTime.format(new Date(iso));
export const day = (iso) => fDay.format(new Date(iso));
export const dayShort = (iso) => fDayShort.format(new Date(iso));
export const stamp = (iso) => fStamp.format(new Date(iso));
export const dayLong = (dateStr) => fDayLong.format(new Date(`${dateStr}T12:00:00Z`));
export const dateStrShort = (dateStr) => fDayShort.format(new Date(`${dateStr}T12:00:00Z`));
export const weekday = (dateStr) =>
  new Intl.DateTimeFormat("en-GB", { weekday: "short", timeZone: "UTC" }).format(new Date(`${dateStr}T12:00:00Z`));

export const minutesBetween = (a, b) => Math.round((new Date(b) - new Date(a)) / 60000);
export const humanDuration = (mins) => {
  const m = Math.abs(mins);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} h ${r} min` : `${h} h`;
};

const fParts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "numeric", minute: "numeric", hourCycle: "h23" });
const fKey = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });

/** London calendar date (YYYY-MM-DD) of an instant. */
export const dateKey = (isoOrMs) => fKey.format(new Date(isoOrMs));

/** London hour/minute of an instant. */
export const londonHM = (ms) => {
  const parts = fParts.formatToParts(new Date(ms));
  return {
    h: Number(parts.find((p) => p.type === "hour").value),
    m: Number(parts.find((p) => p.type === "minute").value),
  };
};
