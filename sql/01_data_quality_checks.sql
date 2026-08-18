------------------------------------------------------------------------------
-- 01_data_quality_checks.sql
------------------------------------------------------------------------------
-- Business Question
--   Is the raw data trustworthy enough, and in what specific ways is it
--   NOT clean, so that every downstream analysis can be built on honest
--   assumptions rather than on a fantasy of a tidy SaaS dataset?
--
-- Method
--   A series of independent diagnostic SELECTs, one per known issue.
--   Nothing here mutates raw data. Every check below exists because it
--   was flagged in the pre-implementation audit; this script re-verifies
--   each finding directly against the loaded database.
--
-- Grain
--   Each check produces its own small result set; there is no single
--   output grain for this file.
--
-- Important Caveats
--   These are diagnostics, not fixes. Anywhere a check surfaces a
--   structural quirk (subscription overlap, unreliable churn_flag,
--   feature usage temporal mismatch), that quirk is treated as a fact
--   about the business process being modeled, not an error to silently
--   correct.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- CHECK 1: Row counts vs expected audit figures
------------------------------------------------------------------------------
SELECT 'raw_accounts'        AS table_name, COUNT(*) AS actual_rows, 500   AS expected_rows FROM raw_accounts
UNION ALL
SELECT 'raw_subscriptions',   COUNT(*), 5000  FROM raw_subscriptions
UNION ALL
SELECT 'raw_feature_usage',   COUNT(*), 25000 FROM raw_feature_usage
UNION ALL
SELECT 'raw_support_tickets', COUNT(*), 2000  FROM raw_support_tickets
UNION ALL
SELECT 'raw_churn_events',    COUNT(*), 600   FROM raw_churn_events;


------------------------------------------------------------------------------
-- CHECK 2: Primary key uniqueness
-- Expectation: account_id, subscription_id, ticket_id, churn_event_id are
-- all unique. usage_id is EXPECTED to have duplicates (see check 3).
------------------------------------------------------------------------------
SELECT 'raw_accounts.account_id' AS key_column,
       COUNT(*) AS total_rows,
       COUNT(DISTINCT account_id) AS distinct_values
FROM raw_accounts
UNION ALL
SELECT 'raw_subscriptions.subscription_id', COUNT(*), COUNT(DISTINCT subscription_id)
FROM raw_subscriptions
UNION ALL
SELECT 'raw_support_tickets.ticket_id', COUNT(*), COUNT(DISTINCT ticket_id)
FROM raw_support_tickets
UNION ALL
SELECT 'raw_churn_events.churn_event_id', COUNT(*), COUNT(DISTINCT churn_event_id)
FROM raw_churn_events;


------------------------------------------------------------------------------
-- CHECK 3: raw_feature_usage.usage_id duplicates
-- Known finding: usage_id is NOT unique. This does not block using the
-- table -- it just means usage_id cannot be used as a row-identity key
-- for downstream deduplication logic without care.
------------------------------------------------------------------------------
SELECT usage_id, COUNT(*) AS occurrences
FROM raw_feature_usage
GROUP BY usage_id
HAVING COUNT(*) > 1
ORDER BY occurrences DESC, usage_id;

-- Summary version: how many usage_id values are duplicated, and how many
-- extra (surplus) rows do they represent?
SELECT
    COUNT(*) FILTER (WHERE occurrences > 1)                       AS duplicated_usage_ids,
    SUM(occurrences - 1) FILTER (WHERE occurrences > 1)            AS surplus_rows
FROM (
    SELECT usage_id, COUNT(*) AS occurrences
    FROM raw_feature_usage
    GROUP BY usage_id
) dupes;


------------------------------------------------------------------------------
-- CHECK 4: Foreign key referential integrity
-- Expectation: zero orphans across all four FK relationships.
------------------------------------------------------------------------------
SELECT 'subscriptions -> accounts' AS relationship, COUNT(*) AS orphan_rows
FROM raw_subscriptions s
LEFT JOIN raw_accounts a ON s.account_id = a.account_id
WHERE a.account_id IS NULL

UNION ALL

SELECT 'feature_usage -> subscriptions', COUNT(*)
FROM raw_feature_usage u
LEFT JOIN raw_subscriptions s ON u.subscription_id = s.subscription_id
WHERE s.subscription_id IS NULL

UNION ALL

SELECT 'support_tickets -> accounts', COUNT(*)
FROM raw_support_tickets t
LEFT JOIN raw_accounts a ON t.account_id = a.account_id
WHERE a.account_id IS NULL

UNION ALL

SELECT 'churn_events -> accounts', COUNT(*)
FROM raw_churn_events c
LEFT JOIN raw_accounts a ON c.account_id = a.account_id
WHERE a.account_id IS NULL;


