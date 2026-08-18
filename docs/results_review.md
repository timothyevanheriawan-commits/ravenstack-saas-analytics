# RavenStack — Results Review

All figures below come from `sql/11_business_summary_output.txt`, which is the
validated output of `sql/11_business_summary.sql`. Three independent validation
checks at the end of that file all returned `t` (true). Cross-references to
source SQL files are provided for every metric.

---

## Validated Summary Table

| Metric | Value | Comparison | Source |
|---|---|---|---|
| Total accounts (2023-01 to 2024-12) | **500** | — | `03_account_acquisition.sql` |
| Top acquisition channel | **organic** | 114 accounts | `03_account_acquisition.sql` Q2 |
| Latest month Aggregate Subscription-Record MRR (2024-12) | **$10,734,251** | ⚠ see caveat below | `04_aggregate_mrr.sql` Q1 |
| Trial subscription records | **778** | 690 with a later paid record | `05_trial_conversion.sql` Q1 |
| Trial→paid conversion rate (subscription-level proxy) | **88.7%** | ⚠ see caveat below | `05_trial_conversion.sql` Q1 |
| 6-month observed account subscription retention (pooled) | **98.9%** | ⚠ see caveat below | `06_cohort_retention.sql` Q2 |
| Most-used feature (by total usage_count) | **feature_32** | 6,686 total usage_count | `08_feature_engagement.sql` Q1 |
| Total churn events | **600** | 352 unique churned accounts | `09_churn_analysis.sql` Q1 |
| Churned-account rate | **70.4%** | 352 / 500 accounts | `09_churn_analysis.sql` |
| Repeat-churn accounts | **175** | 61 reactivation events | `09_churn_analysis.sql` Q5 |
| Support satisfaction score missingness | **41.3%** | Range: 3.0–5.0 only | `10_support_vs_churn.sql` Q4 |
| Support avg resolution time: churned vs non-churned | **35.74h vs 36.13h** | Difference negligible | `10_support_vs_churn.sql` Q1 |

---

## Per-Metric Caveats

### Aggregate Subscription-Record MRR — $10,734,251

> **Metric definition:** Sum of `mrr_amount` across every subscription record
> open in December 2024 (i.e. `start_date <= 2024-12-31 AND (end_date IS NULL
> OR end_date >= 2024-12-01)`).
>
> **Caveat:** This figure **double-, triple-, or N-times-counts revenue** for
> any account holding multiple concurrent open subscription records in the same
> month, by design. Because accounts routinely hold 5–14 open records
> simultaneously, this is not equivalent to a per-customer MRR figure, a
> contracted revenue figure, or a net-MRR-retention metric. It is labeled
> "Aggregate Subscription-Record MRR" throughout and never as "Company MRR,"
> "Account MRR," or "ARR."

Source: `sql/04_aggregate_mrr.sql`, Q1. Validated against direct-calculation
cross-check in the same file's VALIDATION block.

---

### Trial→Paid Conversion Rate — 88.7%

> **Metric definition:** Share of trial subscription records (778 total) where
> the same account also holds at least one paid subscription record with a
> `start_date` on or after the trial's `start_date`.
>
> **Caveat:** This is a **subscription-level proxy**, not a certified causal
> funnel. Because accounts hold many concurrently open subscriptions, a trial
> record and a paid record can coexist for the same account without one having
> caused the other (e.g. a trial for a new seat while an existing paid plan is
> also open). The account-level conversion rate (of accounts with any trial,
> how many ever also had a paid record) is effectively 100% — this is why only
> the subscription-level proxy is reported as a meaningful metric.

Source: `sql/05_trial_conversion.sql`, Q1 and Q3.

---

### 6-Month Pooled Observed Account Subscription Retention — 98.9%

> **Metric definition:** Of all accounts whose signup cohort is early enough
> that 6 months have elapsed within the observed data window (the "eligible
> cohort" denominator), the share that hold at least one open subscription
> record in the 6th month after their signup month.
>
> **Caveat:** This metric is **structurally close to a ceiling effect**, not a
> sensitive attrition signal, for two reasons:
> 1. ~90% of subscription records never receive an `end_date`, so once an
>    account has any open record it will continue to register as "active" under
>    this definition indefinitely.
> 2. The gap between `signup_date` and first subscription `start_date`
>    (documented in data quality check 16) means the metric rises from ~44% at
>    month 0 to ~99% by month 6 — the curve shape reflects an onboarding ramp,
>    not meaningful attrition discrimination.
>
> **Interpretation:** Read this as "observed account subscription retention"
> under a specific structural definition, not as a claim that 98.9% of
> customers are retained after 6 months.

Source: `sql/06_cohort_retention.sql`, Q2 (eligible-cohort-only denominator).
Cross-validated against `11_business_summary.sql`.

---

### Churned-Account Rate — 70.4%

> **Metric definition:** Unique accounts appearing in `raw_churn_events` (352)
> divided by total accounts (500). This counts any account that has ever had at
> least one churn event, regardless of whether the account subsequently
> reactivated.
>
> **Caveat:** This is **not** an event-based churn rate (which would be events /
> customer-months at risk). It is a prevalence figure — the share of the 500-
> account cohort that appears in the churn events table at least once. Given
> that 175 accounts have 2+ churn events (implying reactivation cycles), many
> of the 352 "churned" accounts are or were also active at other points.

Source: `sql/09_churn_analysis.sql`.

---

### Support Activity — Churned vs Non-Churned Accounts

> **Metric definition (resolution time):** Average `resolution_time_hours`
> across all support tickets submitted by accounts that have (or have not) at
> least one row in `raw_churn_events`.
>
> **Caveat:** This is an **observational association** only. Ticket timing is
> not scoped to before/after any specific churn event — a ticket could have
> been submitted before or after any of the account's churn events. The
> difference (35.74h churned vs 36.13h non-churned) is negligible; no causal
> claim is made.
>
> Escalation rates by churn status are a stronger result from this analysis:
> see `sql/10_support_vs_churn.sql`, Q1, and `outputs/support/`.

Source: `sql/10_support_vs_churn.sql`, Q1.

---

## Validation Record

From `sql/11_business_summary_output.txt`:

```
 accounts_check | churn_events_check | unique_churned_accounts_check
----------------+--------------------+-------------------------------
 t              | t                  | t
(1 row)
```

All three cross-checks passed. The summary figures are consistent with the
underlying table counts.
