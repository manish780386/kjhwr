"""Core analytics: choosing the forecast available at decision time, and scoring it.

Terminology
-----------
* delivery day D : the UK-local calendar day the power is delivered.
* decision time  : the day-ahead cutoff on D-1 (default 09:00 UK local time).
* horizon        : startTime - publishTime, i.e. how far ahead a forecast was made.
* error          : forecast - actual. Positive = over-forecast (wind came in lower
                   than expected, so the buyer is short).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config

TZ = config.LOCAL_TZ
_CUTOFF_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


# ----------------------------------------------------------------- time helpers
def parse_cutoff(cutoff: str) -> tuple[int, int]:
    match = _CUTOFF_RE.match(cutoff)
    if not match:
        raise ValueError(f"cutoff must be HH:MM (24h), got {cutoff!r}")
    return int(match.group(1)), int(match.group(2))


def cutoff_utc(delivery_date, cutoff: str, days_ahead: int = config.DAYS_AHEAD) -> pd.Timestamp:
    """Decision cutoff for a delivery date, as a UTC timestamp (handles BST/GMT)."""
    hour, minute = parse_cutoff(cutoff)
    local = pd.Timestamp(delivery_date) - pd.Timedelta(days=days_ahead) + pd.Timedelta(hours=hour, minutes=minute)
    return local.tz_localize(TZ, ambiguous=False, nonexistent="shift_forward").tz_convert("UTC")


def add_delivery_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["delivery_date"] = out["start_time"].dt.tz_convert(TZ).dt.date
    return out


# ------------------------------------------------------------ forecast selection
def select_latest_before_cutoff(forecasts: pd.DataFrame, cutoff: str = config.DEFAULT_CUTOFF) -> pd.DataFrame:
    """For every target half-hour keep the newest forecast published at or before the
    decision cutoff of the previous day. This is what a buyer could actually see."""
    cols = ["start_time", "publish_time", "forecast_mw", "cutoff_time"]
    if forecasts.empty:
        return pd.DataFrame(columns=cols)
    f = add_delivery_date(forecasts)
    cutoffs = {d: cutoff_utc(d, cutoff) for d in f["delivery_date"].unique()}
    f["cutoff_time"] = pd.to_datetime(f["delivery_date"].map(cutoffs), utc=True).astype("datetime64[ns, UTC]")
    f = f[f["publish_time"] <= f["cutoff_time"]]
    f = f.sort_values(["start_time", "publish_time"]).drop_duplicates("start_time", keep="last")
    return f[cols].reset_index(drop=True)


def select_by_lead_time(forecasts: pd.DataFrame, lead_hours: float) -> pd.DataFrame:
    """Newest forecast that was published at least `lead_hours` before the target."""
    cols = ["start_time", "publish_time", "forecast_mw"]
    if forecasts.empty:
        return pd.DataFrame(columns=cols)
    f = forecasts[forecasts["publish_time"] <= forecasts["start_time"] - pd.Timedelta(hours=lead_hours)]
    f = f.sort_values(["start_time", "publish_time"]).drop_duplicates("start_time", keep="last")
    return f[cols].reset_index(drop=True)


def build_comparison(actuals: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    """Outer-join selected forecasts with actuals and derive error columns."""
    df = actuals.merge(selected, on="start_time", how="outer").sort_values("start_time").reset_index(drop=True)
    df = add_delivery_date(df)
    df["horizon_h"] = (df["start_time"] - df["publish_time"]) / pd.Timedelta(hours=1)
    df["error"] = df["forecast_mw"] - df["actual_mw"]
    df["abs_error"] = df["error"].abs()
    return df


def filter_dates(df: pd.DataFrame, start, end) -> pd.DataFrame:
    return df[(df["delivery_date"] >= start) & (df["delivery_date"] <= end)].reset_index(drop=True)


# ---------------------------------------------------------------------- metrics
def _num(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return float(x)


def compute_metrics(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["forecast_mw", "actual_mw"])
    n = int(len(d))
    if n == 0:
        return {"n": 0}
    err, abs_err = d["error"], d["abs_error"]
    mean_actual = float(d["actual_mw"].mean())
    big = d[d["actual_mw"] >= config.MIN_ACTUAL_FOR_MAPE_MW]
    mape = float((big["abs_error"] / big["actual_mw"]).mean() * 100) if len(big) else None
    return {
        "n": n,
        "mean_actual_mw": mean_actual,
        "mean_forecast_mw": float(d["forecast_mw"].mean()),
        "mae": float(abs_err.mean()),
        "rmse": float(np.sqrt((err**2).mean())),
        "bias": float(err.mean()),
        "mape_pct": _num(mape),
        "nmae_pct": float(abs_err.mean() / mean_actual * 100) if mean_actual else None,
        "p50_abs": float(abs_err.quantile(0.50)),
        "p90_abs": float(abs_err.quantile(0.90)),
        "p95_abs": float(abs_err.quantile(0.95)),
        "p99_abs": float(abs_err.quantile(0.99)),
        "p05_err": float(err.quantile(0.05)),
        "p95_err": float(err.quantile(0.95)),
        "over_share_pct": float((err > 0).mean() * 100),
        "max_over": float(err.max()),
        "max_under": float(err.min()),
    }


def daily_metrics(df: pd.DataFrame) -> list[dict]:
    d = df.dropna(subset=["forecast_mw", "actual_mw"])
    if d.empty:
        return []
    g = d.assign(sq=d["error"] ** 2).groupby("delivery_date")
    out = pd.DataFrame(
        {"mae": g["abs_error"].mean(), "bias": g["error"].mean(), "rmse": np.sqrt(g["sq"].mean()), "n": g.size()}
    ).reset_index()
    out["delivery_date"] = out["delivery_date"].astype(str)
    return [{**r, "n": int(r["n"])} for r in out.to_dict("records")]


def error_histogram(df: pd.DataFrame, bins: int = 31) -> list[dict]:
    err = df["error"].dropna()
    if err.empty:
        return []
    limit = float(np.ceil(max(abs(err.quantile(0.005)), abs(err.quantile(0.995))) / 500) * 500) or 500.0
    counts, edges = np.histogram(err.clip(-limit, limit), bins=bins, range=(-limit, limit))
    return [
        {"from": float(edges[i]), "to": float(edges[i + 1]), "mid": float((edges[i] + edges[i + 1]) / 2), "count": int(c)}
        for i, c in enumerate(counts)
    ]


def horizon_metrics(
    forecasts: pd.DataFrame, actuals: pd.DataFrame, start, end, bucket_hours: int = 6, max_horizon: int = 168
) -> list[dict]:
    """Accuracy of *every* published forecast, grouped by how far ahead it was made."""
    f = forecasts.merge(actuals, on="start_time", how="inner")
    if f.empty:
        return []
    f = filter_dates(add_delivery_date(f), start, end)
    f["horizon_h"] = (f["start_time"] - f["publish_time"]) / pd.Timedelta(hours=1)
    f = f[(f["horizon_h"] >= 0) & (f["horizon_h"] < max_horizon)]
    if f.empty:
        return []
    f["error"] = f["forecast_mw"] - f["actual_mw"]
    f["abs_error"] = f["error"].abs()
    f["sq"] = f["error"] ** 2
    f["bucket"] = (f["horizon_h"] // bucket_hours * bucket_hours).astype(int)
    g = f.groupby("bucket")
    out = pd.DataFrame(
        {
            "mae": g["abs_error"].mean(),
            "rmse": np.sqrt(g["sq"].mean()),
            "bias": g["error"].mean(),
            "p90_abs": g["abs_error"].quantile(0.9),
            "n": g.size(),
        }
    ).reset_index()
    return [{**r, "bucket": int(r["bucket"]), "n": int(r["n"]), "label": f"{int(r['bucket'])}-{int(r['bucket']) + bucket_hours}h"} for r in out.to_dict("records")]


# --------------------------------------------------------------------- summaries
def day_summaries(df: pd.DataFrame) -> list[dict]:
    """One row per delivery day describing what the forecast says."""
    out = []
    for day, g in df.groupby("delivery_date"):
        f = g.dropna(subset=["forecast_mw"])
        if f.empty:
            continue
        peak, low = f.loc[f["forecast_mw"].idxmax()], f.loc[f["forecast_mw"].idxmin()]
        a = g.dropna(subset=["actual_mw"])
        both = g.dropna(subset=["actual_mw", "forecast_mw"])
        out.append(
            {
                "date": str(day),
                "periods": int(len(f)),
                "forecast_mwh": float(f["forecast_mw"].sum() * 0.5),
                "forecast_mean_mw": float(f["forecast_mw"].mean()),
                "peak_mw": float(peak["forecast_mw"]),
                "peak_time": peak["start_time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "low_mw": float(low["forecast_mw"]),
                "low_time": low["start_time"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "actual_mwh": float(a["actual_mw"].sum() * 0.5) if len(a) else None,
                "mae": float(both["abs_error"].mean()) if len(both) else None,
                "issued_first": f["publish_time"].min().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "issued_last": f["publish_time"].max().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "cutoff_time": (
                    f["cutoff_time"].iloc[0].strftime("%Y-%m-%dT%H:%M:%SZ") if "cutoff_time" in f and pd.notna(f["cutoff_time"].iloc[0]) else None
                ),
            }
        )
    return out


def build_insights(m: dict, daily: list[dict], horizon: list[dict]) -> list[dict]:
    if not m.get("n"):
        return []
    items = []
    bias = m["bias"]
    if abs(bias) < 0.02 * m["mean_actual_mw"]:
        items.append({"title": "No systematic lean", "text": f"Over and under-forecasts roughly cancel out (average bias {bias:+,.0f} MW). Plan around the size of the misses, not their direction."})
    elif bias > 0:
        items.append({"title": "Forecast runs high", "text": f"On average the forecast is {bias:,.0f} MW above what wind delivered, so you are more often short than long. Consider buying a little extra cover."})
    else:
        items.append({"title": "Forecast runs low", "text": f"On average the forecast is {abs(bias):,.0f} MW below what wind delivered, so you tend to over-buy. Consider trimming thermal cover."})
    items.append({"title": "A planning buffer", "text": f"Nine in ten half-hours missed by less than {m['p90_abs']:,.0f} MW. One in a hundred missed by more than {m['p99_abs']:,.0f} MW."})
    if daily:
        worst = max(daily, key=lambda r: r["mae"])
        best = min(daily, key=lambda r: r["mae"])
        items.append({"title": "Hardest and easiest days", "text": f"{worst['delivery_date']} was the hardest to call (average miss {worst['mae']:,.0f} MW). {best['delivery_date']} was the easiest ({best['mae']:,.0f} MW)."})
    if len(horizon) >= 2:
        first, last = horizon[0], horizon[min(len(horizon) - 1, 4)]
        if last["mae"] > first["mae"]:
            items.append({"title": "Older forecasts are worse", "text": f"Forecasts made {first['label']} ahead miss by {first['mae']:,.0f} MW on average. By {last['label']} ahead that grows to {last['mae']:,.0f} MW. Always use the newest forecast available."})
    return items
