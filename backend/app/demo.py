"""Synthetic wind data so the UI can be explored without network access.

NOT real data. The API labels it as source="demo" and the UI shows a banner.
Run:  python -m app.demo
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def generate(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp(config.FORECAST_FETCH_FROM, tz="UTC")
    end = pd.Timestamp(config.DELIVERY_END, tz="UTC") + pd.Timedelta(days=1)
    idx = pd.date_range(start, end, freq="30min", inclusive="left")

    # Smooth, weather-like signal: slow fronts + faster ripple + noise.
    t = np.arange(len(idx))
    base = 7500 + 4200 * np.sin(t / 310.0) + 2200 * np.sin(t / 97.0 + 1.3) + 700 * np.sin(t / 23.0)
    noise = np.convolve(rng.normal(0, 380, len(t)), np.ones(6) / 6, mode="same")
    truth = np.clip(base + noise, 150, 16500)
    truth_s = pd.Series(truth, index=idx)

    lo = pd.Timestamp(config.DELIVERY_START, tz="UTC")
    hi = pd.Timestamp(config.DELIVERY_END, tz="UTC") + pd.Timedelta(days=1)
    in_range = (idx >= lo) & (idx < hi)
    actuals = pd.DataFrame({"start_time": idx[in_range], "actual_mw": truth[in_range].round(0)})

    publishes = pd.date_range(start, end - pd.Timedelta(days=1), freq="1h")
    horizons = pd.timedelta_range("30min", "72h", freq="30min")
    frames = []
    for p in publishes:
        targets = p + horizons
        targets = targets[(targets >= idx[0]) & (targets <= idx[-1])]
        if len(targets) == 0:
            continue
        h_hours = np.asarray((targets - p) / pd.Timedelta(hours=1), dtype=float)
        sd = 250 + 210 * np.sqrt(h_hours)
        values = truth_s.reindex(targets).to_numpy() * 0.985 + rng.normal(0, sd)
        frames.append(pd.DataFrame({"start_time": targets, "publish_time": p, "forecast_mw": np.clip(values, 0, 17000).round(0)}))
    forecasts = pd.concat(frames, ignore_index=True)
    for col in ("start_time", "publish_time"):
        forecasts[col] = pd.to_datetime(forecasts[col], utc=True).astype("datetime64[ns, UTC]")
    actuals["start_time"] = pd.to_datetime(actuals["start_time"], utc=True).astype("datetime64[ns, UTC]")
    return actuals, forecasts


if __name__ == "__main__":
    from .store import store

    store.load_demo()
    print(f"Wrote demo snapshot to {config.DATA_DIR}")
