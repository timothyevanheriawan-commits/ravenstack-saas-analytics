------------------------------------------------------------------------------
-- 07_cohort_observed_value.sql
------------------------------------------------------------------------------
-- Business Question
--   How does observed recurring-revenue value accumulate by signup
--   cohort over the months following signup?
--
-- Method
--   For each (cohort_month, months_since_signup) pair, sum mrr_amount
--   across every open subscription record belonging to accounts in that
--   cohort during that calendar month -- the same "open subscription
--   record" definition used in 04_aggregate_mrr.sql and
--   06_cohort_retention.sql, applied per cohort instead of globally.
--   Cumulative observed MRR is a running SUM of that monthly figure
--   within each cohort, computed with a window function.
--
-- Grain
--   One row per (cohort_month, months_since_signup).
--
-- Important Caveats
--   This is OBSERVED SUBSCRIPTION VALUE, not lifetime value (LTV). The
--   dataset only covers a ~2-year observation window (Jan 2023-Dec
--   2024), cohorts near the end of that window have little observed
--   history, and -- as with 04_aggregate_mrr.sql -- accounts holding
--   multiple concurrently open subscription records have their MRR
--   summed across all of them, so this is not a clean per-customer
--   revenue figure. No extrapolation beyond the observed window is
--   performed anywhere in this file.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Observed subscription value by cohort and months since signup,
-- with cumulative observed MRR via window function.
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT
        account_id,
        DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM cohorts
    GROUP BY cohort_month
),
monthly_open_subs AS (
    SELECT
        c.cohort_month,
        cs.month_start,
        (EXTRACT(YEAR FROM cs.month_start) - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + (EXTRACT(MONTH FROM cs.month_start) - EXTRACT(MONTH FROM c.cohort_month))
            AS months_since_signup,
        s.subscription_id,
        s.mrr_amount
    FROM cohorts c
    JOIN raw_subscriptions s ON s.account_id = c.account_id
    JOIN calendar_month_spine cs
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    WHERE cs.month_start >= c.cohort_month
),
cohort_monthly_value AS (
    SELECT
        cohort_month,
        months_since_signup,
        SUM(mrr_amount) AS observed_subscription_mrr,
        COUNT(DISTINCT subscription_id) AS open_subscription_records
    FROM monthly_open_subs
    WHERE months_since_signup BETWEEN 0 AND 18
    GROUP BY cohort_month, months_since_signup
)
SELECT
    TO_CHAR(cmv.cohort_month, 'YYYY-MM') AS cohort_month,
    cmv.months_since_signup,
    cs.cohort_size,
    cmv.open_subscription_records,
    cmv.observed_subscription_mrr,
    ROUND(cmv.observed_subscription_mrr / cs.cohort_size, 2) AS observed_mrr_per_cohort_account,
    SUM(cmv.observed_subscription_mrr) OVER (
        PARTITION BY cmv.cohort_month
        ORDER BY cmv.months_since_signup
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_observed_mrr
FROM cohort_monthly_value cmv
JOIN cohort_sizes cs ON cs.cohort_month = cmv.cohort_month
ORDER BY cmv.cohort_month, cmv.months_since_signup;


------------------------------------------------------------------------------
-- Q2: Cohort comparison -- total observed value accumulated by each
-- cohort within its first 6 months (only cohorts with at least 6 months
-- of observed history are included, so cohorts aren't unfairly compared
-- against ones that haven't had time to accumulate).
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT account_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
cohort_sizes AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM cohorts
    GROUP BY cohort_month
),
monthly_open_subs AS (
    SELECT
        c.cohort_month,
        (EXTRACT(YEAR FROM cs.month_start) - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + (EXTRACT(MONTH FROM cs.month_start) - EXTRACT(MONTH FROM c.cohort_month))
            AS months_since_signup,
        s.mrr_amount
    FROM cohorts c
    JOIN raw_subscriptions s ON s.account_id = c.account_id
    JOIN calendar_month_spine cs
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    WHERE cs.month_start >= c.cohort_month
),
eligible_cohorts AS (
    -- cohort must be old enough to have reached month 5 within the observed data window
    SELECT cohort_month
    FROM cohort_sizes
    WHERE cohort_month <= (SELECT DATE_TRUNC('month', MAX(start_date)) - INTERVAL '5 months' FROM raw_subscriptions)
)
SELECT
    TO_CHAR(mos.cohort_month, 'YYYY-MM') AS cohort_month,
    cs.cohort_size,
    SUM(mos.mrr_amount) FILTER (WHERE mos.months_since_signup BETWEEN 0 AND 5) AS observed_mrr_first_6_months,
    ROUND(
        SUM(mos.mrr_amount) FILTER (WHERE mos.months_since_signup BETWEEN 0 AND 5) / cs.cohort_size, 2
    ) AS observed_mrr_per_account_first_6_months
FROM monthly_open_subs mos
JOIN cohort_sizes cs ON cs.cohort_month = mos.cohort_month
JOIN eligible_cohorts ec ON ec.cohort_month = mos.cohort_month
GROUP BY mos.cohort_month, cs.cohort_size
ORDER BY mos.cohort_month;


------------------------------------------------------------------------------
-- VALIDATION: sum of cohort observed MRR for a given calendar month
-- should equal the global aggregate subscription MRR for that same
-- month from 04_aggregate_mrr.sql (independent cross-check).
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT account_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
cohort_view AS (
    SELECT
        cs.month_start,
        SUM(s.mrr_amount) AS mrr_via_cohort_path
    FROM cohorts c
    JOIN raw_subscriptions s ON s.account_id = c.account_id
    JOIN calendar_month_spine cs
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    GROUP BY cs.month_start
),
direct_view AS (
    SELECT
        cs.month_start,
        SUM(s.mrr_amount) AS mrr_via_direct_path
    FROM calendar_month_spine cs
    JOIN raw_subscriptions s
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    GROUP BY cs.month_start
)
SELECT
    TO_CHAR(cv.month_start, 'YYYY-MM') AS month,
    cv.mrr_via_cohort_path,
    dv.mrr_via_direct_path,
    (cv.mrr_via_cohort_path = dv.mrr_via_direct_path) AS reconciles
FROM cohort_view cv
JOIN direct_view dv ON dv.month_start = cv.month_start
ORDER BY cv.month_start
LIMIT 24;
