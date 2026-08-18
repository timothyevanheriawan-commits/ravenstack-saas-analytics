------------------------------------------------------------------------------
-- 06_cohort_retention.sql
------------------------------------------------------------------------------
-- Business Question
--   For accounts grouped by signup month, what share are still active
--   in each subsequent month?
--
-- Method
--   Retention definition (documented explicitly because the standard
--   "still a customer" definition does not cleanly apply to this data):
--
--       An account is considered ACTIVE in a given month if it has at
--       least one subscription record (raw_subscriptions) open during
--       that month, i.e. start_date <= month_end AND
--       (end_date IS NULL OR end_date >= month_start).
--
--   Cohort = calendar month of raw_accounts.signup_date.
--   "Months since cohort" = number of full months between cohort_month
--   and the observation month.
--
-- Grain
--   One row per (cohort_month, months_since_signup).
--
-- Important Caveats
--   Because accounts routinely hold multiple concurrently open
--   subscription records, "active" here means "holds at least one open
--   subscription record" -- not "holds exactly one clean ongoing plan."
--   An account can look "active" under this definition even while
--   several of its subscription records have already churned, as long
--   as at least one other record remains open. This is documented as
--   OBSERVED ACCOUNT SUBSCRIPTION RETENTION, not conventional contractual
--   SaaS retention. Diagnostic columns (avg open subs per active account)
--   are included specifically to keep this structural quirk visible in
--   the output rather than hidden inside a clean-looking percentage.
--
--   Q2's pooled curve is restricted to "eligible" cohorts at each
--   months_since_signup value (see inline note above Q2) to avoid
--   right-censoring bias from immature cohorts. Even so, the resulting
--   curve RISES from 44% (month 0) to ~99% by month 6 and then
--   plateaus near 99-100% -- this is a genuine finding, not a bug: it
--   reflects (a) the signup-date-vs-first-subscription-start_date gap
--   documented in data quality check 16, which depresses early months,
--   and (b) the fact that ~90% of subscription records never receive an
--   end_date, so once an account has any open record it tends to keep
--   showing as "active" under this definition indefinitely. Read this
--   as evidence that OBSERVED ACCOUNT SUBSCRIPTION RETENTION, as
--   defined here, is structurally close to a ceiling effect rather than
--   a curve that meaningfully discriminates true customer attrition --
--   a limitation worth stating plainly in the README rather than
--   presenting a ~99% "retention rate" without this context.
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Cohort retention matrix
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
-- Every (account, month) pair where the account holds at least one open
-- subscription record during that month, plus how many open records it
-- holds (diagnostic).
account_month_activity AS (
    SELECT
        s.account_id,
        cs.month_start,
        COUNT(DISTINCT s.subscription_id) AS open_sub_records
    FROM raw_subscriptions s
    JOIN calendar_month_spine cs
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
    GROUP BY s.account_id, cs.month_start
),
cohort_month_activity AS (
    SELECT
        c.cohort_month,
        ama.month_start AS activity_month,
        -- months_since_signup: full-month difference
        (EXTRACT(YEAR FROM ama.month_start) - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + (EXTRACT(MONTH FROM ama.month_start) - EXTRACT(MONTH FROM c.cohort_month))
            AS months_since_signup,
        c.account_id,
        ama.open_sub_records
    FROM cohorts c
    JOIN account_month_activity ama ON ama.account_id = c.account_id
    WHERE ama.month_start >= c.cohort_month  -- retention looks forward only
)
SELECT
    TO_CHAR(cma.cohort_month, 'YYYY-MM') AS cohort_month,
    cma.months_since_signup,
    cs.cohort_size,
    COUNT(DISTINCT cma.account_id) AS active_accounts,
    ROUND(100.0 * COUNT(DISTINCT cma.account_id) / cs.cohort_size, 1) AS retention_rate_pct,
    ROUND(AVG(cma.open_sub_records), 1) AS avg_open_sub_records_per_active_account
FROM cohort_month_activity cma
JOIN cohort_sizes cs ON cs.cohort_month = cma.cohort_month
WHERE cma.months_since_signup BETWEEN 0 AND 18  -- cap so matrix stays readable; longest cohorts don't yet have more history
GROUP BY cma.cohort_month, cma.months_since_signup, cs.cohort_size
ORDER BY cma.cohort_month, cma.months_since_signup;


------------------------------------------------------------------------------
-- Q2: Pooled retention curve by months-since-signup.
--
-- IMPORTANT METHODOLOGY NOTE: this is deliberately restricted to
-- "eligible" cohorts at each months_since_signup value -- i.e. only
-- cohorts old enough that months_since_signup has actually occurred
-- within the observed subscription date range. A naive version that
-- pools ALL cohorts (including ones too young to have reached that many
-- months yet) would silently count immature cohorts as "not active"
-- for months they haven't lived through, which is right-censoring bias,
-- not real attrition. Both the eligible-only denominator and cohort
-- coverage are reported so the restriction is auditable.
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT
        account_id,
        DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
max_observed_month AS (
    SELECT DATE_TRUNC('month', MAX(start_date)) AS v FROM raw_subscriptions
),
account_month_activity AS (
    SELECT DISTINCT
        s.account_id,
        cs.month_start
    FROM raw_subscriptions s
    JOIN calendar_month_spine cs
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
),
joined AS (
    SELECT
        c.account_id,
        c.cohort_month,
        (EXTRACT(YEAR FROM ama.month_start) - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + (EXTRACT(MONTH FROM ama.month_start) - EXTRACT(MONTH FROM c.cohort_month))
            AS months_since_signup
    FROM cohorts c
    JOIN account_month_activity ama ON ama.account_id = c.account_id
    WHERE ama.month_start >= c.cohort_month
),
eligible_accounts_per_month AS (
    -- For a given months_since_signup value M, an account is "eligible"
    -- only if its cohort_month + M months falls at or before the latest
    -- month with observed subscription data. This is account-level (not
    -- just a count) so it can be joined against `joined` below to keep
    -- the numerator and denominator on the exact same population.
    SELECT
        m.months_since_signup,
        c.account_id
    FROM (SELECT generate_series(0, 18) AS months_since_signup) m
    CROSS JOIN cohorts c
    CROSS JOIN max_observed_month mo
    WHERE c.cohort_month + (m.months_since_signup || ' months')::interval <= mo.v
)
SELECT
    e.months_since_signup,
    COUNT(DISTINCT e.account_id) AS eligible_accounts,
    COUNT(DISTINCT j.account_id) AS active_accounts,
    ROUND(
        100.0 * COUNT(DISTINCT j.account_id) / COUNT(DISTINCT e.account_id), 1
    ) AS retention_rate_pct_eligible_cohorts_only
FROM eligible_accounts_per_month e
LEFT JOIN joined j
       ON j.account_id = e.account_id
      AND j.months_since_signup = e.months_since_signup
GROUP BY e.months_since_signup
ORDER BY e.months_since_signup;


------------------------------------------------------------------------------
-- VALIDATION: independent cross-check of the month-6 eligible-cohort
-- retention rate against 11_business_summary.sql, which computes the
-- same figure via a differently-structured query.
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT account_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
max_observed_month AS (
    SELECT DATE_TRUNC('month', MAX(start_date)) AS v FROM raw_subscriptions
),
eligible AS (
    SELECT c.account_id, c.cohort_month
    FROM cohorts c, max_observed_month mo
    WHERE c.cohort_month + INTERVAL '6 months' <= mo.v
),
active_at_month_6 AS (
    SELECT DISTINCT e.account_id
    FROM eligible e
    JOIN raw_subscriptions s ON s.account_id = e.account_id
    JOIN calendar_month_spine cs ON cs.month_start = e.cohort_month + INTERVAL '6 months'
    WHERE s.start_date <= cs.month_end
      AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
)
SELECT
    (SELECT COUNT(*) FROM eligible)          AS eligible_accounts_month6,
    (SELECT COUNT(*) FROM active_at_month_6) AS active_accounts_month6,
    ROUND(100.0 * (SELECT COUNT(*) FROM active_at_month_6) / (SELECT COUNT(*) FROM eligible), 1)
        AS retention_rate_pct_cross_check;


------------------------------------------------------------------------------
-- Q3: Diagnostic -- how many accounts have ZERO months where they show as
-- "active" under this definition (sanity check; should be close to zero
-- since every account has at least one subscription record by FK design,
-- but months_since_signup could still exclude edge cases at the very
-- final observed month).
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT account_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
ever_active AS (
    SELECT DISTINCT account_id
    FROM raw_subscriptions
)
SELECT
    COUNT(*) FILTER (WHERE ea.account_id IS NULL) AS accounts_never_active,
    COUNT(*) FILTER (WHERE ea.account_id IS NOT NULL) AS accounts_active_at_least_once
FROM cohorts c
LEFT JOIN ever_active ea ON ea.account_id = c.account_id;


------------------------------------------------------------------------------
-- VALIDATION: what share of accounts show as active in their own signup
-- month?
--
-- FINDING (not an assumption -- verified against the data): this is only
-- ~44%, not ~100%. signup_date and the first subscription's start_date
-- are NOT tightly coupled -- for many accounts the first subscription
-- record begins weeks or months after signup_date (gap up to ~430 days
-- across the dataset; only ~5% of accounts have a subscription starting
-- on their exact signup date). This is precisely why the pooled
-- retention curve in Q2 RISES from month 0 to a peak around month 3-4
-- before declining -- accounts are still "arriving" at their first open
-- subscription record in the early months of the curve. This is
-- documented here rather than treated as a bug: it is a real structural
-- property of the dataset (signup_date marks account creation, not
-- subscription start), and it means retention figures for
-- months_since_signup 0-3 should be read as "ramp-up," not attrition.
------------------------------------------------------------------------------
WITH cohorts AS (
    SELECT account_id, DATE_TRUNC('month', signup_date) AS cohort_month
    FROM raw_accounts
),
account_month_activity AS (
    SELECT DISTINCT s.account_id, cs.month_start
    FROM raw_subscriptions s
    JOIN calendar_month_spine cs
      ON s.start_date <= cs.month_end
     AND (s.end_date IS NULL OR s.end_date >= cs.month_start)
)
SELECT
    COUNT(*) AS total_accounts,
    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1 FROM account_month_activity ama
            WHERE ama.account_id = c.account_id
              AND ama.month_start = c.cohort_month
        )
    ) AS accounts_active_in_own_signup_month
FROM cohorts c;
