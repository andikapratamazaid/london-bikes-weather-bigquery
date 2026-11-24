-- 02_daily_demand_weather_join.sql
-- The core join of this project: daily Santander Cycles demand from
-- london_bicycles.cycle_hire joined to daily weather at London Heathrow
-- from noaa_gsod. GSOD units are imperial; they are converted here:
-- temperature F to C, precipitation inches to mm, wind knots to km/h.
-- GSOD missing-value sentinels (9999.9 temp, 99.99 prcp) become NULL.

WITH daily_rides AS (
  SELECT
    DATE(start_date) AS ride_date,
    COUNT(*) AS rides,
    AVG(duration) / 60 AS avg_duration_min
  FROM `bigquery-public-data.london_bicycles.cycle_hire`
  WHERE start_date >= TIMESTAMP('2017-01-01')
    AND start_date < TIMESTAMP('2020-01-01')
  GROUP BY ride_date
),
weather AS (
  SELECT
    DATE(CAST(year AS INT64), CAST(mo AS INT64), CAST(da AS INT64)) AS weather_date,
    (NULLIF(temp, 9999.9) - 32) * 5 / 9 AS temp_avg_c,
    (SAFE_CAST(REPLACE(CAST(max AS STRING), '*', '') AS FLOAT64) - 32) * 5 / 9 AS temp_max_c,
    (SAFE_CAST(REPLACE(CAST(min AS STRING), '*', '') AS FLOAT64) - 32) * 5 / 9 AS temp_min_c,
    NULLIF(prcp, 99.99) * 25.4 AS prcp_mm,
    wdsp * 1.852 AS wind_kmh,
    fog
  FROM `bigquery-public-data.noaa_gsod.gsod*`
  WHERE _TABLE_SUFFIX BETWEEN '2017' AND '2019'
    AND stn = '037720'
    AND wban = '99999'
)
SELECT
  r.ride_date,
  EXTRACT(DAYOFWEEK FROM r.ride_date) AS day_of_week,  -- 1 = Sunday
  r.rides,
  r.avg_duration_min,
  w.temp_avg_c,
  w.temp_max_c,
  w.temp_min_c,
  w.prcp_mm,
  w.wind_kmh,
  w.fog,
  IF(w.prcp_mm > 0, 1, 0) AS rain_day
FROM daily_rides r
JOIN weather w
  ON w.weather_date = r.ride_date
ORDER BY r.ride_date;
