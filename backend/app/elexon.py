"""Thin client for the Elexon Insights (BMRS) stream endpoints.

Both endpoints return a JSON array. Long windows are split into chunks, and a chunk
is split further automatically if the API rejects it as too large (HTTP 400).
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import httpx
import pandas as pd

from . import config

log = logging.getLogger(__name__)


class WindowTooLarge(Exception):
    pass


def _get_json(client: httpx.Client, path: str, params: dict, retries: int = 4) -> list[dict]:
    url = f"{config.ELEXON_BASE_URL}{path}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.get(url, params=params, timeout=90)
            if response.status_code == 400:
                raise WindowTooLarge(response.text[:300])
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else payload.get("data", [])
        except WindowTooLarge:
            raise
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Elexon request failed for {path}: {last_error}")


def _fetch_windowed(
    fetch_window: Callable[[datetime, datetime], list[dict]],
    start: datetime,
    end: datetime,
    chunk: timedelta,
    min_chunk: timedelta = timedelta(hours=6),
) -> list[dict]:
    rows: list[dict] = []
    cursor = start
    while cursor < end:
        window_end = min(cursor + chunk, end)
        rows.extend(_fetch_recursive(fetch_window, cursor, window_end, min_chunk))
        cursor = window_end
    return rows


def _fetch_recursive(fetch_window, lo: datetime, hi: datetime, min_chunk: timedelta) -> list[dict]:
    try:
        log.info("Fetching %s -> %s", lo.isoformat(), hi.isoformat())
        return fetch_window(lo, hi)
    except WindowTooLarge:
        if hi - lo <= min_chunk:
            raise
        mid = lo + (hi - lo) / 2
        return _fetch_recursive(fetch_window, lo, mid, min_chunk) + _fetch_recursive(fetch_window, mid, hi, min_chunk)


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).astype("datetime64[ns, UTC]")


def fetch_actuals(client: httpx.Client, start: date, end: date) -> pd.DataFrame:
    """Half-hourly national wind generation (FUELHH, fuelType=WIND). `end` is inclusive."""
    lo = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    hi = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)

    def fetch_window(a: datetime, b: datetime) -> list[dict]:
        params = {
            "settlementDateFrom": a.date().isoformat(),
            "settlementDateTo": (b - timedelta(seconds=1)).date().isoformat(),
            "fuelType": "WIND",
            "format": "json",
        }
        return _get_json(client, "/datasets/FUELHH/stream", params)

    rows = _fetch_windowed(fetch_window, lo, hi, chunk=timedelta(days=7), min_chunk=timedelta(days=1))
    if not rows:
        return pd.DataFrame(columns=["start_time", "actual_mw"])
    df = pd.DataFrame(rows)
    if "fuelType" in df:
        df = df[df["fuelType"] == "WIND"]
    if "publishTime" in df:
        df = df.sort_values("publishTime")
    df = df.rename(columns={"startTime": "start_time", "generation": "actual_mw"})
    df["start_time"] = _to_utc(df["start_time"])
    df["actual_mw"] = pd.to_numeric(df["actual_mw"], errors="coerce")
    df = df.drop_duplicates("start_time", keep="last")
    return df[["start_time", "actual_mw"]].sort_values("start_time").reset_index(drop=True)


def fetch_forecasts(client: httpx.Client, publish_from: date, publish_to: date) -> pd.DataFrame:
    """All WINDFOR forecast versions published in [publish_from, publish_to)."""
    lo = datetime(publish_from.year, publish_from.month, publish_from.day, tzinfo=timezone.utc)
    hi = datetime(publish_to.year, publish_to.month, publish_to.day, tzinfo=timezone.utc)

    def fetch_window(a: datetime, b: datetime) -> list[dict]:
        params = {
            "publishDateTimeFrom": a.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publishDateTimeTo": b.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "format": "json",
        }
        return _get_json(client, "/datasets/WINDFOR/stream", params)

    rows = _fetch_windowed(fetch_window, lo, hi, chunk=timedelta(days=2), min_chunk=timedelta(hours=6))
    if not rows:
        return pd.DataFrame(columns=["start_time", "publish_time", "forecast_mw"])
    df = pd.DataFrame(rows).rename(
        columns={"startTime": "start_time", "publishTime": "publish_time", "generation": "forecast_mw"}
    )
    df["start_time"] = _to_utc(df["start_time"])
    df["publish_time"] = _to_utc(df["publish_time"])
    df["forecast_mw"] = pd.to_numeric(df["forecast_mw"], errors="coerce")
    df = df.dropna(subset=["forecast_mw"]).drop_duplicates(["start_time", "publish_time"], keep="last")
    return df[["start_time", "publish_time", "forecast_mw"]].sort_values(["start_time", "publish_time"]).reset_index(drop=True)


def fetch_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    with httpx.Client(headers={"Accept": "application/json"}) as client:
        actuals = fetch_actuals(client, config.DELIVERY_START, config.DELIVERY_END)
        forecasts = fetch_forecasts(client, config.FORECAST_FETCH_FROM, config.FORECAST_FETCH_TO)
    return actuals, forecasts