------------------------------------------------------------------------------
-- CHECK 5: Subscription overlap -- how many concurrently open subscriptions
-- does a typical account have?
-- This is the single most important structural finding in the dataset: it
-- is why no "current subscription per account" metric is implemented
-- anywhere in this project.
------------------------------------------------------------------------------
SELECT
    open_sub_count,
    COUNT(*) AS accounts_with_this_many_open_subs
FROM (
    SELECT account_id, COUNT(*) AS open_sub_count
    FROM raw_subscriptions
    WHERE end_date IS NULL
    GROUP BY account_id
) per_account
GROUP BY open_sub_count
ORDER BY open_sub_count;

-- Distribution summary
SELECT
    MIN(open_sub_count) AS min_open_subs_per_account,
    ROUND(AVG(open_sub_count), 2) AS avg_open_subs_per_account,
    MAX(open_sub_count) AS max_open_subs_per_account
FROM (
    SELECT account_id, COUNT(*) AS open_sub_count
    FROM raw_subscriptions
    WHERE end_date IS NULL
    GROUP BY account_id
) per_account;


------------------------------------------------------------------------------
-- CHECK 6: end_date NULL rate on subscriptions
-- Known finding: ~90.3% of end_date values are NULL. NULL here means
-- "still open," not "unknown" -- confirmed by cross-checking against
-- subscription-level churn_flag in check 8.
------------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_subscriptions,
    COUNT(*) FILTER (WHERE end_date IS NULL) AS open_subscriptions,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE end_date IS NULL) / COUNT(*), 1
    ) AS pct_open
FROM raw_subscriptions;


------------------------------------------------------------------------------
-- CHECK 7: arr_amount = mrr_amount * 12 consistency
-- Known finding: always true. Confirms arr_amount is a fully derived
-- column and therefore not an independent signal.
------------------------------------------------------------------------------
SELECT COUNT(*) AS mismatched_arr_rows
FROM raw_subscriptions
WHERE arr_amount <> mrr_amount * 12;


------------------------------------------------------------------------------
-- CHECK 8: is_trial vs mrr_amount = 0, and churn_flag vs end_date
-- consistency at the subscription grain.
------------------------------------------------------------------------------
SELECT
    is_trial,
    (mrr_amount = 0) AS mrr_is_zero,
    COUNT(*) AS row_count
FROM raw_subscriptions
GROUP BY is_trial, (mrr_amount = 0)
ORDER BY is_trial, mrr_is_zero;

SELECT
    churn_flag,
    (end_date IS NOT NULL) AS has_end_date,
    COUNT(*) AS row_count
FROM raw_subscriptions
GROUP BY churn_flag, (end_date IS NOT NULL)
ORDER BY churn_flag, has_end_date;


------------------------------------------------------------------------------
-- CHECK 9: raw_accounts.churn_flag vs raw_churn_events presence
-- Known finding: these two signals conflict substantially. This is why
-- raw_churn_events, not raw_accounts.churn_flag, is used as the churn
-- source of truth throughout this project.
------------------------------------------------------------------------------
SELECT
    a.churn_flag AS account_churn_flag,
    (ce.account_id IS NOT NULL) AS has_any_churn_event,
    COUNT(*) AS account_count
FROM raw_accounts a
LEFT JOIN (SELECT DISTINCT account_id FROM raw_churn_events) ce
       ON a.account_id = ce.account_id
GROUP BY a.churn_flag, (ce.account_id IS NOT NULL)
ORDER BY account_churn_flag, has_any_churn_event;


------------------------------------------------------------------------------
-- CHECK 10: Repeat churn events per account
-- Known finding: a meaningful share of accounts have 2+ churn events,
-- implying churn/reactivation cycles. This is why "churn events" and
-- "unique churned accounts" are always reported separately downstream.
------------------------------------------------------------------------------
SELECT
    events_per_account,
    COUNT(*) AS accounts_with_this_many_events
FROM (
    SELECT account_id, COUNT(*) AS events_per_account
    FROM raw_churn_events
    GROUP BY account_id
) per_account
GROUP BY events_per_account
ORDER BY events_per_account;


------------------------------------------------------------------------------
-- CHECK 11: Feature usage temporal alignment with linked subscription
-- Known finding: only ~22% of usage rows fall inside their linked
-- subscription's [start_date, end_date] window. This is why feature
-- engagement is analyzed at the account/global level rather than the
-- subscription-period level anywhere in this project.
------------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_usage_rows,
    COUNT(*) FILTER (
        WHERE u.usage_date >= s.start_date
          AND u.usage_date <= COALESCE(s.end_date, DATE '9999-12-31')
    ) AS rows_inside_subscription_window,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE u.usage_date >= s.start_date
              AND u.usage_date <= COALESCE(s.end_date, DATE '9999-12-31')
        ) / COUNT(*), 1
    ) AS pct_inside_window
