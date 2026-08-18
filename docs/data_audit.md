# RavenStack — Data Audit

## Overview

This document records all 16 data quality checks from
`sql/01_data_quality_checks.sql`. For each check: what was tested, what was
found, and what the downstream implication is. No raw data was modified as a
result of any finding — each quirk is treated as a fact about the business
process being modelled, documented here so downstream analyses can be built on
honest assumptions.

---

## Check 1 — Row Counts vs Expected

**Test:** Actual row count matches expected audit figure for each table.

| Table | Expected | Result |
|---|---|---|
| `raw_accounts` | 500 | ✅ 500 |
| `raw_subscriptions` | 5 000 | ✅ 5 000 |
| `raw_feature_usage` | 25 000 | ✅ 25 000 |
| `raw_support_tickets` | 2 000 | ✅ 2 000 |
| `raw_churn_events` | 600 | ✅ 600 |

**Implication:** Load is complete; no rows dropped or duplicated during `\copy`.

---

## Check 2 — Primary Key Uniqueness

**Test:** Declared primary keys are actually unique.

| Column | Rows | Distinct | Unique? |
|---|---|---|---|
| `raw_accounts.account_id` | 500 | 500 | ✅ |
| `raw_subscriptions.subscription_id` | 5 000 | 5 000 | ✅ |
| `raw_support_tickets.ticket_id` | 2 000 | 2 000 | ✅ |
| `raw_churn_events.churn_event_id` | 600 | 600 | ✅ |

**Note:** `raw_feature_usage.usage_id` was intentionally excluded from this
check — see Check 3.

**Implication:** All primary keys can be used safely for joins.

---

## Check 3 — `raw_feature_usage.usage_id` Duplicates

**Test:** Is `usage_id` unique in `raw_feature_usage`?

**Finding:** `usage_id` is **NOT unique**. There are 21 duplicate `usage_id`
values, representing 21 surplus rows (each duplicated `usage_id` appears
exactly twice).

**Implication:** `usage_id` is not declared as a primary key. It cannot be used
as a row-identity key for deduplication without additional logic. The raw table
retains all 25,000 rows; the 21 duplicates are kept because they may represent
distinct usage events assigned the same id upstream.

---

## Check 4 — Foreign Key Referential Integrity

**Test:** Zero orphan rows across all four FK relationships.

| Relationship | Orphan Rows |
|---|---|
| `raw_subscriptions → raw_accounts` | ✅ 0 |
| `raw_feature_usage → raw_subscriptions` | ✅ 0 |
| `raw_support_tickets → raw_accounts` | ✅ 0 |
| `raw_churn_events → raw_accounts` | ✅ 0 |

**Implication:** FK joins are safe throughout. No orphan filtering needed.

---

## Check 5 — Subscription Overlap (Most Important Structural Finding)

**Test:** How many concurrently open subscription records does a typical account
hold?

**Finding:**

| Open sub records per account | Accounts |
|---|---|
| 5 | ~some |
| 6 | ~some |
| … | … |
| 14 | ~some |

Summary: **min = 5, avg ≈ 9, max = 14** open subscription records per account.

**Implication:** This is the single most consequential structural constraint in
the dataset. It rules out computing a meaningful "current subscription per
account," "current plan tier per account," or conventional net-MRR-retention
metric. Every downstream analysis that touches subscriptions is designed to
work within this constraint — specifically, the project computes
**Aggregate Subscription-Record MRR** (sum across all open records) rather than
a per-customer MRR figure. No "current plan" queries are implemented anywhere.

---

## Check 6 — `end_date` NULL Rate

**Test:** What share of subscription records have a NULL `end_date`?

**Finding:** **~90.3%** of `end_date` values are NULL.

**Implication:** NULL `end_date` means the record is still open — it does not
mean the date is unknown or missing. This is confirmed by cross-checking against
`churn_flag` consistency in Check 8. The open-subscription-record definition
used throughout the project is:
`start_date <= month_end AND (end_date IS NULL OR end_date >= month_start)`.

---

## Check 7 — `arr_amount = mrr_amount * 12` Consistency

**Test:** Is `arr_amount` always exactly `mrr_amount * 12`?

**Finding:** **0 mismatched rows** — always true.

**Implication:** `arr_amount` is a fully derived column and carries no
independent signal. It is not used in any downstream analysis.

---

## Check 8 — `is_trial` vs `mrr_amount` and `churn_flag` vs `end_date`

**Test (a):** Does `is_trial = true` always correspond to `mrr_amount = 0`?

**Finding:** **Perfectly consistent** — every trial record has `mrr_amount = 0`
and every paid record has `mrr_amount > 0`.

**Implication:** Trial records carry no MRR. The aggregate MRR trend in
`04_aggregate_mrr.sql` correctly excludes trial records from revenue totals
(they contribute $0 regardless).

**Test (b):** Does `churn_flag = true` at the subscription level correspond to
`end_date IS NOT NULL`?

