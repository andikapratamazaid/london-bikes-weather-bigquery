#!/usr/bin/env python3
"""All charts in the README and dashboard are rendered here from the
result CSVs, so every visual is a real analysis output."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "results"
CH = ROOT / "charts"
CH.mkdir(exist_ok=True)
NAVY, TEAL, ORANGE, GREY = "#16324f", "#1b9aaa", "#ef476f", "#8d99ae"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#cccccc",
                     "axes.labelcolor": NAVY, "text.color": NAVY,
                     "xtick.color": "#444444", "ytick.color": "#444444"})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CH / name, dpi=150)
    plt.close(fig)
    print(name)


def main():
    df = pd.read_csv(RES / "daily_demand_weather.csv", parse_dates=["date"])

    # 1. Daily demand trend with 30 day rolling mean
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot(df["date"], df["rides"], color=TEAL, lw=0.5, alpha=0.55)
    ax.plot(df["date"], df["rides"].rolling(30).mean(), color=NAVY, lw=1.8,
            label="30 day rolling mean")
    ax.set_title("Daily Santander Cycles rides, 2017-2019")
    ax.set_ylabel("Rides per day")
    ax.legend(frameon=False)
    save(fig, "daily_demand_trend.png")

    # 2. Rides vs temperature (binned means)
    bins = np.arange(-4, 30, 2)
    df["tbin"] = pd.cut(df["temp_avg_c"], bins)
    g = df.groupby("tbin", observed=True)["rides"].agg(["mean", "count"])
    centres = [(b.left + b.right) / 2 for b in g.index]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.plot(centres, g["mean"], "o-", color=NAVY, lw=2)
    ax.set_title("Warmer days, more rides: mean daily rides by temperature")
    ax.set_xlabel("Average temperature (C)")
    ax.set_ylabel("Mean rides per day")
    save(fig, "rides_vs_temperature.png")

    # 3. Rain impact bars
    bands = pd.read_csv(RES / "weather_bands.csv")
    rb = bands[bands["dimension"] == "rainfall"]
    order = ["dry (0 mm)", "light (0-2 mm)", "moderate (2-5 mm)",
             "heavy (5-10 mm)", "very heavy (10+ mm)"]
    rb = rb.set_index("band").reindex(order)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(range(len(rb)), rb["avg_daily_rides"],
           color=[TEAL, "#57b8c4", "#e0a458", "#e2703a", ORANGE])
    ax.set_xticks(range(len(rb)))
    ax.set_xticklabels(["Dry\n0 mm", "Light\n0-2 mm", "Moderate\n2-5 mm",
                        "Heavy\n5-10 mm", "Very heavy\n10+ mm"], fontsize=8.5)
    ax.set_title("Rain suppresses demand: mean daily rides by rainfall band")
    ax.set_ylabel("Mean rides per day")
    save(fig, "rain_impact.png")

    # 4. Weekday vs weekend hourly pattern
    hd = pd.read_csv(RES / "hourly_daytype.csv")
    present_wd = int((df["date"].dt.dayofweek < 5).sum())
    present_we = int((df["date"].dt.dayofweek >= 5).sum())
    fig, ax = plt.subplots(figsize=(8, 4))
    for dt, color, lab in [("weekday", NAVY, "Weekday"), ("weekend", ORANGE, "Weekend")]:
        sub = hd[hd["day_type"] == dt].sort_values("hour")
        days = present_wd if dt == "weekday" else present_we
        ax.plot(sub["hour"], sub["rides"] / days, "o-", color=color, lw=1.8,
                ms=3.5, label=lab)
    ax.set_title("Two peaks on weekdays, one at weekends: rides per hour")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Rides per hour (per day)")
    ax.set_xticks(range(0, 24, 2))
    ax.legend(frameon=False)
    save(fig, "hourly_patterns.png")

    # 5. Top stations: starts vs ends
    flow = pd.read_csv(RES / "station_flow_top100.csv").head(12)
    flow = flow.iloc[::-1]
    y = np.arange(len(flow))
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.barh(y - 0.2, flow["starts"] / 1000, height=0.4, color=NAVY, label="Starts")
    ax.barh(y + 0.2, flow["ends"] / 1000, height=0.4, color=TEAL, label="Ends")
    ax.set_yticks(y)
    ax.set_yticklabels(flow["station_name"], fontsize=8)
    ax.set_xlabel("Rides 2017-2019 (thousands)")
    ax.set_title("Busiest stations: ride starts vs ends")
    ax.legend(frameon=False)
    save(fig, "station_flow.png")

    # 6. Forecast: last 180 days actual + 90 day forecast
    fc = pd.read_csv(RES / "forecast_next_90d.csv", parse_dates=["date"])
    hist = df[df["date"] >= "2019-07-04"]
    fig, ax = plt.subplots(figsize=(11, 3.8))
    ax.plot(hist["date"], hist["rides"], color=NAVY, lw=1.1, label="Actual")
    ax.plot(fc["date"], fc["predicted_rides"], color=ORANGE, lw=1.6,
            label="SARIMA forecast")
    ax.fill_between(fc["date"], fc["lower_90"], fc["upper_90"],
                    color=ORANGE, alpha=0.18, label="90% interval")
    ax.set_title("Daily demand: actual (Jul-Dec 2019) and forecast (Jan-Mar 2020)")
    ax.set_ylabel("Rides per day")
    ax.legend(frameon=False)
    save(fig, "forecast.png")


if __name__ == "__main__":
    main()
