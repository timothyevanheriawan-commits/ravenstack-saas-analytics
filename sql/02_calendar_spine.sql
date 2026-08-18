------------------------------------------------------------------------------
-- 02_calendar_spine.sql
------------------------------------------------------------------------------
-- Business Question
--   N/A (infrastructure). Several downstream analyses (aggregate MRR,
--   cohort retention, cohort observed value) need a complete list of
--   calendar months to report against -- including months where a
--   metric might legitimately be zero -- rather than only the months
--   that happen to appear in a GROUP BY of the source data.
--
-- Method
--   Generate one row per calendar month spanning the observed data range
--   (account signups run 2023-01 to 2024-12; subscriptions and usage stay
--   within the same window) plus a small buffer, using generate_series.
--   Materialized as a view so it always reflects the current data range
--   without needing to be manually re-dated.
--
-- Grain
--   One row per calendar month.
--
-- Important Caveats
--   The buffer extends 3 months past the latest observed date so that
--   cohort "months since signup" calculations near the end of the
--   observation window don't silently truncate. Months beyond actual
--   data coverage will simply show zero activity downstream -- this is
--   expected, not an error.
------------------------------------------------------------------------------

DROP VIEW IF EXISTS calendar_month_spine CASCADE;

CREATE VIEW calendar_month_spine AS
WITH data_range AS (
    SELECT
        LEAST(
            (SELECT MIN(signup_date) FROM raw_accounts),
            (SELECT MIN(start_date) FROM raw_subscriptions)
        ) AS earliest_date,
        GREATEST(
            (SELECT MAX(signup_date) FROM raw_accounts),
            (SELECT MAX(start_date) FROM raw_subscriptions),
            (SELECT MAX(end_date) FROM raw_subscriptions),
            (SELECT MAX(usage_date) FROM raw_feature_usage),
            (SELECT MAX(churn_date) FROM raw_churn_events)
        ) AS latest_date
)
SELECT
    month_start::date AS month_start,
    (month_start + INTERVAL '1 month' - INTERVAL '1 day')::date AS month_end,
    TO_CHAR(month_start, 'YYYY-MM') AS month_label
FROM data_range,
     generate_series(
         DATE_TRUNC('month', earliest_date),
         DATE_TRUNC('month', latest_date) + INTERVAL '3 months',
         INTERVAL '1 month'
     ) AS month_start
ORDER BY month_start;

-- Validation: spine should have no gaps and cover the full observed range
SELECT
    MIN(month_start) AS spine_starts,
    MAX(month_start) AS spine_ends,
    COUNT(*) AS total_months,
    COUNT(*) - (COUNT(DISTINCT month_start)) AS duplicate_months
FROM calendar_month_spine;
