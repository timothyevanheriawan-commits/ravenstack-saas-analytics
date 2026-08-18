------------------------------------------------------------------------------
-- 04_aggregate_mrr.sql
------------------------------------------------------------------------------
-- Business Question
--   How does total recurring revenue across all open subscription
--   records trend month over month?
--
-- Method
--   Because accounts routinely hold multiple concurrently open
--   subscription records (avg ~9 per account, see data quality check 5),
--   this file deliberately does NOT compute anything resembling a
--   per-account "current MRR". Instead it sums mrr_amount across every
--   subscription record considered open in a given month -- i.e. a
--   subscription with start_date <= month_end AND
--   (end_date IS NULL OR end_date >= month_start) -- and reports that as
--   an aggregate of subscription records, not of customers.
--
-- Grain
--   One row per calendar month.
--
-- Important Caveats
--   This metric is named "Aggregate Subscription-Record MRR" throughout,
--   never "Customer MRR," "Account MRR," or "Net MRR." It double-, triple-
--   , or N-times-counts revenue for any account holding multiple open
--   subscriptions in the same month, by design -- that is what "sum of
--   open subscription records" means. No expansion/contraction/net
--   revenue retention logic is computed anywhere in this file, because
--   that would require a clean sequential per-account plan history,
--   which this dataset does not have.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Aggregate Subscription-Record MRR by month
------------------------------------------------------------------------------
WITH monthly_open_subs AS (
    SELECT
        cs.month_label,
        cs.month_start,
        s.subscription_id,
        s.mrr_amount
    FROM calendar_month_spine cs
    JOIN raw_subscriptions s
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    WHERE cs.month_start <= (SELECT DATE_TRUNC('month', MAX(start_date)) FROM raw_subscriptions)
)
SELECT
    month_label,
    month_start,
    COUNT(DISTINCT subscription_id) AS active_subscription_records,
    SUM(mrr_amount)                  AS aggregate_subscription_mrr
FROM monthly_open_subs
GROUP BY month_label, month_start
ORDER BY month_start;


------------------------------------------------------------------------------
-- Q2: Aggregate Subscription-Record MRR by month, split by plan tier
-- (conditional aggregation, same open-subscription-record logic as Q1)
------------------------------------------------------------------------------
WITH monthly_open_subs AS (
    SELECT
        cs.month_label,
        cs.month_start,
        s.subscription_id,
        s.mrr_amount,
        s.plan_tier
    FROM calendar_month_spine cs
    JOIN raw_subscriptions s
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    WHERE cs.month_start <= (SELECT DATE_TRUNC('month', MAX(start_date)) FROM raw_subscriptions)
)
SELECT
    month_label,
    month_start,
    SUM(mrr_amount) FILTER (WHERE plan_tier = 'Basic')      AS basic_mrr,
    SUM(mrr_amount) FILTER (WHERE plan_tier = 'Pro')         AS pro_mrr,
    SUM(mrr_amount) FILTER (WHERE plan_tier = 'Enterprise')  AS enterprise_mrr,
    SUM(mrr_amount)                                          AS total_mrr
FROM monthly_open_subs
GROUP BY month_label, month_start
ORDER BY month_start;


------------------------------------------------------------------------------
-- Q3: Trial vs paid split of aggregate MRR by month
-- Trial subscriptions always carry mrr_amount = 0 (confirmed in data
-- quality checks), so this mainly surfaces record-count mix, not a
-- revenue split -- included for record-count context alongside Q1.
------------------------------------------------------------------------------
WITH monthly_open_subs AS (
    SELECT
        cs.month_label,
        cs.month_start,
        s.subscription_id,
        s.mrr_amount,
        s.is_trial
    FROM calendar_month_spine cs
    JOIN raw_subscriptions s
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    WHERE cs.month_start <= (SELECT DATE_TRUNC('month', MAX(start_date)) FROM raw_subscriptions)
)
SELECT
    month_label,
    month_start,
    COUNT(*) FILTER (WHERE is_trial)      AS open_trial_records,
    COUNT(*) FILTER (WHERE NOT is_trial)  AS open_paid_records,
    SUM(mrr_amount) FILTER (WHERE NOT is_trial) AS paid_mrr
FROM monthly_open_subs
GROUP BY month_label, month_start
ORDER BY month_start;


------------------------------------------------------------------------------
-- VALIDATION: independent cross-check of the latest month's aggregate MRR
-- using a plain WHERE clause instead of the calendar spine join, and
-- confirm Q1 and Q2's total_mrr agree.
------------------------------------------------------------------------------
WITH latest_month AS (
    SELECT DATE_TRUNC('month', MAX(start_date)) AS month_start
    FROM raw_subscriptions
)
SELECT
    (SELECT SUM(mrr_amount) FROM raw_subscriptions s, latest_month lm
      WHERE s.start_date <= (lm.month_start + INTERVAL '1 month' - INTERVAL '1 day')
        AND (s.end_date IS NULL OR s.end_date >= lm.month_start)
    ) AS latest_month_mrr_direct_calc,
    (SELECT SUM(mrr_amount) FROM raw_subscriptions) AS all_time_sum_mrr_upper_bound;
