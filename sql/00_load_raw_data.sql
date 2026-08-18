------------------------------------------------------------------------------
-- 00_load_raw_data.sql
------------------------------------------------------------------------------
-- Purpose
--   Create raw (source-fidelity) tables for the five RavenStack CSV exports
--   and load them unmodified via \copy. No cleaning, type coercion beyond
--   what is needed to represent the source values, or filtering happens
--   here. This is the "as delivered" layer.
--
-- Grain
--   One table per source CSV, one row per source row.
--
-- Important caveats (see 01_data_quality_checks.sql for evidence)
--   - raw_feature_usage.usage_id is NOT unique (21 duplicate rows).
--     No primary key is declared on usage_id for that reason.
--   - raw_subscriptions.end_date is NULL for ~90% of rows. NULL does not
--     mean "data missing" here -- it means the subscription record has
--     not been closed. Do not backfill or impute this column.
--   - raw_accounts.churn_flag is retained as-is but is NOT used as the
--     churn source of truth anywhere downstream. raw_churn_events is.
--   - Raw tables are never UPDATEd or DELETEd from by later scripts.
--     All downstream transformations live in views/derived tables so the
--     raw layer always reflects the original CSVs.
------------------------------------------------------------------------------

DROP TABLE IF EXISTS raw_feature_usage CASCADE;
DROP TABLE IF EXISTS raw_churn_events CASCADE;
DROP TABLE IF EXISTS raw_support_tickets CASCADE;
DROP TABLE IF EXISTS raw_subscriptions CASCADE;
DROP TABLE IF EXISTS raw_accounts CASCADE;

------------------------------------------------------------------------------
-- raw_accounts
-- Grain: 1 row per account. account_id is unique (confirmed in audit).
------------------------------------------------------------------------------
CREATE TABLE raw_accounts (
    account_id        text        PRIMARY KEY,
    account_name      text        NOT NULL,
    industry          text        NOT NULL,
    country            text        NOT NULL,
    signup_date       date        NOT NULL,
    referral_source   text        NOT NULL,
    plan_tier         text        NOT NULL,   -- static label only; NOT a subscription-history field
    seats             integer     NOT NULL,
    is_trial          boolean     NOT NULL,
    churn_flag        boolean     NOT NULL    -- unreliable; do not use as churn ground truth
);

------------------------------------------------------------------------------
-- raw_subscriptions
-- Grain: 1 row per subscription record. subscription_id is unique.
-- Accounts can, and typically do, have multiple subscription rows open
-- (no end_date) at the same time. Do NOT treat this table as a sequential
-- plan history.
------------------------------------------------------------------------------
CREATE TABLE raw_subscriptions (
    subscription_id    text        PRIMARY KEY,
    account_id          text        NOT NULL REFERENCES raw_accounts(account_id),
    start_date          date        NOT NULL,
    end_date            date,                  -- NULL for ~90% of rows: still open, not missing data
    plan_tier           text        NOT NULL,
    seats               integer     NOT NULL,
    mrr_amount          numeric(12,2) NOT NULL,
    arr_amount           numeric(12,2) NOT NULL, -- always mrr_amount * 12 (confirmed in audit)
    is_trial             boolean     NOT NULL,   -- perfectly consistent with mrr_amount = 0
    upgrade_flag         boolean     NOT NULL,
    downgrade_flag       boolean     NOT NULL,
    churn_flag           boolean     NOT NULL,   -- consistent with end_date, conflicts with raw_accounts.churn_flag
    billing_frequency    text        NOT NULL,
    auto_renew_flag       boolean     NOT NULL
);

