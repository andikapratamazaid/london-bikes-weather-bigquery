#!/usr/bin/env python3
"""Local equivalent of SQL 02-05: join daily demand with Heathrow
weather, quantify weather impact bands, station flow and commuter
patterns. Reads data/processed/, writes data/results/.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
RES = ROOT / "data" / "results"
RES.mkdir(parents=True, exist_ok=True)


def main():
    daily = pd.read_csv(PROC / "daily_rides.csv", parse_dates=["date"])
    weather = pd.read_csv(PROC / "weather_daily.csv", parse_dates=["date"])
    df = daily.merge(weather, on="date", how="inner").sort_values("date")
    # TfL never published extract #49, so 15-21 Mar 2017 (7 days) are
    # absent from the official source: 1,088 of 1,095 days are present.
    assert len(df) == 1088, f"joined days = {len(df)}"
    df["day_of_week"] = df["date"].dt.dayofweek  # 0 = Monday
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    df.to_csv(RES / "daily_demand_weather.csv", index=False)

    # --- weather bands (mirror of SQL 03) ---
    rows = []
    tb = pd.cut(df["temp_avg_c"], [-99, 5, 10, 15, 20, 99],
                labels=["below 5C", "5-10C", "10-15C", "15-20C", "20C and above"])
    for band, g in df.groupby(tb, observed=True):
        rows.append(("temperature", band, len(g), round(g["rides"].mean())))
    rb = pd.cut(df["prcp_mm"], [-0.01, 0, 2, 5, 10, 999],
                labels=["dry (0 mm)", "light (0-2 mm)", "moderate (2-5 mm)",
                        "heavy (5-10 mm)", "very heavy (10+ mm)"])
    for band, g in df.groupby(rb, observed=True):
        rows.append(("rainfall", band, len(g), round(g["rides"].mean())))
    wb = pd.cut(df["wind_kmh"], [0, 10, 20, 30, 999],
                labels=["calm (below 10 km/h)", "breeze (10-20 km/h)",
                        "windy (20-30 km/h)", "strong (30+ km/h)"])
    for band, g in df.groupby(wb, observed=True):
        rows.append(("wind", band, len(g), round(g["rides"].mean())))
    bands = pd.DataFrame(rows, columns=["dimension", "band", "days", "avg_daily_rides"])
    bands.to_csv(RES / "weather_bands.csv", index=False)

    corr = df[["rides", "temp_avg_c", "temp_max_c", "prcp_mm", "wind_kmh"]] \
        .corr()["rides"].drop("rides")
    corr.rename("pearson_r_with_rides").to_csv(RES / "weather_correlations.csv")

    # --- monthly summary ---
    monthly = df.groupby("year_month").agg(
        days=("date", "count"), total_rides=("rides", "sum"),
        avg_daily_rides=("rides", "mean"), avg_temp_c=("temp_avg_c", "mean"),
        total_prcp_mm=("prcp_mm", "sum")).reset_index()
    monthly.to_csv(RES / "monthly_summary.csv", index=False)

    # --- station flow (from processed aggregate) ---
    flow = pd.read_csv(PROC / "station_flow.csv")
    flow["imbalance_ratio"] = (flow["net_flow"].abs() / flow["total_activity"]).round(3)
    flow.head(100).to_csv(RES / "station_flow_top100.csv", index=False)
    busy = flow[flow["total_activity"] >= 20000]
    imbalance_top = busy.reindex(
        busy["imbalance_ratio"].sort_values(ascending=False).index).head(15)
    imbalance_top.to_csv(RES / "station_imbalance_top15.csv", index=False)

    # --- commuter patterns ---
    hourly = pd.read_csv(PROC / "hourly_weekday.csv")
    hourly["day_type"] = np.where(hourly["weekday"] >= 5, "weekend", "weekday")
    hd = hourly.groupby(["day_type", "hour"], as_index=False)["rides"].sum()
    totals = hd.groupby("day_type")["rides"].transform("sum")
    hd["share_pct"] = (hd["rides"] / totals * 100).round(2)
    hd.to_csv(RES / "hourly_daytype.csv", index=False)

    dur_wd = np.load(PROC / "durations_weekday.npy") / 60.0
    dur_we = np.load(PROC / "durations_weekend.npy") / 60.0
    commute_hours = (7, 8, 9, 17, 18, 19)
    cw = {}
    for dt in ("weekday", "weekend"):
        sub = hd[hd["day_type"] == dt]
        cw[dt] = round(sub.loc[sub["hour"].isin(commute_hours), "rides"].sum()
                       / sub["rides"].sum() * 100, 1)
    summary = {
        "total_rides": int(df["rides"].sum()),
        "days": int(len(df)),
        "avg_daily_rides": round(float(df["rides"].mean())),
        "busiest_day": str(df.loc[df["rides"].idxmax(), "date"].date()),
        "busiest_day_rides": int(df["rides"].max()),
        "quietest_day": str(df.loc[df["rides"].idxmin(), "date"].date()),
        "quietest_day_rides": int(df["rides"].min()),
        "stations": int(len(flow)),
        "median_duration_weekday_min": round(float(np.median(dur_wd)), 1),
        "median_duration_weekend_min": round(float(np.median(dur_we)), 1),
        "mean_duration_weekday_min": round(float(dur_wd.mean()), 1),
        "mean_duration_weekend_min": round(float(dur_we.mean()), 1),
        "commute_window_share_weekday_pct": cw["weekday"],
        "commute_window_share_weekend_pct": cw["weekend"],
        "corr_temp": round(float(corr["temp_avg_c"]), 3),
        "corr_prcp": round(float(corr["prcp_mm"]), 3),
        "corr_wind": round(float(corr["wind_kmh"]), 3),
    }
    dry = df[df["prcp_mm"] == 0]["rides"].mean()
    heavy = df[df["prcp_mm"] >= 5]["rides"].mean()
    summary["heavy_rain_vs_dry_pct"] = round((heavy / dry - 1) * 100, 1)
    warm = df[df["temp_avg_c"] >= 20]["rides"].mean()
    cold = df[df["temp_avg_c"] < 5]["rides"].mean()
    summary["warm_vs_cold_pct"] = round((warm / cold - 1) * 100, 1)
    (RES / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
