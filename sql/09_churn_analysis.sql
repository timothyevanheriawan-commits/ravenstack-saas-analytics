------------------------------------------------------------------------------
-- 09_churn_analysis.sql
------------------------------------------------------------------------------
-- Business Question
--   How much churn is occurring, why, when, and does it repeat for the
--   same accounts?
--
-- Method
--   raw_churn_events is used as the sole source of truth throughout this
--   file (see 01_data_quality_checks.sql, check 9, for why
--   raw_accounts.churn_flag is not used). Every metric explicitly states
--   whether it counts EVENTS or unique ACCOUNTS, since the two differ
--   materially here (600 events across 352 unique accounts).
--
-- Grain
--   Varies per query: monthly (Q1), reason code (Q2), plan tier (Q3),
--   time-to-churn (Q4), repeat-churn (Q5), refunds (Q6).
--
-- Important Caveats
--   No churn prediction model is built here. "Preceding upgrade/downgrade
--   indicators" (Q7) describe what proportion of churn events were
--   immediately preceded by an upgrade or downgrade flag on that same
--   churn_events row -- this is a descriptive flag already present in
--   the source data, not a derived prediction.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Churn events over time (monthly), plus unique churned accounts
-- per month for comparison.
------------------------------------------------------------------------------
SELECT
    cs.month_label,
    cs.month_start,
    COUNT(ce.churn_event_id)         AS churn_events,
    COUNT(DISTINCT ce.account_id)    AS unique_churned_accounts
FROM calendar_month_spine cs
LEFT JOIN raw_churn_events ce
       ON DATE_TRUNC('month', ce.churn_date) = cs.month_start
WHERE cs.month_start <= (SELECT DATE_TRUNC('month', MAX(churn_date)) FROM raw_churn_events)
GROUP BY cs.month_label, cs.month_start
ORDER BY cs.month_start;


------------------------------------------------------------------------------
-- Q2: Churn by reason code, ranked
------------------------------------------------------------------------------
SELECT
    reason_code,
    COUNT(*)                                                AS churn_events,
    COUNT(DISTINCT account_id)                               AS unique_accounts,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct_of_all_churn_events,
    RANK() OVER (ORDER BY COUNT(*) DESC)                      AS reason_rank
FROM raw_churn_events
GROUP BY reason_code
ORDER BY churn_events DESC;


------------------------------------------------------------------------------
-- Q3: Churn by account plan tier (joined from raw_accounts; plan_tier
-- here is the account's current static label, not necessarily the plan
-- held at the moment of churn -- documented since account-level
-- plan_tier is a snapshot, not history).
------------------------------------------------------------------------------
SELECT
    a.plan_tier,
    COUNT(ce.churn_event_id)               AS churn_events,
    COUNT(DISTINCT ce.account_id)          AS unique_churned_accounts,
    (SELECT COUNT(*) FROM raw_accounts a2 WHERE a2.plan_tier = a.plan_tier) AS accounts_on_this_plan,
    ROUND(
        100.0 * COUNT(DISTINCT ce.account_id)
        / (SELECT COUNT(*) FROM raw_accounts a2 WHERE a2.plan_tier = a.plan_tier), 1
    ) AS pct_of_plan_accounts_with_churn_event
FROM raw_churn_events ce
JOIN raw_accounts a ON a.account_id = ce.account_id
GROUP BY a.plan_tier
ORDER BY churn_events DESC;


------------------------------------------------------------------------------
-- Q4: Time-to-first-churn -- days between account signup and the
-- account's EARLIEST churn event (only meaningful for accounts with at
-- least one churn event).
------------------------------------------------------------------------------
WITH first_churn AS (
    SELECT
        account_id,
        MIN(churn_date) AS first_churn_date
    FROM raw_churn_events
    GROUP BY account_id
)
SELECT
    a.account_id,
    a.signup_date,
    fc.first_churn_date,
    (fc.first_churn_date - a.signup_date) AS days_to_first_churn
FROM first_churn fc
JOIN raw_accounts a ON a.account_id = fc.account_id
ORDER BY days_to_first_churn;

-- Distribution summary of time-to-first-churn
WITH first_churn AS (
    SELECT account_id, MIN(churn_date) AS first_churn_date
    FROM raw_churn_events
    GROUP BY account_id
),
days_calc AS (
    SELECT (fc.first_churn_date - a.signup_date) AS days_to_first_churn
    FROM first_churn fc
    JOIN raw_accounts a ON a.account_id = fc.account_id
)
SELECT
    MIN(days_to_first_churn)                                          AS min_days,
    ROUND(AVG(days_to_first_churn), 1)                                 AS avg_days,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_first_churn)   AS median_days,
    MAX(days_to_first_churn)                                          AS max_days
FROM days_calc;


------------------------------------------------------------------------------
-- Q5: Repeat churn / reactivation -- accounts with multiple churn events,
-- and how many of those events are flagged as reactivations.
------------------------------------------------------------------------------
SELECT
    events_per_account,
    COUNT(*) AS accounts
FROM (
    SELECT account_id, COUNT(*) AS events_per_account
    FROM raw_churn_events
    GROUP BY account_id
) per_account
GROUP BY events_per_account
ORDER BY events_per_account;

SELECT
    COUNT(*) AS total_churn_events,
    COUNT(*) FILTER (WHERE is_reactivation) AS reactivation_events,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_reactivation) / COUNT(*), 1) AS pct_reactivation_events,
    COUNT(DISTINCT account_id) AS unique_churned_accounts,
    COUNT(DISTINCT account_id) FILTER (
        WHERE account_id IN (
            SELECT account_id FROM raw_churn_events GROUP BY account_id HAVING COUNT(*) > 1
        )
    ) AS repeat_churn_accounts
FROM raw_churn_events;


------------------------------------------------------------------------------
-- Q6: Refund amounts -- total and by reason code
------------------------------------------------------------------------------
SELECT
    reason_code,
    COUNT(*)                          AS churn_events,
    ROUND(SUM(refund_amount_usd), 2)  AS total_refund_usd,
    ROUND(AVG(refund_amount_usd), 2)  AS avg_refund_usd
FROM raw_churn_events
GROUP BY reason_code
ORDER BY total_refund_usd DESC;

SELECT
    ROUND(SUM(refund_amount_usd), 2) AS total_refund_usd_all_events,
    ROUND(AVG(refund_amount_usd), 2) AS avg_refund_usd_per_event
FROM raw_churn_events;


------------------------------------------------------------------------------
-- Q7: Preceding upgrade/downgrade indicators on churn events
-- Descriptive only -- these are source columns on raw_churn_events, not
-- a derived prediction.
------------------------------------------------------------------------------
SELECT
    preceding_upgrade_flag,
    preceding_downgrade_flag,
    COUNT(*) AS churn_events,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_churn_events
FROM raw_churn_events
GROUP BY preceding_upgrade_flag, preceding_downgrade_flag
ORDER BY churn_events DESC;


------------------------------------------------------------------------------
-- VALIDATION: total churn events (600) and unique churned accounts (352)
-- should match data quality check 10's findings; reason_code totals
-- should sum back to 600.
------------------------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM raw_churn_events)                       AS total_churn_events,
    (SELECT COUNT(DISTINCT account_id) FROM raw_churn_events)      AS unique_churned_accounts,
    (SELECT SUM(churn_events) FROM (
        SELECT reason_code, COUNT(*) AS churn_events
        FROM raw_churn_events GROUP BY reason_code
    ) by_reason)                                                   AS total_via_reason_code_sum;