------------------------------------------------------------------------------
-- raw_feature_usage
-- Grain: intended to be 1 row per usage event, but usage_id has 21
-- duplicate values, so it is NOT declared unique/primary key here.
-- subscription_id is a valid FK, but only ~22% of rows fall inside the
-- linked subscription's [start_date, end_date] window -- see
-- 01_data_quality_checks.sql. Do not treat this join as temporally valid.
------------------------------------------------------------------------------
CREATE TABLE raw_feature_usage (
    usage_id              text        NOT NULL,  -- not unique -- see data quality checks
    subscription_id        text        NOT NULL REFERENCES raw_subscriptions(subscription_id),
    usage_date             date        NOT NULL,
    feature_name             text        NOT NULL,
    usage_count              integer     NOT NULL,
    usage_duration_secs      integer     NOT NULL,
    error_count               integer     NOT NULL,
    is_beta_feature            boolean     NOT NULL
);

------------------------------------------------------------------------------
-- raw_support_tickets
-- Grain: 1 row per ticket. ticket_id is unique.
-- satisfaction_score has substantial missingness (~41%) and only ranges
-- 3.0-5.0 where present -- treat as a biased, non-representative sample.
------------------------------------------------------------------------------
CREATE TABLE raw_support_tickets (
    ticket_id                      text        PRIMARY KEY,
    account_id                     text        NOT NULL REFERENCES raw_accounts(account_id),
    submitted_at                   timestamp   NOT NULL,
    closed_at                      timestamp   NOT NULL,
    resolution_time_hours          numeric(10,2) NOT NULL,
    priority                       text        NOT NULL,
    first_response_time_minutes    integer     NOT NULL,
    satisfaction_score             numeric(3,1),  -- NULL for ~41% of rows; range 3.0-5.0 only when present
    escalation_flag                boolean     NOT NULL
);

------------------------------------------------------------------------------
-- raw_churn_events
-- Grain: 1 row per churn event. churn_event_id is unique. Accounts can
-- have multiple churn events (repeat churn/reactivation cycles). This is
-- the authoritative churn source of truth for the whole project.
------------------------------------------------------------------------------
CREATE TABLE raw_churn_events (
    churn_event_id              text        PRIMARY KEY,
    account_id                  text        NOT NULL REFERENCES raw_accounts(account_id),
    churn_date                  date        NOT NULL,
    reason_code                 text        NOT NULL,
    refund_amount_usd            numeric(10,2) NOT NULL,
    preceding_upgrade_flag       boolean     NOT NULL,
    preceding_downgrade_flag     boolean     NOT NULL,
    is_reactivation               boolean     NOT NULL,
    feedback_text                 text                  -- NULL for ~25% of rows
);

------------------------------------------------------------------------------
-- Load
-- Run this script with psql from the project root so the relative \copy
-- paths resolve, e.g.:
--   psql -h localhost -U postgres -d ravenstack -f sql/00_load_raw_data.sql
------------------------------------------------------------------------------
\copy raw_accounts        FROM 'data/raw/ravenstack_accounts.csv'        WITH (FORMAT csv, HEADER true);
\copy raw_subscriptions   FROM 'data/raw/ravenstack_subscriptions.csv'   WITH (FORMAT csv, HEADER true);
\copy raw_feature_usage   FROM 'data/raw/ravenstack_feature_usage.csv'   WITH (FORMAT csv, HEADER true);
\copy raw_support_tickets FROM 'data/raw/ravenstack_support_tickets.csv' WITH (FORMAT csv, HEADER true);
\copy raw_churn_events    FROM 'data/raw/ravenstack_churn_events.csv'    WITH (FORMAT csv, HEADER true);

-- Quick row-count sanity check immediately after load
SELECT 'raw_accounts' AS table_name, COUNT(*) AS row_count FROM raw_accounts
UNION ALL SELECT 'raw_subscriptions', COUNT(*) FROM raw_subscriptions
UNION ALL SELECT 'raw_feature_usage', COUNT(*) FROM raw_feature_usage
UNION ALL SELECT 'raw_support_tickets', COUNT(*) FROM raw_support_tickets
UNION ALL SELECT 'raw_churn_events', COUNT(*) FROM raw_churn_events;
