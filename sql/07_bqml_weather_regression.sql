-- 07_bqml_weather_regression.sql
-- BigQuery ML linear regression: predict daily ride counts from the
-- weather (average temperature, rainfall, wind) plus calendar features
-- (day of week, month). ML.WEIGHTS then reads as plain English: how
-- many rides one extra degree, or one extra mm of rain, is worth.
-- Replace the project and dataset in the model name with your own.

CREATE OR REPLACE MODEL `your_project.london_bikes.weather_demand_lm`
OPTIONS (
  MODEL_TYPE = 'LINEAR_REG',
  INPUT_LABEL_COLS = ['rides']
) AS
WITH daily AS (
  SELECT DATE(start_date) AS ride_date, COUNT(*) AS rides
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
)
SELECT
  d.rides,
  w.temp_avg_c,
  w.prcp_mm,
  w.wind_kmh,
  EXTRACT(DAYOFWEEK FROM d.ride_date) AS day_of_week,
  EXTRACT(MONTH FROM d.ride_date) AS month
FROM daily d
JOIN weather w ON w.weather_date = d.ride_date;

-- Fit quality on the training data (mean absolute error, R squared).
SELECT *
FROM ML.EVALUATE(MODEL `your_project.london_bikes.weather_demand_lm`);

-- The interpretable part: one row per feature weight.
SELECT
  processed_input,
  weight
FROM ML.WEIGHTS(MODEL `your_project.london_bikes.weather_demand_lm`)
ORDER BY ABS(weight) DESC;
