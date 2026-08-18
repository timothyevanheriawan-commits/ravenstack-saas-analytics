------------------------------------------------------------------------------
-- 05_trial_conversion.sql
------------------------------------------------------------------------------
-- Business Question
--   Of the trial subscription records created, how many convert to paid,
--   and does that vary by plan tier or signup cohort?
--
-- Method
--   The only funnel stages genuinely observable in this dataset are
--   "trial subscription record exists" (is_trial = true, mrr_amount = 0)
--   and "that same account later holds a paid subscription record"
--   (is_trial = false, mrr_amount > 0). No "activation" event exists in
--   the data, so none is invented.
--
--   Two distinct denominators are reported, and never mixed:
--     (a) SUBSCRIPTION-level: of all trial subscription records, how many
--         accounts holding them also hold at least one paid record with
--         a start_date on or after the trial's start_date (a proxy for
--         "this trial led to a later paid record," since there is no
--         explicit trial->paid link column).
--     (b) ACCOUNT-level: of all accounts that ever had at least one trial
--         subscription record, how many ever had at least one paid
--         subscription record (regardless of ordering).
--
-- Grain
--   Q1/Q2: one row overall / per plan tier (subscription-level).
--   Q3: one row overall (account-level).
--   Q4: one row per signup cohort month (account-level).
--
-- Important Caveats
--   Because accounts hold many concurrently open subscriptions, a trial
--   record and a paid record can coexist for the same account without
--   one having caused the other (e.g. a trial for a new add-on seat
--   while an existing paid plan is also open). The subscription-level
--   metric below is therefore a proxy, not a certified causal funnel --
--   it is explicitly labeled as such. The account-level metric is more
--   conservative and less prone to that ambiguity, which is why both are
--   reported side by side.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Subscription-level conversion proxy, overall
-- Numerator: trial subscription records where the same account has at
-- least one paid subscription record starting on/after the trial's
-- start_date.
------------------------------------------------------------------------------
WITH trial_subs AS (
    SELECT subscription_id, account_id, start_date, plan_tier
    FROM raw_subscriptions
    WHERE is_trial = true
),
paid_subs AS (
    SELECT subscription_id, account_id, start_date
    FROM raw_subscriptions
    WHERE is_trial = false
)
SELECT
    COUNT(DISTINCT t.subscription_id) AS total_trial_subscription_records,
    COUNT(DISTINCT t.subscription_id) FILTER (
        WHERE EXISTS (
            SELECT 1 FROM paid_subs p
            WHERE p.account_id = t.account_id
              AND p.start_date >= t.start_date
        )
    ) AS trial_records_with_later_paid_record,
    ROUND(
        100.0 * COUNT(DISTINCT t.subscription_id) FILTER (
            WHERE EXISTS (
                SELECT 1 FROM paid_subs p
                WHERE p.account_id = t.account_id
                  AND p.start_date >= t.start_date
            )
        ) / COUNT(DISTINCT t.subscription_id), 1
    ) AS subscription_level_conversion_rate_pct
FROM trial_subs t;


------------------------------------------------------------------------------
-- Q2: Subscription-level conversion proxy, by plan tier
------------------------------------------------------------------------------
WITH trial_subs AS (
    SELECT subscription_id, account_id, start_date, plan_tier
    FROM raw_subscriptions
    WHERE is_trial = true
),
paid_subs AS (
    SELECT subscription_id, account_id, start_date
    FROM raw_subscriptions
    WHERE is_trial = false
)
SELECT
    t.plan_tier,
    COUNT(DISTINCT t.subscription_id) AS trial_records,
    COUNT(DISTINCT t.subscription_id) FILTER (
        WHERE EXISTS (
            SELECT 1 FROM paid_subs p
            WHERE p.account_id = t.account_id
              AND p.start_date >= t.start_date
        )
    ) AS trial_records_with_later_paid_record,
    ROUND(
        100.0 * COUNT(DISTINCT t.subscription_id) FILTER (
            WHERE EXISTS (
                SELECT 1 FROM paid_subs p
                WHERE p.account_id = t.account_id
                  AND p.start_date >= t.start_date
            )
        ) / COUNT(DISTINCT t.subscription_id), 1
    ) AS conversion_rate_pct
FROM trial_subs t
GROUP BY t.plan_tier
ORDER BY conversion_rate_pct DESC;


------------------------------------------------------------------------------
-- Q3: Account-level conversion, overall
-- Of accounts that ever had a trial subscription record, how many ever
-- had a paid subscription record (any ordering).
------------------------------------------------------------------------------
WITH account_trial_flag AS (
    SELECT
        account_id,
        BOOL_OR(is_trial = true)  AS ever_had_trial,
        BOOL_OR(is_trial = false) AS ever_had_paid
    FROM raw_subscriptions
    GROUP BY account_id
)
SELECT
    COUNT(*) FILTER (WHERE ever_had_trial)                        AS accounts_with_any_trial,
    COUNT(*) FILTER (WHERE ever_had_trial AND ever_had_paid)       AS accounts_with_trial_and_paid,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE ever_had_trial AND ever_had_paid)
        / NULLIF(COUNT(*) FILTER (WHERE ever_had_trial), 0), 1
    ) AS account_level_conversion_rate_pct
FROM account_trial_flag;


------------------------------------------------------------------------------
-- Q4: Account-level conversion by signup cohort month
------------------------------------------------------------------------------
WITH account_trial_flag AS (
    SELECT
        account_id,
        BOOL_OR(is_trial = true)  AS ever_had_trial,
        BOOL_OR(is_trial = false) AS ever_had_paid
    FROM raw_subscriptions
    GROUP BY account_id
),
cohort AS (
    SELECT
        a.account_id,
        DATE_TRUNC('month', a.signup_date) AS cohort_month
    FROM raw_accounts a
)
SELECT
    TO_CHAR(c.cohort_month, 'YYYY-MM') AS cohort_month,
    COUNT(*) FILTER (WHERE t.ever_had_trial)                      AS accounts_with_any_trial,
    COUNT(*) FILTER (WHERE t.ever_had_trial AND t.ever_had_paid)  AS accounts_with_trial_and_paid,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.ever_had_trial AND t.ever_had_paid)
        / NULLIF(COUNT(*) FILTER (WHERE t.ever_had_trial), 0), 1
    ) AS conversion_rate_pct
FROM cohort c
JOIN account_trial_flag t ON t.account_id = c.account_id
GROUP BY c.cohort_month
ORDER BY c.cohort_month;


------------------------------------------------------------------------------
-- VALIDATION: total trial subscription record count should match the
-- is_trial = true count from the data quality checks (778).
------------------------------------------------------------------------------
SELECT
    COUNT(*) FILTER (WHERE is_trial = true)  AS trial_records_check,
    COUNT(*) FILTER (WHERE is_trial = false) AS paid_records_check
FROM raw_subscriptions;
