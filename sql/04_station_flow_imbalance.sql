-- 04_station_flow_imbalance.sql
-- Station balance: where rides start vs where they end. A station with a
-- strongly negative net flow (more starts than ends) fills up with empty
-- docks in the morning peak and needs rebalancing vans; the opposite
-- sign fills with bikes. Imbalance ratio = |net| / total activity.

WITH starts AS (
  SELECT start_station_id AS station_id, COUNT(*) AS starts
  FROM `bigquery-public-data.london_bicycles.cycle_hire`
  WHERE start_date >= TIMESTAMP('2017-01-01')
    AND start_date < TIMESTAMP('2020-01-01')
  GROUP BY station_id
),
ends AS (
  SELECT end_station_id AS station_id, COUNT(*) AS ends
  FROM `bigquery-public-data.london_bicycles.cycle_hire`
  WHERE start_date >= TIMESTAMP('2017-01-01')
    AND start_date < TIMESTAMP('2020-01-01')
  GROUP BY station_id
),
flow AS (
  SELECT
    COALESCE(s.station_id, e.station_id) AS station_id,
    IFNULL(s.starts, 0) AS starts,
    IFNULL(e.ends, 0) AS ends
  FROM starts s
  FULL OUTER JOIN ends e USING (station_id)
)
SELECT
  f.station_id,
  cs.name AS station_name,
  cs.latitude,
  cs.longitude,
  f.starts,
  f.ends,
  f.ends - f.starts AS net_flow,
  f.starts + f.ends AS total_activity,
  ROUND(ABS(f.ends - f.starts) / (f.starts + f.ends), 3) AS imbalance_ratio
FROM flow f
LEFT JOIN `bigquery-public-data.london_bicycles.cycle_stations` cs
  ON cs.id = f.station_id
ORDER BY total_activity DESC
LIMIT 100;
