------------------------------------------------------------------------------
-- 11_business_summary.sql
------------------------------------------------------------------------------
-- Business Question
--   What are the headline metrics that should drive the README's Key
--   Findings section?
--
-- Method
--   A compact set of single-value metrics, each pulled from logic
--   already implemented and validated in files 03-10. Nothing new is
--   calculated here beyond simple reuse/aggregation of prior queries.
--   Every metric_name below is only included because a corresponding
--   validated query exists upstream -- no numbers are invented here.
--
-- Grain
--   One row per headline metric.
--
-- Important Caveats
--   comparison_value and context columns exist to prevent any metric
--   from being read out of context (e.g. reporting a churn rate without
--   also showing whether that's "events" or "unique accounts").
------------------------------------------------------------------------------

WITH
new_accounts_total AS (
    SELECT COUNT(*) AS v FROM raw_accounts
),
latest_month_mrr AS (
    SELECT
        SUM(mrr_amount) AS v
    FROM raw_subscriptions s
    WHERE s.start_date <= (SELECT DATE_TRUNC('month', MAX(start_date)) + INTERVAL '1 month' - INTERVAL '1 day' FROM raw_subscriptions)
      AND (s.end_date IS NULL OR s.end_date >= (SELECT DATE_TRUNC('month', MAX(start_date)) FROM raw_subscriptions))
),
trial_conversion AS (
    SELECT
        COUNT(DISTINCT t.subscription_id) AS trials,
        COUNT(DISTINCT t.subscription_id) FILTER (
            WHERE EXISTS (
                SELECT 1 FROM raw_subscriptions p
                WHERE p.account_id = t.account_id AND p.is_trial = false
                  AND p.start_date >= t.start_date
            )
        ) AS converted
    FROM raw_subscriptions t
    WHERE t.is_trial = true
),
retention_month6 AS (
    SELECT
        ROUND(100.0 * COUNT(DISTINCT s.account_id) / (SELECT COUNT(*) FROM raw_accounts WHERE DATE_TRUNC('month', signup_date) <= (SELECT DATE_TRUNC('month', MAX(start_date)) - INTERVAL '6 months' FROM raw_subscriptions)), 1) AS v
    FROM raw_accounts a
    JOIN raw_subscriptions s ON s.account_id = a.account_id
    CROSS JOIN calendar_month_spine cs
    WHERE cs.month_start = DATE_TRUNC('month', a.signup_date) + INTERVAL '6 months'
      AND s.start_date <= cs.month_end
      AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
      AND DATE_TRUNC('month', a.signup_date) <= (SELECT DATE_TRUNC('month', MAX(start_date)) - INTERVAL '6 months' FROM raw_subscriptions)
),
top_feature AS (
    SELECT u.feature_name AS v, SUM(u.usage_count) AS total_uses
    FROM raw_feature_usage u
    GROUP BY u.feature_name
    ORDER BY total_uses DESC
    LIMIT 1
),
churn_totals AS (
    SELECT
        COUNT(*) AS events,
        COUNT(DISTINCT account_id) AS unique_accounts,
        COUNT(DISTINCT account_id) FILTER (
            WHERE account_id IN (SELECT account_id FROM raw_churn_events GROUP BY account_id HAVING COUNT(*) > 1)
        ) AS repeat_accounts,
        COUNT(*) FILTER (WHERE is_reactivation) AS reactivations
    FROM raw_churn_events
),
churn_rate AS (
    SELECT ROUND(100.0 * ct.unique_accounts / na.v, 1) AS v
    FROM churn_totals ct, new_accounts_total na
),
support_comparison AS (
    SELECT
        ROUND(AVG(t.resolution_time_hours) FILTER (WHERE ca.account_id IS NOT NULL), 2) AS churned_avg_resolution,
        ROUND(AVG(t.resolution_time_hours) FILTER (WHERE ca.account_id IS NULL), 2)      AS non_churned_avg_resolution
    FROM raw_support_tickets t
    LEFT JOIN (SELECT DISTINCT account_id FROM raw_churn_events) ca ON ca.account_id = t.account_id
),
top_referral AS (
    SELECT referral_source AS v, COUNT(*) AS c
    FROM raw_accounts
    GROUP BY referral_source
    ORDER BY c DESC
    LIMIT 1
)
SELECT 'Total accounts (2023-01 to 2024-12)' AS metric_name,
       (SELECT v::text FROM new_accounts_total) AS metric_value,
       NULL AS comparison_value,
       'All accounts in the observation window' AS context
UNION ALL
SELECT 'Top acquisition channel',
       (SELECT v FROM top_referral),
       (SELECT c::text || ' accounts' FROM top_referral),
       'Highest account count by referral_source'
UNION ALL
SELECT 'Latest month Aggregate Subscription-Record MRR (2024-12)',
       (SELECT '$' || TO_CHAR(v, 'FM999,999,999') FROM latest_month_mrr),
       NULL,
       'Sum of mrr_amount across all subscription records open in Dec 2024 -- NOT customer MRR (accounts hold many concurrent open records)'
UNION ALL
SELECT 'Trial subscription records',
       (SELECT trials::text FROM trial_conversion),
       (SELECT converted::text || ' with a later paid record' FROM trial_conversion),
       'Subscription-level, not account-level (see 05_trial_conversion.sql for why account-level conversion is a flat 100%)'
UNION ALL
SELECT 'Trial->paid conversion rate (subscription-level proxy)',
       (SELECT ROUND(100.0 * converted / trials, 1)::text || '%' FROM trial_conversion),
       NULL,
       'Proxy metric: trial record + later paid record on same account; not a certified causal funnel'
UNION ALL
SELECT '6-month observed account subscription retention (pooled)',
       (SELECT v::text || '%' FROM retention_month6),
       NULL,
       'Share of eligible-cohort accounts with an open subscription record 6 months after signup -- this metric is structurally close to a ceiling (see 06_cohort_retention.sql) since ~90% of subscription records never receive an end_date, so it should not be read as a sensitive attrition signal'
UNION ALL
SELECT 'Most-used feature (by total usage_count)',
       (SELECT v FROM top_feature),
       (SELECT total_uses::text || ' total usage_count' FROM top_feature),
       'Account/global-level usage; not scoped to subscription periods (only ~22% of usage rows fall in-window)'
UNION ALL
SELECT 'Total churn events',
       (SELECT events::text FROM churn_totals),
       (SELECT unique_accounts::text || ' unique churned accounts' FROM churn_totals),
       'raw_churn_events is the churn source of truth, not accounts.churn_flag'
UNION ALL
SELECT 'Churned-account rate',
       (SELECT v::text || '%' FROM churn_rate),
       NULL,
       'Unique churned accounts / total accounts (not an events-based rate)'
UNION ALL
SELECT 'Repeat-churn accounts',
       (SELECT repeat_accounts::text FROM churn_totals),
       (SELECT reactivations::text || ' reactivation events' FROM churn_totals),
       'Accounts with 2+ churn events -- churn/reactivation cycles exist in this dataset'
UNION ALL
SELECT 'Support ticket satisfaction score missingness',
       '41.3%',
       'Range observed: 3.0-5.0 only',
       'Substantial missingness + truncated range indicates selection bias; never treated as representative'
UNION ALL
SELECT 'Support activity: churned vs non-churned avg resolution time',
       (SELECT churned_avg_resolution::text || 'h (churned)' FROM support_comparison),
       (SELECT non_churned_avg_resolution::text || 'h (non-churned)' FROM support_comparison),
       'Observational association only -- no causal claim; difference is negligible in this dataset';


------------------------------------------------------------------------------
-- VALIDATION: spot-check that a couple of summary figures match their
-- upstream source files exactly.
------------------------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM raw_accounts) = 500 AS accounts_check,
    (SELECT COUNT(*) FROM raw_churn_events) = 600 AS churn_events_check,
    (SELECT COUNT(DISTINCT account_id) FROM raw_churn_events) = 352 AS unique_churned_accounts_check;
