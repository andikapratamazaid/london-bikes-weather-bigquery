-- 06_bqml_arima_forecast.sql
-- BigQuery ML time series forecasting: an ARIMA_PLUS model on daily
-- ride counts learns trend, weekly and yearly seasonality and holiday
-- effects, then forecasts the next 90 days. Replace the project and
-- dataset in the model name with your own before running.
--
-- The training input is the daily aggregation of cycle_hire. ARIMA_PLUS
-- auto-selects the ARIMA order and decomposes the series; inspect the
-- chosen model with ML.ARIMA_EVALUATE after training.

CREATE OR REPLACE MODEL `your_project.london_bikes.daily_demand_arima`
OPTIONS (
  MODEL_TYPE = 'ARIMA_PLUS',
  TIME_SERIES_TIMESTAMP_COL = 'ride_date',
  TIME_SERIES_DATA_COL = 'rides',
  HORIZON = 90,
  AUTO_ARIMA = TRUE,
  DATA_FREQUENCY = 'DAILY',
  HOLIDAY_REGION = 'GB'
) AS
SELECT
  DATE(start_date) AS ride_date,
  COUNT(*) AS rides
FROM `bigquery-public-data.london_bicycles.cycle_hire`
WHERE start_date >= TIMESTAMP('2017-01-01')
  AND start_date < TIMESTAMP('2020-01-01')
GROUP BY ride_date;

-- Which ARIMA order and seasonality did the model pick, and how well
-- does it fit the training period?
SELECT *
FROM ML.ARIMA_EVALUATE(MODEL `your_project.london_bikes.daily_demand_arima`);

-- The 90 day forecast with its prediction interval.
SELECT
  forecast_timestamp AS forecast_date,
  forecast_value AS predicted_rides,
  prediction_interval_lower_bound,
  prediction_interval_upper_bound
FROM ML.FORECAST(MODEL `your_project.london_bikes.daily_demand_arima`,
                 STRUCT(90 AS horizon, 0.9 AS confidence_level))
ORDER BY forecast_date;
