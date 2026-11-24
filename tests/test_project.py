"""Consistency tests for the London Bikes x Weather project.

These check the pipeline outputs against each other and against
independently known facts about the source data (TfL publishes annual
hire totals of roughly 10-11 million per year for 2017-2019, and
2017-2019 contains exactly 1,095 days).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RES = ROOT / "data" / "results"


@pytest.fixture(scope="module")
def daily():
    return pd.read_csv(PROC / "daily_rides.csv", parse_dates=["date"])


@pytest.fixture(scope="module")
def joined():
    return pd.read_csv(RES / "daily_demand_weather.csv", parse_dates=["date"])


def test_daily_covers_full_window(daily):
    # 1,088 of 1,095 days: TfL never published extract #49, so
    # 15-21 Mar 2017 are absent from the official source itself.
    assert len(daily) == 1088
    assert daily["date"].min() == pd.Timestamp("2017-01-01")
    assert daily["date"].max() == pd.Timestamp("2019-12-31")
    assert daily["date"].is_unique
    missing = pd.date_range("2017-01-01", "2019-12-31").difference(daily["date"])
    assert [str(d.date()) for d in missing] == [
        f"2017-03-{d:02d}" for d in range(15, 22)]


def test_total_rides_plausible(daily):
    total = daily["rides"].sum()
    # TfL annual totals for the scheme are ~10-11M per year in this era.
    assert 28_000_000 < total < 36_000_000


def test_weather_complete():
    w = pd.read_csv(PROC / "weather_daily.csv", parse_dates=["date"])
    assert len(w) == 1095
    assert w["temp_avg_c"].notna().all()
    assert w["prcp_mm"].notna().all()
    # London Heathrow sanity: mild maritime climate.
    assert -6 < w["temp_avg_c"].min() and w["temp_avg_c"].max() < 31
    assert w["prcp_mm"].max() < 60


def test_join_loses_no_days(joined, daily):
    assert len(joined) == len(daily)
    assert joined["rides"].sum() == daily["rides"].sum()


def test_hourly_matrix_reconciles(daily):
    h = pd.read_csv(PROC / "hourly_weekday.csv")
    assert h["rides"].sum() == daily["rides"].sum()
    assert set(h["weekday"]) == set(range(7))
    assert set(h["hour"]) == set(range(24))


def test_station_flow_reconciles(daily):
    f = pd.read_csv(PROC / "station_flow.csv")
    assert f["starts"].sum() == daily["rides"].sum()
    # 65,928 rides (0.21%) have no end station recorded in the source
    # extracts, so ends reconcile to the total minus exactly those.
    assert f["ends"].sum() == daily["rides"].sum() - 65928
    assert len(f) > 700  # the scheme had ~800 stations in this period


def test_durations_split_reconciles(daily):
    wd = np.load(PROC / "durations_weekday.npy")
    we = np.load(PROC / "durations_weekend.npy")
    # Duration arrays hold only rides with a valid (recorded, positive)
    # duration. In the source extracts, 65,346 rides have a blank
    # duration and 5,566 have a zero or negative one (5,492 zero,
    # 74 negative); both groups are excluded from duration statistics
    # but still count as rides.
    assert daily["rides"].sum() - daily["duration_n"].sum() == 65346
    assert daily["duration_n"].sum() - (len(wd) + len(we)) == 5566
    assert (wd > 0).all() and (we > 0).all()
    med_wd, med_we = np.median(wd) / 60, np.median(we) / 60
    assert 5 < med_wd < 30 and 5 < med_we < 40


def test_weather_bands_cover_all_days():
    b = pd.read_csv(RES / "weather_bands.csv")
    for dim in ("temperature", "rainfall", "wind"):
        assert b.loc[b["dimension"] == dim, "days"].sum() == 1088


def test_weather_effects_direction():
    s = json.loads((RES / "summary.json").read_text())
    assert s["corr_temp"] > 0.5        # warmer, more rides
    assert s["corr_prcp"] < 0          # rain suppresses rides
    assert s["heavy_rain_vs_dry_pct"] < -10
    assert s["warm_vs_cold_pct"] > 30


def test_regression_quality():
    m = json.loads((RES / "model_metrics.json").read_text())
    lm = m["regression"]["linear_regression_test_2019"]
    assert lm["r2"] > 0.55
    assert lm["mape_pct"] < 20


def test_forecast_beats_baseline_and_is_plausible():
    m = json.loads((RES / "model_metrics.json").read_text())
    assert (m["forecast"]["sarima_holdout"]["mape_pct"]
            < m["forecast"]["seasonal_naive_holdout"]["mape_pct"])
    fc = pd.read_csv(RES / "forecast_next_90d.csv", parse_dates=["date"])
    assert len(fc) == 90
    assert fc["date"].min() == pd.Timestamp("2020-01-01")
    assert (fc["predicted_rides"] > 5000).all()
    assert (fc["lower_90"] <= fc["predicted_rides"]).all()
    assert (fc["predicted_rides"] <= fc["upper_90"]).all()


def test_sql_files_present_and_on_topic():
    sql = ROOT / "sql"
    files = sorted(sql.glob("*.sql"))
    assert len(files) == 7
    blob = " ".join(f.read_text() for f in files)
    for token in ("london_bicycles.cycle_hire", "noaa_gsod",
                  "ARIMA_PLUS", "ML.FORECAST", "LINEAR_REG", "ML.WEIGHTS"):
        assert token in blob


def test_charts_and_dashboard_exist():
    for name in ("daily_demand_trend.png", "rides_vs_temperature.png",
                 "rain_impact.png", "hourly_patterns.png",
                 "station_flow.png", "forecast.png"):
        p = ROOT / "charts" / name
        assert p.exists() and p.stat().st_size > 10000
    assert (ROOT / "dashboard" / "index.html").exists()
