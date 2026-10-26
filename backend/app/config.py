"""Central configuration. Everything can be overridden with environment variables."""
import os
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))

# Elexon Insights (BMRS) API
ELEXON_BASE_URL = os.getenv("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")

# Market clock. Day-ahead bids are placed on D-1 for delivery day D (UK local time).
LOCAL_TZ = "Europe/London"
DEFAULT_CUTOFF = os.getenv("DEFAULT_CUTOFF", "09:00")  # HH:MM local time on D-1
DAYS_AHEAD = 1

# Scope of the pilot: purchase decisions taken in January 2026.
DECISION_START = date(2026, 1, 1)
DECISION_END = date(2026, 1, 31)
DELIVERY_START = date(2026, 1, 2)   # decision on 1 Jan -> delivery on 2 Jan
DELIVERY_END = date(2026, 2, 1)     # decision on 31 Jan -> delivery on 1 Feb

# Forecasts for early delivery days are published up to ~2 weeks earlier.
FORECAST_FETCH_FROM = date(2025, 12, 18)
FORECAST_FETCH_TO = date(2026, 2, 2)

# Serverless platforms (Vercel) have a read-only filesystem and short timeouts,
# so we only serve the committed snapshot there.
AUTO_FETCH = os.getenv("AUTO_FETCH", "1") == "1" and not os.getenv("VERCEL")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

# MAPE is meaningless when actual output is close to zero, so ignore those periods.
MIN_ACTUAL_FOR_MAPE_MW = 500.0
