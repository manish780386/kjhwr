"""Download the January 2026 snapshot from Elexon and store it in backend/data.

    python scripts/fetch_data.py          # real data (needs internet access)
    python scripts/fetch_data.py --demo   # synthetic data, for offline UI work only
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.store import store  # noqa: E402

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    if "--demo" in sys.argv:
        store.load_demo()
        print("Demo snapshot written (synthetic data!).")
    else:
        store.refresh_from_elexon()
        if store.status != "ready":
            sys.exit(f"Fetch failed: {store.error}")
        print(f"Saved {store.meta['actual_rows']} actuals and {store.meta['forecast_rows']} forecast rows.")
