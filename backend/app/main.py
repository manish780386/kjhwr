"""FastAPI application exposing the wind forecast analytics."""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, forecast
from .store import store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("winddesk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not store.load_from_disk():
        if config.DEMO_MODE:
            store.load_demo()
        elif config.AUTO_FETCH:
            store.refresh_in_background()
    yield


app = FastAPI(title="WindDesk API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


# ------------------------------------------------------------------- helpers
def _ensure_loaded() -> None:
    """Serverless hosts may skip the lifespan hook, so load the snapshot lazily too."""
    if store.status == "empty":
        store.load_from_disk()


def _require_data() -> None:
    _ensure_loaded()
    if store.status != "ready":
        detail = {"empty": "No data loaded yet.", "loading": "Fetching data from Elexon, please wait.", "error": f"Data fetch failed: {store.error}"}[store.status]
        raise HTTPException(status_code=503, detail=detail)


def _parse_range(start: date | None, end: date | None) -> tuple[date, date]:
    start, end = start or config.DELIVERY_START, end or config.DELIVERY_END
    if start > end:
        raise HTTPException(400, "start must be on or before end")
    if start < config.DELIVERY_START or end > config.DELIVERY_END:
        raise HTTPException(400, f"Delivery dates must be between {config.DELIVERY_START} and {config.DELIVERY_END}")
    return start, end


def _validate_cutoff(cutoff: str) -> str:
    try:
        forecast.parse_cutoff(cutoff)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return cutoff


def _comparison(mode: str, cutoff: str, lead_hours: float, start: date, end: date) -> pd.DataFrame:
    if mode == "cutoff":
        selected = forecast.select_latest_before_cutoff(store.forecasts, _validate_cutoff(cutoff))
    else:
        selected = forecast.select_by_lead_time(store.forecasts, lead_hours)
    return forecast.filter_dates(forecast.build_comparison(store.actuals, selected), start, end)


def _iso(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


Mode = Literal["cutoff", "lead"]


# ----------------------------------------------------------------- endpoints
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    _ensure_loaded()
    return {
        "status": store.status,
        "error": store.error,
        "source": store.meta.get("source"),
        "fetched_at": store.meta.get("fetched_at"),
        "actual_rows": store.meta.get("actual_rows"),
        "forecast_rows": store.meta.get("forecast_rows"),
        "delivery_start": config.DELIVERY_START.isoformat(),
        "delivery_end": config.DELIVERY_END.isoformat(),
        "decision_start": config.DECISION_START.isoformat(),
        "decision_end": config.DECISION_END.isoformat(),
        "default_cutoff": config.DEFAULT_CUTOFF,
        "timezone": config.LOCAL_TZ,
        "can_refresh": config.AUTO_FETCH,
    }


@app.post("/api/refresh")
def refresh():
    if not config.AUTO_FETCH:
        raise HTTPException(403, "Refresh is disabled on this deployment. Run scripts/fetch_data.py and redeploy.")
    started = store.refresh_in_background()
    return {"started": started, "status": store.status}


@app.get("/api/actuals")
def actuals(start: date | None = None, end: date | None = None):
    _require_data()
    start, end = _parse_range(start, end)
    a = forecast.filter_dates(forecast.add_delivery_date(store.actuals), start, end)
    return [{"t": t, "actual_mw": v} for t, v in zip(_iso(a["start_time"]), a["actual_mw"])]


@app.get("/api/forecast/latest")
def latest_forecast(
    start: date | None = None,
    end: date | None = None,
    mode: Mode = "cutoff",
    cutoff: str = config.DEFAULT_CUTOFF,
    lead_hours: float = Query(24, ge=0, le=336),
):
    """The forecast a buyer could see at decision time, joined with actuals."""
    _require_data()
    start, end = _parse_range(start, end)
    df = _comparison(mode, cutoff, lead_hours, start, end)
    points = pd.DataFrame(
        {
            "t": _iso(df["start_time"]),
            "actual_mw": df["actual_mw"],
            "forecast_mw": df["forecast_mw"],
            "published": _iso(df["publish_time"]).where(df["publish_time"].notna()),
            "horizon_h": df["horizon_h"],
            "error": df["error"],
        }
    )
    points = points.astype(object).where(points.notna(), None)
    return {
        "mode": mode,
        "cutoff": cutoff,
        "lead_hours": lead_hours,
        "points": points.to_dict("records"),
        "days": forecast.day_summaries(df),
    }


@app.get("/api/metrics")
def metrics(
    start: date | None = None,
    end: date | None = None,
    mode: Mode = "cutoff",
    cutoff: str = config.DEFAULT_CUTOFF,
    lead_hours: float = Query(24, ge=0, le=336),
):
    _require_data()
    start, end = _parse_range(start, end)
    df = _comparison(mode, cutoff, lead_hours, start, end)
    overall = forecast.compute_metrics(df)
    daily = forecast.daily_metrics(df)
    horizon = forecast.horizon_metrics(store.forecasts, store.actuals, start, end)
    return {
        "overall": overall,
        "daily": daily,
        "histogram": forecast.error_histogram(df),
        "insights": forecast.build_insights(overall, daily, horizon),
    }


@app.get("/api/horizon-metrics")
def horizon_metrics(
    start: date | None = None,
    end: date | None = None,
    bucket_hours: int = Query(6, ge=1, le=24),
    max_horizon: int = Query(168, ge=6, le=336),
):
    _require_data()
    start, end = _parse_range(start, end)
    return forecast.horizon_metrics(store.forecasts, store.actuals, start, end, bucket_hours, max_horizon)
