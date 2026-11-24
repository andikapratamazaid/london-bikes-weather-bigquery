-- 01_dataset_profile.sql
-- Profile of the two public datasets used in this project.
-- Run in BigQuery (Standard SQL).

-- How big is the cycle hire table, and what period does it cover?
SELECT
  COUNT(*) AS total_rides,
  MIN(start_date) AS first_ride,
  MAX(start_date) AS last_ride,
  COUNT(DISTINCT bike_id) AS distinct_bikes,
  COUNT(DISTINCT start_station_id) AS distinct_start_stations
FROM `bigquery-public-data.london_bicycles.cycle_hire`;

-- Rides per year: the table grows with the scheme.
SELECT
  EXTRACT(YEAR FROM start_date) AS ride_year,
  COUNT(*) AS rides
FROM `bigquery-public-data.london_bicycles.cycle_hire`
GROUP BY ride_year
ORDER BY ride_year;

-- Station inventory.
SELECT
  COUNT(*) AS stations,
  SUM(total_docks) AS total_docks
FROM `bigquery-public-data.london_bicycles.cycle_stations`;

-- Weather coverage for London Heathrow (station 037720, wban 99999)
-- in the NOAA GSOD tables: one row per day.
SELECT
  COUNT(*) AS weather_days,
  MIN(DATE(CAST(year AS INT64), CAST(mo AS INT64), CAST(da AS INT64))) AS first_day,
  MAX(DATE(CAST(year AS INT64), CAST(mo AS INT64), CAST(da AS INT64))) AS last_day
FROM `bigquery-public-data.noaa_gsod.gsod*`
WHERE _TABLE_SUFFIX BETWEEN '2017' AND '2019'
  AND stn = '037720'
  AND wban = '99999';

-- Data quality spot checks on cycle_hire: missing stations, odd durations.
SELECT
  COUNTIF(start_station_id IS NULL) AS missing_start_station,
  COUNTIF(end_station_id IS NULL) AS missing_end_station,
  COUNTIF(duration <= 0) AS non_positive_duration,
  COUNTIF(duration > 86400) AS duration_over_24h
FROM `bigquery-public-data.london_bicycles.cycle_hire`
WHERE start_date >= TIMESTAMP('2017-01-01')
  AND start_date < TIMESTAMP('2020-01-01');
