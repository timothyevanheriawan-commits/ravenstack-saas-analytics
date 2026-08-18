------------------------------------------------------------------------------
-- 08_feature_engagement.sql
------------------------------------------------------------------------------
-- Business Question
--   Which features see the most usage, duration, and errors, and does
--   engagement differ between accounts that have churned (per
--   raw_churn_events) and accounts that have not?
--
-- Method
--   Feature usage is joined from raw_feature_usage to raw_subscriptions
--   only to recover account_id (a valid, structural FK relationship),
--   then aggregated at the ACCOUNT/GLOBAL level. As established in data
--   quality check 11, only ~22% of usage rows fall inside their linked
--   subscription's own active date window, so no query in this file
--   filters or groups by subscription-period activity. The join to
--   raw_subscriptions is used purely as a bridge to account_id, which IS
--   a temporally-independent, always-valid relationship (a usage event
--   belongs to the account regardless of which of that account's many
--   subscription records happened to generate it).
--
-- Grain
--   Q1-Q3: one row per feature. Q4: one row per (feature, churn status).
--
-- Important Caveats
--   "Churned account" here means "has at least one row in
--   raw_churn_events" -- consistent with the churn definition used
--   throughout this project. Because usage timing cannot be reliably
--   bounded to a specific subscription period, engagement comparisons
--   between churned and non-churned accounts use ALL observed usage
--   history for the account, not just usage "before churn." This is an
--   account-level association, not a temporally-scoped behavioral
--   signal, and it is not used to claim causation.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Most-used features by total usage volume and duration
------------------------------------------------------------------------------
WITH usage_with_account AS (
    SELECT
        u.feature_name,
        u.usage_count,
        u.usage_duration_secs,
        u.error_count,
        s.account_id
    FROM raw_feature_usage u
    JOIN raw_subscriptions s ON s.subscription_id = u.subscription_id
)
SELECT
    feature_name,
    COUNT(*)                          AS usage_events,
    COUNT(DISTINCT account_id)        AS distinct_accounts_using,
    SUM(usage_count)                  AS total_usage_count,
    SUM(usage_duration_secs)          AS total_duration_secs,
    ROUND(AVG(usage_duration_secs), 1) AS avg_duration_secs_per_event,
    RANK() OVER (ORDER BY SUM(usage_count) DESC) AS usage_volume_rank
FROM usage_with_account
GROUP BY feature_name
ORDER BY total_usage_count DESC;


------------------------------------------------------------------------------
-- Q2: Features with the highest error counts (reliability signal)
------------------------------------------------------------------------------
WITH usage_with_account AS (
    SELECT
        u.feature_name,
        u.error_count,
        u.usage_count,
        s.account_id
    FROM raw_feature_usage u
    JOIN raw_subscriptions s ON s.subscription_id = u.subscription_id
)
SELECT
    feature_name,
    SUM(error_count)                                       AS total_errors,
    SUM(usage_count)                                       AS total_usage_count,
    ROUND(100.0 * SUM(error_count) / NULLIF(SUM(usage_count), 0), 2) AS error_rate_pct,
    RANK() OVER (ORDER BY SUM(error_count) DESC)            AS error_count_rank
FROM usage_with_account
GROUP BY feature_name
ORDER BY total_errors DESC;


------------------------------------------------------------------------------
-- Q3: Beta vs non-beta feature usage and error comparison
------------------------------------------------------------------------------
SELECT
    is_beta_feature,
    COUNT(DISTINCT feature_name)          AS distinct_features,
    COUNT(*)                              AS usage_events,
    SUM(usage_count)                      AS total_usage_count,
    SUM(error_count)                      AS total_errors,
    ROUND(100.0 * SUM(error_count) / NULLIF(SUM(usage_count), 0), 2) AS error_rate_pct
FROM raw_feature_usage
GROUP BY is_beta_feature
ORDER BY is_beta_feature;


------------------------------------------------------------------------------
-- Q4: Feature engagement -- churned vs non-churned accounts
-- "Churned" = account_id appears at least once in raw_churn_events.
-- Uses ALL observed usage history per account (see caveats above).
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
),
usage_with_churn_status AS (
    SELECT
        u.feature_name,
        u.usage_count,
        u.usage_duration_secs,
        s.account_id,
        (ca.account_id IS NOT NULL) AS is_churned_account
    FROM raw_feature_usage u
    JOIN raw_subscriptions s ON s.subscription_id = u.subscription_id
    LEFT JOIN churned_accounts ca ON ca.account_id = s.account_id
)
SELECT
    feature_name,
    is_churned_account,
    COUNT(DISTINCT account_id)         AS distinct_accounts,
    SUM(usage_count)                   AS total_usage_count,
    ROUND(AVG(usage_count), 2)         AS avg_usage_count_per_event,
    ROUND(SUM(usage_count)::numeric / COUNT(DISTINCT account_id), 2) AS usage_per_account
FROM usage_with_churn_status
GROUP BY feature_name, is_churned_account
ORDER BY feature_name, is_churned_account;


------------------------------------------------------------------------------
-- Q5: Overall (not per-feature) engagement summary -- churned vs
-- non-churned accounts, for a top-line comparison.
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
),
usage_with_churn_status AS (
    SELECT
        u.usage_count,
        u.usage_duration_secs,
        u.error_count,
        s.account_id,
        (ca.account_id IS NOT NULL) AS is_churned_account
    FROM raw_feature_usage u
    JOIN raw_subscriptions s ON s.subscription_id = u.subscription_id
    LEFT JOIN churned_accounts ca ON ca.account_id = s.account_id
)
SELECT
    is_churned_account,
    COUNT(DISTINCT account_id)                                  AS accounts,
    COUNT(*)                                                    AS usage_events,
    ROUND(COUNT(*)::numeric / COUNT(DISTINCT account_id), 1)    AS usage_events_per_account,
    ROUND(SUM(usage_count)::numeric / COUNT(DISTINCT account_id), 1) AS usage_count_per_account,
    ROUND(SUM(error_count)::numeric / COUNT(DISTINCT account_id), 2) AS errors_per_account
FROM usage_with_churn_status
GROUP BY is_churned_account
ORDER BY is_churned_account;


------------------------------------------------------------------------------
-- VALIDATION: distinct feature count should equal 40 (per audit); total
-- usage events via this file's account-bridge join should equal 25,000
-- (all rows, since subscription_id is a valid FK with zero orphans).
------------------------------------------------------------------------------
SELECT
    COUNT(DISTINCT u.feature_name) AS distinct_features,
    COUNT(*) AS total_usage_events_after_join
FROM raw_feature_usage u
JOIN raw_subscriptions s ON s.subscription_id = u.subscription_id;
