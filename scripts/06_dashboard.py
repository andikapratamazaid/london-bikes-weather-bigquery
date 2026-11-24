#!/usr/bin/env python3
"""Build the static dashboard page from summary + model metrics."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "results"
OUT = ROOT / "dashboard"
OUT.mkdir(exist_ok=True)

s = json.loads((RES / "summary.json").read_text())
m = json.loads((RES / "model_metrics.json").read_text())
lm = m["regression"]["linear_regression_test_2019"]
fc = m["forecast"]["sarima_holdout"]
nv = m["forecast"]["seasonal_naive_holdout"]


def card(label, value, sub=""):
    return (f'<div class="card"><div class="v">{value}</div>'
            f'<div class="l">{label}</div><div class="s">{sub}</div></div>')


html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>London Bikes x Weather - Demand Dashboard 2017-2019</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;margin:0;background:#f4f6f9;color:#16324f}}
header{{background:#16324f;color:#fff;padding:28px 36px}}
header h1{{margin:0 0 6px;font-size:26px}} header p{{margin:0;opacity:.85}}
.wrap{{max-width:1080px;margin:0 auto;padding:24px 20px 40px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:22px}}
.card{{background:#fff;border-radius:10px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.card .v{{font-size:24px;font-weight:700}} .card .l{{font-size:13px;margin-top:2px}}
.card .s{{font-size:12px;color:#667}}
.panel{{background:#fff;border-radius:10px;padding:20px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}}
.panel h2{{margin-top:0;font-size:18px}} .panel img{{width:100%}}
table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{border-bottom:1px solid #e3e8ef;padding:7px 8px;text-align:left}}
footer{{font-size:12px;color:#778;text-align:center;padding:14px}}
</style></head><body>
<header><h1>London Bikes x Weather</h1>
<p>Santander Cycles demand vs Heathrow weather, 2017-2019.
BigQuery public datasets london_bicycles + noaa_gsod, computed locally from the official TfL and NOAA sources.</p></header>
<div class="wrap">
<div class="cards">
{card("Total rides analysed", f"{s['total_rides']:,}", "2017-2019, official TfL extracts")}
{card("Average rides per day", f"{s['avg_daily_rides']:,}", f"busiest day {s['busiest_day']} ({s['busiest_day_rides']:,})")}
{card("Stations", f"{s['stations']}", "with at least one start or end")}
{card("Temperature correlation", s['corr_temp'], "daily rides vs average temperature")}
{card("Heavy rain effect", f"{s['heavy_rain_vs_dry_pct']}%", "mean daily rides, 5+ mm days vs dry days")}
{card("Warm vs cold days", f"+{s['warm_vs_cold_pct']}%", "20C+ days vs below 5C days")}
</div>
<div class="panel"><h2>Daily demand</h2><img src="../charts/daily_demand_trend.png"></div>
<div class="panel"><h2>Weather impact</h2><img src="../charts/rides_vs_temperature.png">
<img src="../charts/rain_impact.png"></div>
<div class="panel"><h2>Commuter pattern</h2><img src="../charts/hourly_patterns.png">
<p>Weekday rides inside the commute windows (07:00-09:59 and 17:00-19:59) make up
<b>{s['commute_window_share_weekday_pct']}%</b> of weekday rides, against
<b>{s['commute_window_share_weekend_pct']}%</b> at weekends. Median trip duration:
{s['median_duration_weekday_min']} minutes on weekdays, {s['median_duration_weekend_min']} minutes at weekends.</p></div>
<div class="panel"><h2>Busiest stations</h2><img src="../charts/station_flow.png"></div>
<div class="panel"><h2>Models</h2>
<table>
<tr><th>Model</th><th>Evaluation</th><th>MAE</th><th>RMSE</th><th>R2 / MAPE</th></tr>
<tr><td>Weather regression (linear, BigQuery ML equivalent)</td><td>trained 2017-2018, tested on 2019</td>
<td>{lm['mae']:,}</td><td>{lm['rmse']:,}</td><td>R2 {lm['r2']}, MAPE {lm['mape_pct']}%</td></tr>
<tr><td>Demand forecast (SARIMA, ARIMA_PLUS equivalent)</td><td>last 90 days of 2019 held out</td>
<td>{fc['mae']:,}</td><td>{fc['rmse']:,}</td><td>MAPE {fc['mape_pct']}%</td></tr>
<tr><td>Seasonal naive baseline</td><td>same holdout</td>
<td>{nv['mae']:,}</td><td>{nv['rmse']:,}</td><td>MAPE {nv['mape_pct']}%</td></tr>
</table>
<img src="../charts/forecast.png" style="margin-top:14px"></div>
</div>
<footer>Data: Transport for London open data and NOAA GSOD (Heathrow 03772099999).
SQL for the original BigQuery public datasets is in the sql folder of the project.</footer>
</body></html>"""
(OUT / "index.html").write_text(html)
print("dashboard written")
