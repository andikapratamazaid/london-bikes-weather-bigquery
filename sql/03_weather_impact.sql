-- 03_weather_impact.sql
-- How demand moves with the weather: average daily rides by temperature
-- band, by rainfall band, and wet vs dry days. Built on the same join
-- as 02_daily_demand_weather_join.sql.

WITH daily AS (
  SELECT
    DATE(start_date) AS ride_date,
    COUNT(*) AS rides
  FROM `bigquery-public-data.london_bicycles.cycle_hire`
  WHERE start_date >= TIMESTAMP('2017-01-01')
    AND start_date < TIMESTAMP('2020-01-01')
  GROUP BY ride_date
),
weather AS (
  SELECT
    DATE(CAST(year AS INT64), CAST(mo AS INT64), CAST(da AS INT64)) AS weather_date,
    (NULLIF(temp, 9999.9) - 32) * 5 / 9 AS temp_avg_c,
    NULLIF(prcp, 99.99) * 25.4 AS prcp_mm,
    wdsp * 1.852 AS wind_kmh
  FROM `bigquery-public-data.noaa_gsod.gsod*`
  WHERE _TABLE_SUFFIX BETWEEN '2017' AND '2019'
    AND stn = '037720'
    AND wban = '99999'
),
joined AS (
  SELECT d.rides, w.temp_avg_c, w.prcp_mm, w.wind_kmh
  FROM daily d
  JOIN weather w ON w.weather_date = d.ride_date
)
-- Temperature bands
SELECT
  'temperature' AS dimension,
  CASE
    WHEN temp_avg_c < 5 THEN 'below 5C'
    WHEN temp_avg_c < 10 THEN '5-10C'
    WHEN temp_avg_c < 15 THEN '10-15C'
    WHEN temp_avg_c < 20 THEN '15-20C'
    ELSE '20C and above'
  END AS band,
  COUNT(*) AS days,
  ROUND(AVG(rides)) AS avg_daily_rides
FROM joined
GROUP BY band

UNION ALL

-- Rainfall bands
SELECT
  'rainfall',
  CASE
    WHEN prcp_mm = 0 THEN 'dry (0 mm)'
    WHEN prcp_mm < 2 THEN 'light (0-2 mm)'
    WHEN prcp_mm < 5 THEN 'moderate (2-5 mm)'
    WHEN prcp_mm < 10 THEN 'heavy (5-10 mm)'
    ELSE 'very heavy (10+ mm)'
  END,
  COUNT(*),
  ROUND(AVG(rides))
FROM joined
GROUP BY band

UNION ALL

-- Wind bands
SELECT
  'wind',
  CASE
    WHEN wind_kmh < 10 THEN 'calm (below 10 km/h)'
    WHEN wind_kmh < 20 THEN 'breeze (10-20 km/h)'
    WHEN wind_kmh < 30 THEN 'windy (20-30 km/h)'
    ELSE 'strong (30+ km/h)'
  END,
  COUNT(*),
  ROUND(AVG(rides))
FROM joined
GROUP BY band
ORDER BY dimension, days DESC;