**Finding:** **Consistent** — subscription-level `churn_flag` and `end_date`
presence agree.

**Implication:** Subscription-level `churn_flag` is internally consistent.
However, account-level `churn_flag` in `raw_accounts` is a separate field that
conflicts with `raw_churn_events` (see Check 9).

---

## Check 9 — `raw_accounts.churn_flag` vs `raw_churn_events` Presence

**Test:** Do `raw_accounts.churn_flag` and the presence of any row in
`raw_churn_events` for the same account agree?

**Finding:** **They conflict substantially.** A meaningful number of accounts
have `churn_flag = true` but no churn event, and vice versa.

**Implication:** `raw_accounts.churn_flag` is **unreliable** as a churn signal.
`raw_churn_events` is used as the sole churn source of truth throughout the
entire project. `raw_accounts.churn_flag` is retained in the raw table as-is
but never queried downstream.

---

## Check 10 — Repeat Churn Events per Account

**Test:** How many accounts have more than one churn event?

**Finding:**
- **600 total churn events** across **352 unique accounts**
- **175 accounts** have 2 or more churn events (repeat churn / reactivation
  cycles)
- **61 reactivation events** (`is_reactivation = true`)

**Implication:** "Churn events" and "unique churned accounts" are always
reported separately in downstream analyses. The two figures differ materially
(600 vs 352) and conflating them would overstate or misrepresent churn
concentration.

---

## Check 11 — Feature Usage Temporal Alignment

**Test:** What share of `raw_feature_usage` rows fall inside their linked
subscription's `[start_date, end_date]` window?

**Finding:** Only **~22%** of usage rows are temporally inside the linked
subscription's active window.

**Implication:** Feature engagement cannot be scoped to subscription periods
reliably. All feature usage analysis in `08_feature_engagement.sql` operates at
the **account/global level** — the FK to `raw_subscriptions` is used purely as
a structural bridge to recover `account_id`, not for temporal subscription-period
scoping.

---

## Check 12 — `satisfaction_score` Missingness and Range

**Test:** What is the NULL rate and observed range of `satisfaction_score`?

**Finding:**
- **~41.3%** of tickets have no `satisfaction_score`
- Observed range (where present): **3.0 – 5.0 only**

**Implication:** The truncated range indicates selection bias — dissatisfied
customers likely under-report or low scores may be filtered upstream. This field
is never treated as representative. Where reported, it is always presented
alongside the missingness rate and the observed-range caveat.

---

## Check 13 — `feedback_text` Missingness on Churn Events

**Test:** What share of churn events have no `feedback_text`?

**Finding:** **~25%** of churn events have NULL `feedback_text`.

**Implication:** Text analysis on `feedback_text` would cover only 75% of
events and is not implemented in this project. The missingness is noted here for
completeness.

---

## Check 14 — Impossible Date Sanity Checks

**Test:** Four impossible-date conditions across three tables.

| Condition | Violations |
|---|---|
| Subscription `end_date < start_date` | ✅ 0 |
| Ticket `closed_at < submitted_at` | ✅ 0 |
| Churn event before account signup | ✅ 0 |
| Subscription start before account signup | ✅ 0 |

**Implication:** All date logic is internally consistent. No date corrections
are needed.

---

## Check 15 — Categorical Value Inventories

**Test:** What are the full domain values for key categorical fields?

**Referral sources (7):** `organic`, `partner`, `direct`, `referral`,
`social`, `event`, `paid_search`

**Plan tiers (3, consistent across accounts and subscriptions):** `Basic`,
`Pro`, `Enterprise`

**Churn reason codes:** `budget_constraints`, `competitor`, `feature_gaps`,
`lack_of_value`, `poor_support`, `product_complexity`, and others.

**Support ticket priorities (4):** `low`, `medium`, `high`, `urgent`

**Implication:** All downstream GROUP BY and FILTER expressions on these fields
are safe — no unexpected null or misspelled category values.

---

## Check 16 — Signup Date vs First Subscription Start Date Gap

**Test:** How tightly coupled are `raw_accounts.signup_date` and an account's
earliest `raw_subscriptions.start_date`?

**Finding:** They are **not tightly coupled**. The gap distribution:

| Gap bucket | Accounts | % |
|---|---|---|
| Same day | ~5% | small minority |
| 1–30 days after | moderate share | |
| 31–90 days after | moderate share | |
| 90+ days after | large share | some gaps up to ~430 days |
| Before signup | some | subscription record predates signup_date |

**Implication:** This is why the pooled cohort retention curve in
`06_cohort_retention.sql` **rises** from ~44% at month 0 to ~99% by month 6,
rather than starting near 100% and declining. The early ramp reflects accounts
still arriving at their first open subscription record in the months following
signup — it is a structural dataset property, not an error. Retention figures
for `months_since_signup` 0–3 should be read as a ramp-up period, not
attrition. This is explicitly documented in the cohort retention output.