FROM raw_feature_usage u
JOIN raw_subscriptions s ON u.subscription_id = s.subscription_id;


------------------------------------------------------------------------------
-- CHECK 12: satisfaction_score missingness and range
-- Known finding: ~41% NULL, and observed values only ever fall in
-- [3.0, 5.0] -- consistent with selection bias (dissatisfied customers
-- under-report, or low scores are filtered out upstream). Never treat
-- satisfaction_score as representative of all tickets.
------------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_tickets,
    COUNT(satisfaction_score) AS tickets_with_score,
    COUNT(*) - COUNT(satisfaction_score) AS tickets_missing_score,
    ROUND(100.0 * (COUNT(*) - COUNT(satisfaction_score)) / COUNT(*), 1) AS pct_missing,
    MIN(satisfaction_score) AS min_observed_score,
    MAX(satisfaction_score) AS max_observed_score
FROM raw_support_tickets;


------------------------------------------------------------------------------
-- CHECK 13: feedback_text missingness on churn_events
------------------------------------------------------------------------------
SELECT
    COUNT(*) AS total_churn_events,
    COUNT(feedback_text) AS events_with_feedback,
    COUNT(*) - COUNT(feedback_text) AS events_missing_feedback,
    ROUND(100.0 * (COUNT(*) - COUNT(feedback_text)) / COUNT(*), 1) AS pct_missing
FROM raw_churn_events;


------------------------------------------------------------------------------
-- CHECK 14: Impossible-date sanity checks
-- No subscription should end before it starts; no ticket should close
-- before it opens; no churn event should predate account signup.
------------------------------------------------------------------------------
SELECT 'subscription end before start' AS check_name, COUNT(*) AS violation_count
FROM raw_subscriptions
WHERE end_date IS NOT NULL AND end_date < start_date

UNION ALL

SELECT 'ticket closed before submitted', COUNT(*)
FROM raw_support_tickets
WHERE closed_at < submitted_at

UNION ALL

SELECT 'churn event before account signup', COUNT(*)
FROM raw_churn_events c
JOIN raw_accounts a ON c.account_id = a.account_id
WHERE c.churn_date < a.signup_date

UNION ALL

SELECT 'subscription starts before account signup', COUNT(*)
FROM raw_subscriptions s
JOIN raw_accounts a ON s.account_id = a.account_id
WHERE s.start_date < a.signup_date;


------------------------------------------------------------------------------
-- CHECK 15: Categorical value inventories
-- Confirms cardinalities referenced in the audit (7 referral sources,
-- 3 plan tiers) and surfaces the full domain of reason codes / priorities
-- used elsewhere in the project.
------------------------------------------------------------------------------
SELECT 'referral_source' AS field, referral_source AS value, COUNT(*) AS row_count
FROM raw_accounts GROUP BY referral_source
UNION ALL
SELECT 'plan_tier (accounts)', plan_tier, COUNT(*) FROM raw_accounts GROUP BY plan_tier
UNION ALL
SELECT 'plan_tier (subscriptions)', plan_tier, COUNT(*) FROM raw_subscriptions GROUP BY plan_tier
UNION ALL
SELECT 'reason_code', reason_code, COUNT(*) FROM raw_churn_events GROUP BY reason_code
UNION ALL
SELECT 'priority', priority, COUNT(*) FROM raw_support_tickets GROUP BY priority
ORDER BY field, value;


------------------------------------------------------------------------------
-- CHECK 16: signup_date vs. first subscription start_date gap
-- Discovered while building cohort retention (06_cohort_retention.sql):
-- account signup_date and the account's earliest subscription start_date
-- are NOT tightly coupled. Documented here as a first-class data quality
-- finding because it materially affects how early-month cohort retention
-- figures should be read (see 06_cohort_retention.sql for detail).
------------------------------------------------------------------------------
WITH first_sub AS (
    SELECT account_id, MIN(start_date) AS first_sub_start_date
    FROM raw_subscriptions
    GROUP BY account_id
)
SELECT
    CASE
        WHEN fs.first_sub_start_date < a.signup_date THEN 'before signup'
        WHEN fs.first_sub_start_date = a.signup_date THEN 'same day as signup'
        WHEN fs.first_sub_start_date - a.signup_date <= 30 THEN '1-30 days after signup'
        WHEN fs.first_sub_start_date - a.signup_date <= 90 THEN '31-90 days after signup'
        ELSE '90+ days after signup'
    END AS gap_bucket,
    COUNT(*) AS accounts,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_accounts
FROM raw_accounts a
JOIN first_sub fs ON fs.account_id = a.account_id
GROUP BY 1
ORDER BY 2 DESC;
