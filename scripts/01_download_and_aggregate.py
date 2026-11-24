#!/usr/bin/env python3
"""Download official TfL cycle hire journey extracts (files #38-#194,
covering rides that start 2017-01-01 to 2019-12-31) from the TfL open
data S3 bucket and aggregate them on the fly.

Raw CSVs are kept in data/raw_tfl/ (excluded from the repo ZIP; this
script re-creates them). Aggregates land in data/processed/.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw_tfl"
PROC = ROOT / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)

BUCKET = "https://s3-eu-west-1.amazonaws.com/cycling.data.tfl.gov.uk"
FIRST_FILE, LAST_FILE = 38, 194
START = pd.Timestamp("2017-01-01")
END = pd.Timestamp("2020-01-01")  # exclusive


def list_keys():
    items, token = [], None
    while True:
        url = (f"{BUCKET}/?list-type=2&prefix=usage-stats/&max-keys=1000"
               + (f"&continuation-token={urllib.parse.quote(token)}" if token else ""))
        x = urllib.request.urlopen(url).read().decode()
        for m in re.finditer(r"<Contents><Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", x, re.S):
            items.append((m.group(1), int(m.group(2))))
        t = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", x)
        if "<IsTruncated>true</IsTruncated>" in x and t:
            token = t.group(1)
        else:
            return items


def file_number(key):
    m = re.match(r"usage-stats/(\d+)", key)
    return int(m.group(1)) if m else -1


def download(key, size):
    dest = RAW / Path(key).name
    if dest.exists() and dest.stat().st_size == size:
        return dest
    url = f"{BUCKET}/{urllib.parse.quote(key)}"
    for attempt in range(3):
        try:
            urllib.request.urlretrieve(url, dest)
            if dest.stat().st_size == size:
                return dest
        except Exception as e:  # noqa: BLE001
            print(f"  retry {attempt+1} {key}: {e}", flush=True)
            time.sleep(3)
    raise RuntimeError(f"download failed: {key}")


def norm(col):
    return re.sub(r"[^a-z0-9]", "", col.lower())


def main():
    keys = [(k, s) for k, s in list_keys()
            if FIRST_FILE <= file_number(k) <= LAST_FILE and k.endswith(".csv")]
    keys.sort(key=lambda t: file_number(t[0]))
    print(f"{len(keys)} extract files selected", flush=True)

    daily, hourly, starts, ends = {}, {}, {}, {}
    dur_wd, dur_we = [], []
    total = 0
    for idx, (key, size) in enumerate(keys, 1):
        path = download(key, size)
        df = pd.read_csv(path, usecols=lambda c: norm(c) in {
            "duration", "durationseconds", "startdate", "startstationid",
            "startstationname", "endstationid", "endstationname"},
            low_memory=False)
        df.columns = [norm(c) for c in df.columns]
        # Later extracts name the column Duration_Seconds instead of Duration.
        df = df.rename(columns={"durationseconds": "duration"})
        df["start"] = pd.to_datetime(df["startdate"], format="%d/%m/%Y %H:%M",
                                     errors="coerce")
        df = df.dropna(subset=["start"])
        df = df[(df["start"] >= START) & (df["start"] < END)]
        if df.empty:
            print(f"[{idx}/{len(keys)}] {path.name}: 0 rides in window", flush=True)
            continue
        total += len(df)
        d = df["start"].dt.date
        # Rides are counted with size(): about 1% of rides in the
        # Jan-Jul 2017 extracts have a blank Duration and must still
        # count as rides. Duration sums use only recorded durations.
        g = df.groupby(d).agg(rides=("duration", "size"),
                              dur_sum=("duration", "sum"),
                              dur_n=("duration", "count"))
        for dt, row in g.iterrows():
            a = daily.setdefault(dt, [0, 0, 0])
            a[0] += int(row["rides"]); a[1] += int(row["dur_sum"])
            a[2] += int(row["dur_n"])
        hw = df.groupby([df["start"].dt.day_of_week, df["start"].dt.hour]).size()
        for (wd, hr), c in hw.items():
            hourly[(int(wd), int(hr))] = hourly.get((int(wd), int(hr)), 0) + int(c)
        for col_id, col_name, store in (
                ("startstationid", "startstationname", starts),
                ("endstationid", "endstationname", ends)):
            gg = df.groupby([col_id, col_name]).size()
            for (sid, name), c in gg.items():
                k2 = (int(sid), str(name))
                store[k2] = store.get(k2, 0) + int(c)
        we_mask = (df["start"].dt.day_of_week >= 5).to_numpy()
        # Duration statistics exclude rides whose duration is missing
        # or non-positive (70,912 rides, 0.23%: 65,346 blank in the
        # source extracts, 5,492 recorded as zero, 74 negative).
        dur = df["duration"].to_numpy(dtype=np.float64)
        valid = np.isfinite(dur) & (dur > 0)
        dur_we.append(dur[we_mask & valid].astype(np.int32))
        dur_wd.append(dur[~we_mask & valid].astype(np.int32))
        print(f"[{idx}/{len(keys)}] {path.name}: {len(df):,} rides (total {total:,})",
              flush=True)

    daily_df = pd.DataFrame(
        [(dt, v[0], v[1], v[2]) for dt, v in sorted(daily.items())],
        columns=["date", "rides", "duration_sec_sum", "duration_n"])
    daily_df["avg_duration_min"] = (daily_df["duration_sec_sum"]
                                    / daily_df["duration_n"] / 60)
    daily_df.to_csv(PROC / "daily_rides.csv", index=False)

    hourly_df = pd.DataFrame(
        [(wd, hr, c) for (wd, hr), c in sorted(hourly.items())],
        columns=["weekday", "hour", "rides"])
    hourly_df.to_csv(PROC / "hourly_weekday.csv", index=False)

    sids = set(starts) | set(ends)
    flow = pd.DataFrame([{
        "station_id": sid, "station_name": name,
        "starts": starts.get((sid, name), 0), "ends": ends.get((sid, name), 0),
        "net_flow": ends.get((sid, name), 0) - starts.get((sid, name), 0),
        "total_activity": starts.get((sid, name), 0) + ends.get((sid, name), 0),
    } for sid, name in sids])
    flow = flow.sort_values("total_activity", ascending=False)
    flow.to_csv(PROC / "station_flow.csv", index=False)

    np.save(PROC / "durations_weekday.npy", np.concatenate(dur_wd))
    np.save(PROC / "durations_weekend.npy", np.concatenate(dur_we))
    log = {"files": len(keys), "total_rides": int(total),
           "rides_with_valid_duration": int(daily_df["duration_n"].sum()),
           "days": int(len(daily_df)),
           "stations": int(len(flow)),
           "date_min": str(daily_df["date"].min()),
           "date_max": str(daily_df["date"].max())}
    (PROC / "ingest_log.json").write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    sys.exit(main())
