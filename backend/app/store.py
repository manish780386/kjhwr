"""In-memory data store backed by a gzip-CSV snapshot on disk.

The snapshot means the API never has to call Elexon per request, and a deployment
without outbound access (e.g. Vercel) can still serve data.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone

import pandas as pd

from . import config

log = logging.getLogger(__name__)

ACTUALS_FILE = "actuals.csv.gz"
FORECASTS_FILE = "forecasts.csv.gz"
META_FILE = "meta.json"


def _utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).astype("datetime64[ns, UTC]")


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.actuals = pd.DataFrame(columns=["start_time", "actual_mw"])
        self.forecasts = pd.DataFrame(columns=["start_time", "publish_time", "forecast_mw"])
        self.meta: dict = {}
        self.status = "empty"  # empty | loading | ready | error
        self.error: str | None = None

    # ---- persistence -------------------------------------------------
    def load_from_disk(self) -> bool:
        a_path, f_path, m_path = (config.DATA_DIR / n for n in (ACTUALS_FILE, FORECASTS_FILE, META_FILE))
        if not (a_path.exists() and f_path.exists()):
            return False
        actuals = pd.read_csv(a_path)
        forecasts = pd.read_csv(f_path)
        actuals["start_time"] = _utc(actuals["start_time"])
        forecasts["start_time"] = _utc(forecasts["start_time"])
        forecasts["publish_time"] = _utc(forecasts["publish_time"])
        meta = json.loads(m_path.read_text()) if m_path.exists() else {}
        self._set(actuals, forecasts, meta)
        return True

    def save_to_disk(self) -> None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.actuals.to_csv(config.DATA_DIR / ACTUALS_FILE, index=False, compression="gzip")
        self.forecasts.to_csv(config.DATA_DIR / FORECASTS_FILE, index=False, compression="gzip")
        (config.DATA_DIR / META_FILE).write_text(json.dumps(self.meta, indent=2))

    def _set(self, actuals: pd.DataFrame, forecasts: pd.DataFrame, meta: dict) -> None:
        with self._lock:
            self.actuals, self.forecasts = actuals, forecasts
            self.meta = {
                **meta,
                "actual_rows": int(len(actuals)),
                "forecast_rows": int(len(forecasts)),
            }
            self.status, self.error = "ready", None

    # ---- refresh -----------------------------------------------------
    def refresh_from_elexon(self) -> None:
        from . import elexon

        self.status, self.error = "loading", None
        try:
            actuals, forecasts = elexon.fetch_all()
            if actuals.empty or forecasts.empty:
                raise RuntimeError("Elexon returned no data for the requested window")
            meta = {"source": "elexon", "fetched_at": datetime.now(timezone.utc).isoformat()}
            self._set(actuals, forecasts, meta)
            self.save_to_disk()
            log.info("Refresh complete: %s actuals, %s forecasts", len(actuals), len(forecasts))
        except Exception as exc:  # surfaced via /api/meta
            log.exception("Refresh failed")
            self.status, self.error = "error", str(exc)

    def refresh_in_background(self) -> bool:
        if self.status == "loading":
            return False
        self.status = "loading"
        threading.Thread(target=self.refresh_from_elexon, daemon=True).start()
        return True

    def load_demo(self) -> None:
        from . import demo

        actuals, forecasts = demo.generate()
        meta = {"source": "demo", "fetched_at": datetime.now(timezone.utc).isoformat()}
        self._set(actuals, forecasts, meta)
        self.save_to_disk()


store = DataStore()
