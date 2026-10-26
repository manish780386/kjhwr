import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import forecast  # noqa: E402


def ts(s):
    return pd.Timestamp(s, tz="UTC")


def make_forecasts(rows):
    df = pd.DataFrame(rows, columns=["start_time", "publish_time", "forecast_mw"])
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True).astype("datetime64[ns, UTC]")
    df["publish_time"] = pd.to_datetime(df["publish_time"], utc=True).astype("datetime64[ns, UTC]")
    return df


def test_picks_latest_forecast_at_or_before_cutoff():
    target = "2026-01-02 12:00"
    f = make_forecasts(
        [
            (target, "2026-01-01 07:00", 100),
            (target, "2026-01-01 08:59", 200),
            (target, "2026-01-01 09:00", 300),  # exactly on the cutoff -> still allowed
            (target, "2026-01-01 09:01", 400),  # after the cutoff -> must be ignored
            (target, "2026-01-02 06:00", 500),  # far too late
        ]
    )
    out = forecast.select_latest_before_cutoff(f, "09:00")
    assert len(out) == 1
    assert out.iloc[0]["forecast_mw"] == 300
    assert out.iloc[0]["publish_time"] == ts("2026-01-01 09:00")


def test_each_target_uses_its_own_previous_day_cutoff():
    f = make_forecasts(
        [
            ("2026-01-02 00:00", "2026-01-01 08:00", 10),  # delivery 2 Jan -> cutoff 1 Jan 09:00
            ("2026-01-03 00:00", "2026-01-01 08:00", 20),
            ("2026-01-03 00:00", "2026-01-02 08:30", 30),  # delivery 3 Jan -> cutoff 2 Jan 09:00
        ]
    )
    out = forecast.select_latest_before_cutoff(f, "09:00").set_index("start_time")["forecast_mw"]
    assert out[ts("2026-01-02 00:00")] == 10
    assert out[ts("2026-01-03 00:00")] == 30


def test_target_with_only_late_forecasts_is_dropped():
    f = make_forecasts([("2026-01-02 12:00", "2026-01-01 10:00", 1)])
    assert forecast.select_latest_before_cutoff(f, "09:00").empty


def test_cutoff_is_in_uk_local_time_during_bst():
    assert forecast.cutoff_utc(pd.Timestamp("2026-07-02").date(), "09:00") == ts("2026-07-01 08:00")
    assert forecast.cutoff_utc(pd.Timestamp("2026-01-02").date(), "09:00") == ts("2026-01-01 09:00")


def test_invalid_cutoff_rejected():
    with pytest.raises(ValueError):
        forecast.parse_cutoff("9am")


def test_select_by_lead_time():
    target = "2026-01-05 12:00"
    f = make_forecasts(
        [
            (target, "2026-01-04 11:00", 1),  # 25h ahead
            (target, "2026-01-04 12:00", 2),  # exactly 24h ahead
            (target, "2026-01-04 13:00", 3),  # 23h ahead -> too fresh for a 24h rule
        ]
    )
    out = forecast.select_by_lead_time(f, 24)
    assert out.iloc[0]["forecast_mw"] == 2


def test_metrics_values():
    actuals = pd.DataFrame({"start_time": pd.date_range("2026-01-02", periods=4, freq="30min", tz="UTC"), "actual_mw": [1000.0, 1000.0, 1000.0, 1000.0]})
    actuals["start_time"] = actuals["start_time"].astype("datetime64[ns, UTC]")
    selected = pd.DataFrame(
        {"start_time": actuals["start_time"], "publish_time": ts("2026-01-01 08:00"), "forecast_mw": [1100.0, 900.0, 1300.0, 1000.0]}
    )
    selected["publish_time"] = selected["publish_time"].astype("datetime64[ns, UTC]")
    df = forecast.build_comparison(actuals, selected)
    m = forecast.compute_metrics(df)
    assert m["n"] == 4
    assert m["mae"] == pytest.approx(125.0)
    assert m["rmse"] == pytest.approx(np.sqrt((100**2 + 100**2 + 300**2) / 4))
    assert m["bias"] == pytest.approx(75.0)
    assert m["over_share_pct"] == pytest.approx(50.0)
    assert m["mape_pct"] == pytest.approx(12.5)


def test_metrics_empty():
    assert forecast.compute_metrics(pd.DataFrame({"forecast_mw": [], "actual_mw": [], "error": [], "abs_error": []}))["n"] == 0
