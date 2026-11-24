#!/usr/bin/env python3
"""Download NOAA GSOD daily weather for London Heathrow (station
03772099999) for 2017-2019 from NOAA NCEI and convert units openly:
temperature Fahrenheit to Celsius, precipitation inches to mm,
wind speed knots to km/h. Missing-value sentinels (9999.9 / 99.99)
are turned into NaN.
"""
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)
STATION = "03772099999"
YEARS = [2017, 2018, 2019]
URL = "https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/{y}/{s}.csv"


def leading_float(x):
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(x))
    return float(m.group(1)) if m else float("nan")


def main():
    frames = []
    for y in YEARS:
        r = requests.get(URL.format(y=y, s=STATION), timeout=120)
        r.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(r.text), dtype=str)
        frames.append(df)
        print(y, len(df), "rows")
    w = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(w["DATE"]).dt.date
    for src, dst in [("TEMP", "temp_avg_c"), ("MAX", "temp_max_c"),
                     ("MIN", "temp_min_c")]:
        v = w[src].map(leading_float)
        v = v.where(v < 9000)
        out[dst] = (v - 32) * 5 / 9
    prcp = w["PRCP"].map(leading_float).where(lambda s: s < 90)
    out["prcp_mm"] = prcp * 25.4
    wdsp = w["WDSP"].map(leading_float).where(lambda s: s < 900)
    out["wind_kmh"] = wdsp * 1.852
    frshtt = w["FRSHTT"].fillna("000000").astype(str).str.zfill(6)
    out["fog"] = frshtt.str[0].astype(int)
    out["rain_flag_gsod"] = frshtt.str[1].astype(int)
    out["rain_day"] = (out["prcp_mm"] > 0).astype(int)
    out = out.sort_values("date")
    out.to_csv(PROC / "weather_daily.csv", index=False)
    print(out.describe().round(2).to_string())
    print("days:", len(out), "| rain days:", int(out["rain_day"].sum()),
          "| missing temp:", int(out["temp_avg_c"].isna().sum()),
          "| missing prcp:", int(out["prcp_mm"].isna().sum()))


if __name__ == "__main__":
    main()
