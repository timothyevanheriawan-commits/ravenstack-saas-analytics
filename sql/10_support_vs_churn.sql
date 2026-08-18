------------------------------------------------------------------------------
-- 10_support_vs_churn.sql
------------------------------------------------------------------------------
-- Business Question
--   Does observed support activity differ between accounts that have
--   had a churn event and accounts that have not?
--
-- Method
--   Support tickets are joined to accounts, then split into "churned"
--   (account appears at least once in raw_churn_events) vs "not
--   churned," and compared on ticket volume, resolution time,
--   first-response time, and escalation rate. satisfaction_score is
--   handled separately with its missingness explicitly reported,
--   because ~41% of tickets have no score and observed scores only ever
--   fall in [3.0, 5.0] -- a biased subset, not a representative sample.
--
-- Grain
--   Q1/Q2: one row per churn status. Q3: one row per (priority, churn
--   status). Q4: satisfaction-specific, one row per churn status.
--
-- Important Caveats
--   All comparisons in this file are observational associations, phrased
--   as "accounts with churn events had higher/lower observed support
--   activity than accounts without," never as "support activity caused
--   churn" or any other causal claim. Ticket timing is not scoped to
--   before/after the churn event -- a ticket could have been submitted
--   before or after any of an account's churn events -- so this is a
--   whole-account-history comparison, not a pre-churn behavioral signal.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Ticket volume and resolution metrics -- churned vs non-churned
-- accounts
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
),
tickets_with_status AS (
    SELECT
        t.*,
        (ca.account_id IS NOT NULL) AS is_churned_account
    FROM raw_support_tickets t
    LEFT JOIN churned_accounts ca ON ca.account_id = t.account_id
)
SELECT
    is_churned_account,
    COUNT(DISTINCT account_id)                          AS accounts,
    COUNT(*)                                            AS tickets,
    ROUND(COUNT(*)::numeric / COUNT(DISTINCT account_id), 2) AS tickets_per_account,
    ROUND(AVG(resolution_time_hours), 2)                AS avg_resolution_time_hours,
    ROUND(AVG(first_response_time_minutes), 1)          AS avg_first_response_minutes,
    COUNT(*) FILTER (WHERE escalation_flag)             AS escalated_tickets,
    ROUND(100.0 * COUNT(*) FILTER (WHERE escalation_flag) / COUNT(*), 1) AS escalation_rate_pct
FROM tickets_with_status
GROUP BY is_churned_account
ORDER BY is_churned_account;


------------------------------------------------------------------------------
-- Q2: Ticket priority mix -- churned vs non-churned accounts
-- (conditional aggregation)
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
),
tickets_with_status AS (
    SELECT
        t.*,
        (ca.account_id IS NOT NULL) AS is_churned_account
    FROM raw_support_tickets t
    LEFT JOIN churned_accounts ca ON ca.account_id = t.account_id
)
SELECT
    is_churned_account,
    COUNT(*) FILTER (WHERE priority = 'low')     AS low_priority_tickets,
    COUNT(*) FILTER (WHERE priority = 'medium')  AS medium_priority_tickets,
    COUNT(*) FILTER (WHERE priority = 'high')    AS high_priority_tickets,
    COUNT(*) FILTER (WHERE priority = 'urgent')  AS urgent_priority_tickets,
    COUNT(*)                                     AS total_tickets,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE priority IN ('high', 'urgent')) / COUNT(*), 1
    ) AS pct_high_or_urgent
FROM tickets_with_status
GROUP BY is_churned_account
ORDER BY is_churned_account;


------------------------------------------------------------------------------
-- Q3: Resolution time by priority and churn status
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
),
tickets_with_status AS (
    SELECT
        t.*,
        (ca.account_id IS NOT NULL) AS is_churned_account
    FROM raw_support_tickets t
    LEFT JOIN churned_accounts ca ON ca.account_id = t.account_id
)
SELECT
    priority,
    is_churned_account,
    COUNT(*)                             AS tickets,
    ROUND(AVG(resolution_time_hours), 2) AS avg_resolution_time_hours,
    ROUND(AVG(first_response_time_minutes), 1) AS avg_first_response_minutes
FROM tickets_with_status
GROUP BY priority, is_churned_account
ORDER BY priority, is_churned_account;


------------------------------------------------------------------------------
-- Q4: Satisfaction score -- churned vs non-churned accounts, with
-- missingness reported alongside the (biased) observed average.
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
),
tickets_with_status AS (
    SELECT
        t.*,
        (ca.account_id IS NOT NULL) AS is_churned_account
    FROM raw_support_tickets t
    LEFT JOIN churned_accounts ca ON ca.account_id = t.account_id
)
SELECT
    is_churned_account,
    COUNT(*)                                                    AS total_tickets,
    COUNT(satisfaction_score)                                   AS tickets_with_score,
    COUNT(*) - COUNT(satisfaction_score)                        AS tickets_missing_score,
    ROUND(100.0 * (COUNT(*) - COUNT(satisfaction_score)) / COUNT(*), 1) AS pct_missing_score,
    ROUND(AVG(satisfaction_score), 2)                           AS avg_observed_score_biased_sample
FROM tickets_with_status
GROUP BY is_churned_account
ORDER BY is_churned_account;


------------------------------------------------------------------------------
-- VALIDATION: total tickets across the churn-status split should equal
-- 2,000; accounts covered should equal the number of distinct account_ids
-- appearing in raw_support_tickets.
------------------------------------------------------------------------------
WITH churned_accounts AS (
    SELECT DISTINCT account_id FROM raw_churn_events
)
SELECT
    (SELECT COUNT(*) FROM raw_support_tickets)                         AS total_tickets_actual,
    (SELECT SUM(tickets) FROM (
        SELECT (ca.account_id IS NOT NULL) AS is_churned, COUNT(*) AS tickets
        FROM raw_support_tickets t
        LEFT JOIN churned_accounts ca ON ca.account_id = t.account_id
        GROUP BY 1
    ) split)                                                            AS total_via_split,
    (SELECT COUNT(DISTINCT account_id) FROM raw_support_tickets)        AS distinct_accounts_with_tickets;
