-- 05_commuter_patterns.sql
-- Commuter vs leisure signatures: rides by hour of day split by weekday
-- and weekend, plus average trip duration for each cell. Weekday demand
-- peaks twice (morning and evening commute); weekend demand peaks once
-- around midday and trips run longer.

SELECT
  IF(EXTRACT(DAYOFWEEK FROM start_date) IN (1, 7), 'weekend', 'weekday') AS day_type,
  EXTRACT(HOUR FROM start_date) AS hour_of_day,
  COUNT(*) AS rides,
  ROUND(AVG(duration) / 60, 1) AS avg_duration_min,
  ROUND(COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY
    IF(EXTRACT(DAYOFWEEK FROM start_date) IN (1, 7), 'weekend', 'weekday')) * 100, 2)
    AS share_of_day_type_pct
FROM `bigquery-public-data.london_bicycles.cycle_hire`
WHERE start_date >= TIMESTAMP('2017-01-01')
  AND start_date < TIMESTAMP('2020-01-01')
GROUP BY day_type, hour_of_day
ORDER BY day_type, hour_of_day;

-- Peak concentration: share of weekday rides inside the two commute
-- windows (07:00-09:59 and 17:00-19:59) vs the same share at weekends.
SELECT
  IF(EXTRACT(DAYOFWEEK FROM start_date) IN (1, 7), 'weekend', 'weekday') AS day_type,
  ROUND(COUNTIF(EXTRACT(HOUR FROM start_date) IN (7, 8, 9, 17, 18, 19))
        / COUNT(*) * 100, 1) AS commute_window_share_pct,
  ROUND(AVG(IF(EXTRACT(HOUR FROM start_date) IN (7, 8, 9, 17, 18, 19),
        duration, NULL)) / 60, 1) AS avg_duration_commute_min,
  ROUND(AVG(IF(EXTRACT(HOUR FROM start_date) NOT IN (7, 8, 9, 17, 18, 19),
        duration, NULL)) / 60, 1) AS avg_duration_other_min
FROM `bigquery-public-data.london_bicycles.cycle_hire`
WHERE start_date >= TIMESTAMP('2017-01-01')
  AND start_date < TIMESTAMP('2020-01-01')
GROUP BY day_type;
