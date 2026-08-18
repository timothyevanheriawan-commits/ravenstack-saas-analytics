------------------------------------------------------------------------------
-- 03_account_acquisition.sql
------------------------------------------------------------------------------
-- Business Question
--   How does account acquisition change over time, which referral
--   sources bring in the most accounts, and how does acquisition vary
--   by plan, industry, and country?
--
-- Method
--   raw_accounts.signup_date is a clean, complete, 1-row-per-account
--   field, so this is a straightforward date-truncation + GROUP BY
--   exercise. No joins to other tables are needed. Ranking functions
--   are used only where "top N" framing genuinely helps (top referral
--   sources, top industries), not decoratively.
--
-- Grain
--   Varies by query: monthly (Q1), referral source (Q2), plan tier (Q3),
--   industry (Q4), country (Q5). Each query is a separate, independent
--   grain -- they are not meant to be UNIONed together.
--
-- Important Caveats
--   raw_accounts.plan_tier is a static, current-state label on the
--   account, not a historical record of what plan the account signed up
--   on. "Acquisition by plan" here means "current plan tier of accounts
--   acquired in period X," not "plan tier at signup."
------------------------------------------------------------------------------


------------------------------------------------------------------------------
-- Q1: Monthly new account acquisition trend
------------------------------------------------------------------------------
SELECT
    cs.month_label,
    cs.month_start,
    COUNT(a.account_id) AS new_accounts
FROM calendar_month_spine cs
LEFT JOIN raw_accounts a
       ON DATE_TRUNC('month', a.signup_date) = cs.month_start
WHERE cs.month_start <= (SELECT DATE_TRUNC('month', MAX(signup_date)) FROM raw_accounts)
GROUP BY cs.month_label, cs.month_start
ORDER BY cs.month_start;


------------------------------------------------------------------------------
-- Q2: Acquisition by referral source, ranked
------------------------------------------------------------------------------
SELECT
    referral_source,
    COUNT(*) AS accounts_acquired,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_total_accounts,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS acquisition_rank
FROM raw_accounts
GROUP BY referral_source
ORDER BY accounts_acquired DESC;


------------------------------------------------------------------------------
-- Q3: Acquisition by current plan tier
-- Caveat: plan_tier here is the account's static current-state label,
-- not the plan the account was acquired onto.
------------------------------------------------------------------------------
SELECT
    plan_tier,
    COUNT(*) AS account_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_total_accounts
FROM raw_accounts
GROUP BY plan_tier
ORDER BY account_count DESC;


------------------------------------------------------------------------------
-- Q4: Acquisition by industry, ranked, with referral-source breakdown
------------------------------------------------------------------------------
SELECT
    industry,
    COUNT(*) AS account_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_total_accounts,
    COUNT(*) FILTER (WHERE referral_source = 'organic') AS organic_accounts,
    COUNT(*) FILTER (WHERE referral_source = 'partner') AS partner_accounts,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS industry_rank
FROM raw_accounts
GROUP BY industry
ORDER BY account_count DESC;


------------------------------------------------------------------------------
-- Q5: Acquisition by country
------------------------------------------------------------------------------
SELECT
    country,
    COUNT(*) AS account_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_total_accounts,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS country_rank
FROM raw_accounts
GROUP BY country
ORDER BY account_count DESC;


------------------------------------------------------------------------------
-- Q6: Referral source performance by plan tier (conditional aggregation)
-- Shows whether certain acquisition channels skew toward particular plan
-- tiers -- useful for a "which channels bring higher-value accounts"
-- read, while staying inside the "current plan label" caveat above.
------------------------------------------------------------------------------
SELECT
    referral_source,
    COUNT(*) FILTER (WHERE plan_tier = 'Basic')      AS basic_accounts,
    COUNT(*) FILTER (WHERE plan_tier = 'Pro')         AS pro_accounts,
    COUNT(*) FILTER (WHERE plan_tier = 'Enterprise')  AS enterprise_accounts,
    COUNT(*)                                          AS total_accounts
FROM raw_accounts
GROUP BY referral_source
ORDER BY total_accounts DESC;


------------------------------------------------------------------------------
-- VALIDATION: acquisition totals across grains must reconcile to 500
------------------------------------------------------------------------------
SELECT
    (SELECT SUM(new_accounts) FROM (
        SELECT COUNT(a.account_id) AS new_accounts
        FROM calendar_month_spine cs
        LEFT JOIN raw_accounts a ON DATE_TRUNC('month', a.signup_date) = cs.month_start
        WHERE cs.month_start <= (SELECT DATE_TRUNC('month', MAX(signup_date)) FROM raw_accounts)
        GROUP BY cs.month_label
    ) monthly)                                          AS total_via_monthly,
    (SELECT SUM(accounts_acquired) FROM (
        SELECT COUNT(*) AS accounts_acquired FROM raw_accounts GROUP BY referral_source
    ) by_referral)                                       AS total_via_referral_source,
    (SELECT COUNT(*) FROM raw_accounts)                  AS total_accounts_actual;
