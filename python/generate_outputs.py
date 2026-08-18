"""
python/generate_outputs.py
--------------------------
Reads raw CSVs from data/raw/ and writes output CSVs to outputs/.

This script mechanically replicates the SQL query logic from each analysis
file so that output CSVs can be produced without a live PostgreSQL connection.
It does NOT add new analysis, interpretations, or metrics — it is a
one-to-one translation of the validated SQL queries.

SQL remains the authoritative analytical engine for this project.
Run from the repository root:
    python python/generate_outputs.py
"""

import pathlib
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"


def load_raw() -> dict[str, pd.DataFrame]:
    """Load all five raw CSVs exactly as delivered."""
    tables = {
        "accounts": pd.read_csv(
            RAW / "ravenstack_accounts.csv",
            parse_dates=["signup_date"],
        ),
        "subscriptions": pd.read_csv(
            RAW / "ravenstack_subscriptions.csv",
            parse_dates=["start_date", "end_date"],
        ),
        "feature_usage": pd.read_csv(
            RAW / "ravenstack_feature_usage.csv",
            parse_dates=["usage_date"],
        ),
        "support_tickets": pd.read_csv(
            RAW / "ravenstack_support_tickets.csv",
            parse_dates=["submitted_at", "closed_at"],
        ),
        "churn_events": pd.read_csv(
            RAW / "ravenstack_churn_events.csv",
            parse_dates=["churn_date"],
        ),
    }
    return tables


def write(df: pd.DataFrame, subdir: str, filename: str) -> None:
    path = OUT / subdir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  wrote {path.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Calendar month spine helper
# (mirrors sql/02_calendar_spine.sql)
# ---------------------------------------------------------------------------

def calendar_month_spine(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    One row per calendar month from the earliest observed date to 3 months
    past the latest, matching the SQL calendar_month_spine view exactly.
    """
    acc = tables["accounts"]
    sub = tables["subscriptions"]
    fu = tables["feature_usage"]
    ce = tables["churn_events"]

    # end_date may be NaT (NULL) for open subscriptions — exclude from max
    sub_end_max = sub["end_date"].dropna().max()

    earliest = min(acc["signup_date"].min(), sub["start_date"].min())
    latest = max(
        acc["signup_date"].max(),
        sub["start_date"].max(),
        sub_end_max if pd.notna(sub_end_max) else pd.Timestamp.min,
        fu["usage_date"].max(),
        ce["churn_date"].max(),
    )

    month_start = pd.date_range(
        start=earliest.to_period("M").to_timestamp(),
        end=(latest.to_period("M") + 3).to_timestamp(),
        freq="MS",
    )
    spine = pd.DataFrame({
        "month_start": month_start,
        "month_end": [m + pd.offsets.MonthEnd(0) for m in month_start],
        "month_label": [m.strftime("%Y-%m") for m in month_start],
    })
    return spine


# ---------------------------------------------------------------------------
# 03_account_acquisition.sql
# ---------------------------------------------------------------------------

def run_acquisition(tables: dict, spine: pd.DataFrame) -> None:
    acc = tables["accounts"].copy()
    acc["cohort_month"] = acc["signup_date"].dt.to_period("M").dt.to_timestamp()

    # Q1: Monthly new account acquisition trend (mirrors 03 Q1)
    # Restrict to months up to the max signup month (same as SQL WHERE clause)
    max_signup_month = acc["signup_date"].dt.to_period("M").max().to_timestamp()
    spine_q1 = spine[spine["month_start"] <= max_signup_month].copy()

    monthly = (
        acc.groupby("cohort_month")["account_id"]
        .count()
        .rename("new_accounts")
        .reset_index()
        .rename(columns={"cohort_month": "month_start"})
    )
    q1 = spine_q1.merge(monthly, on="month_start", how="left")
    q1["new_accounts"] = q1["new_accounts"].fillna(0).astype(int)
    q1 = q1[["month_label", "month_start", "new_accounts"]]
    write(q1, "acquisition", "monthly_new_accounts.csv")

    # Q2: Acquisition by referral source, ranked (mirrors 03 Q2)
    q2 = (
        acc.groupby("referral_source")["account_id"]
        .count()
        .rename("accounts_acquired")
        .reset_index()
        .sort_values("accounts_acquired", ascending=False)
    )
    total = q2["accounts_acquired"].sum()
    q2["pct_of_total_accounts"] = (q2["accounts_acquired"] / total * 100).round(1)
    q2["acquisition_rank"] = q2["accounts_acquired"].rank(
        method="min", ascending=False
    ).astype(int)
    write(q2, "acquisition", "by_referral_source.csv")

    # Q3: Acquisition by current plan tier (mirrors 03 Q3)
    q3 = (
        acc.groupby("plan_tier")["account_id"]
        .count()
        .rename("account_count")
        .reset_index()
        .sort_values("account_count", ascending=False)
    )
    q3["pct_of_total_accounts"] = (q3["account_count"] / total * 100).round(1)
    write(q3, "acquisition", "by_plan_tier.csv")

    # Q4: Acquisition by industry, ranked, with referral-source breakdown (mirrors 03 Q4)
    ind = acc.groupby("industry").agg(
        account_count=("account_id", "count"),
        organic_accounts=("referral_source", lambda x: (x == "organic").sum()),
        partner_accounts=("referral_source", lambda x: (x == "partner").sum()),
    ).reset_index().sort_values("account_count", ascending=False)
    ind["pct_of_total_accounts"] = (ind["account_count"] / total * 100).round(1)
    ind["industry_rank"] = ind["account_count"].rank(method="min", ascending=False).astype(int)
    write(ind, "acquisition", "by_industry.csv")

    # Q5: Acquisition by country (mirrors 03 Q5)
    q5 = (
        acc.groupby("country")["account_id"]
        .count()
        .rename("account_count")
        .reset_index()
        .sort_values("account_count", ascending=False)
    )
    q5["pct_of_total_accounts"] = (q5["account_count"] / total * 100).round(1)
    q5["country_rank"] = q5["account_count"].rank(method="min", ascending=False).astype(int)
    write(q5, "acquisition", "by_country.csv")


# ---------------------------------------------------------------------------
# 04_aggregate_mrr.sql
# ---------------------------------------------------------------------------

def run_mrr(tables: dict, spine: pd.DataFrame) -> None:
    sub = tables["subscriptions"].copy()

    # For open subs (end_date NaT), treat as far-future so they stay open
    OPEN = pd.Timestamp("9999-12-31")
    sub["_end"] = sub["end_date"].fillna(OPEN)

    # Restrict spine to months up to latest subscription start_date month
    max_sub_month = sub["start_date"].dt.to_period("M").max().to_timestamp()
    spine_q = spine[spine["month_start"] <= max_sub_month].copy()

    rows_q1 = []
    rows_q2 = []

    for _, ms in spine_q.iterrows():
        # Open in this month: start_date <= month_end AND _end >= month_start
        mask = (sub["start_date"] <= ms["month_end"]) & (sub["_end"] >= ms["month_start"])
        open_subs = sub[mask]

        # Q1 row
        rows_q1.append({
            "month_label": ms["month_label"],
            "month_start": ms["month_start"],
            "active_subscription_records": open_subs["subscription_id"].nunique(),
            "aggregate_subscription_mrr": open_subs["mrr_amount"].sum(),
        })

        # Q2 row (by plan tier)
        row_q2 = {
            "month_label": ms["month_label"],
            "month_start": ms["month_start"],
            "total_mrr": open_subs["mrr_amount"].sum(),
        }
        for tier in ["Basic", "Pro", "Enterprise"]:
            row_q2[f"{tier.lower()}_mrr"] = open_subs.loc[
                open_subs["plan_tier"] == tier, "mrr_amount"
            ].sum()
        rows_q2.append(row_q2)

    # Q1
    q1 = pd.DataFrame(rows_q1)
    q1["aggregate_subscription_mrr"] = q1["aggregate_subscription_mrr"].round(2)
    write(q1, "mrr", "monthly_aggregate_mrr.csv")

    # Q2
    q2 = pd.DataFrame(rows_q2)[
        ["month_label", "month_start", "basic_mrr", "pro_mrr", "enterprise_mrr", "total_mrr"]
    ]
    for col in ["basic_mrr", "pro_mrr", "enterprise_mrr", "total_mrr"]:
        q2[col] = q2[col].round(2)
    write(q2, "mrr", "monthly_mrr_by_plan_tier.csv")


# ---------------------------------------------------------------------------
# 05_trial_conversion.sql
# ---------------------------------------------------------------------------

def run_conversion(tables: dict) -> None:
    sub = tables["subscriptions"].copy()

    trial_subs = sub[sub["is_trial"] == True][
        ["subscription_id", "account_id", "start_date", "plan_tier"]
    ].copy()
    paid_subs = sub[sub["is_trial"] == False][
        ["subscription_id", "account_id", "start_date"]
    ].copy()

    # Q1: Subscription-level conversion proxy, overall (mirrors 05 Q1)
    # For each trial record, does the same account have a paid record with
    # start_date >= trial start_date? This mirrors the SQL's correlated
    # EXISTS (WHERE p.start_date >= t.start_date), which is a "does at
    # least one qualifying paid record exist" check -- not "is the
    # account's *earliest* paid record after the trial." The correct
    # pandas equivalent is to compare against the account's LATEST paid
    # start_date: if even the latest paid record doesn't clear the trial's
    # start_date, none do; if it does, EXISTS is satisfied.
    paid_max = (
        paid_subs.groupby("account_id")["start_date"]
        .max()
        .rename("latest_paid_start")
        .reset_index()
    )
    trial_merged = trial_subs.merge(paid_max, on="account_id", how="left")
    trial_merged["has_later_paid"] = (
        trial_merged["latest_paid_start"] >= trial_merged["start_date"]
    )

    total_trial = trial_subs["subscription_id"].nunique()
    converted = trial_merged[trial_merged["has_later_paid"]]["subscription_id"].nunique()
    rate = round(100.0 * converted / total_trial, 1) if total_trial > 0 else None

    q1 = pd.DataFrame([{
        "total_trial_subscription_records": total_trial,
        "trial_records_with_later_paid_record": converted,
        "subscription_level_conversion_rate_pct": rate,
    }])
    write(q1, "conversion", "subscription_level_overall.csv")

    # Q2: Subscription-level conversion proxy by plan tier (mirrors 05 Q2)
    rows_q2 = []
    for tier in trial_subs["plan_tier"].unique():
        tier_trials = trial_merged[trial_merged["plan_tier"] == tier]
        t_total = tier_trials["subscription_id"].nunique()
        t_converted = tier_trials[tier_trials["has_later_paid"]]["subscription_id"].nunique()
        t_rate = round(100.0 * t_converted / t_total, 1) if t_total > 0 else None
        rows_q2.append({
            "plan_tier": tier,
            "trial_records": t_total,
            "trial_records_with_later_paid_record": t_converted,
            "conversion_rate_pct": t_rate,
        })
    q2 = pd.DataFrame(rows_q2).sort_values("conversion_rate_pct", ascending=False)
    write(q2, "conversion", "subscription_level_by_plan_tier.csv")

    # Q3: Account-level conversion overall (mirrors 05 Q3)
    account_flags = sub.groupby("account_id").agg(
        ever_had_trial=("is_trial", lambda x: x.any()),
        ever_had_paid=("is_trial", lambda x: (~x).any()),
    ).reset_index()
    accts_with_trial = account_flags["ever_had_trial"].sum()
    accts_trial_and_paid = (
        account_flags["ever_had_trial"] & account_flags["ever_had_paid"]
    ).sum()
    acct_rate = round(100.0 * accts_trial_and_paid / accts_with_trial, 1) if accts_with_trial > 0 else None

    q3 = pd.DataFrame([{
        "accounts_with_any_trial": int(accts_with_trial),
        "accounts_with_trial_and_paid": int(accts_trial_and_paid),
        "account_level_conversion_rate_pct": acct_rate,
    }])
    write(q3, "conversion", "account_level_overall.csv")


# ---------------------------------------------------------------------------
# 06_cohort_retention.sql — Q2 Pooled retention curve
# ---------------------------------------------------------------------------

def run_retention(tables: dict, spine: pd.DataFrame) -> None:
    acc = tables["accounts"].copy()
    sub = tables["subscriptions"].copy()

    acc["cohort_month"] = acc["signup_date"].dt.to_period("M").dt.to_timestamp()

    OPEN = pd.Timestamp("9999-12-31")
    sub["_end"] = sub["end_date"].fillna(OPEN)

    max_observed_month = sub["start_date"].dt.to_period("M").max().to_timestamp()

    # Build account_month_activity: set of (account_id, month_start) where
    # the account has at least one open subscription record that month.
    activity_pairs: set[tuple] = set()
    spine_range = spine[spine["month_start"] <= max_observed_month + pd.offsets.MonthEnd(3)]
    for _, ms in spine_range.iterrows():
        mask = (sub["start_date"] <= ms["month_end"]) & (sub["_end"] >= ms["month_start"])
        active_accounts = sub.loc[mask, "account_id"].unique()
        for aid in active_accounts:
            activity_pairs.add((aid, ms["month_start"]))

    cohorts = acc[["account_id", "cohort_month"]].copy()

    rows = []
    for m in range(0, 19):  # months_since_signup 0..18
        # Eligible accounts: cohort_month + m months <= max_observed_month
        eligible = cohorts[
            cohorts["cohort_month"] + pd.DateOffset(months=m) <= max_observed_month
        ].copy()
        eligible["obs_month"] = eligible["cohort_month"] + pd.DateOffset(months=m)
        # Normalize to period-start
        eligible["obs_month"] = eligible["obs_month"].dt.to_period("M").dt.to_timestamp()

        n_eligible = len(eligible)
        n_active = sum(
            1 for _, row in eligible.iterrows()
            if (row["account_id"], row["obs_month"]) in activity_pairs
        )
        rate = round(100.0 * n_active / n_eligible, 1) if n_eligible > 0 else None
        rows.append({
            "months_since_signup": m,
            "eligible_accounts": n_eligible,
            "active_accounts": n_active,
            "retention_rate_pct_eligible_cohorts_only": rate,
        })

    q2 = pd.DataFrame(rows)
    write(q2, "retention", "pooled_retention_curve.csv")


# ---------------------------------------------------------------------------
# 09_churn_analysis.sql
# ---------------------------------------------------------------------------

def run_churn(tables: dict, spine: pd.DataFrame) -> None:
    ce = tables["churn_events"].copy()
    acc = tables["accounts"].copy()

    ce["churn_month"] = ce["churn_date"].dt.to_period("M").dt.to_timestamp()

    # Q1: Churn events over time (monthly) (mirrors 09 Q1)
    max_churn_month = ce["churn_date"].dt.to_period("M").max().to_timestamp()
    spine_q = spine[spine["month_start"] <= max_churn_month].copy()

    monthly_ce = (
        ce.groupby("churn_month")
        .agg(
            churn_events=("churn_event_id", "count"),
            unique_churned_accounts=("account_id", "nunique"),
        )
        .reset_index()
        .rename(columns={"churn_month": "month_start"})
    )
    q1 = spine_q.merge(monthly_ce, on="month_start", how="left")
    q1["churn_events"] = q1["churn_events"].fillna(0).astype(int)
    q1["unique_churned_accounts"] = q1["unique_churned_accounts"].fillna(0).astype(int)
    q1 = q1[["month_label", "month_start", "churn_events", "unique_churned_accounts"]]
    write(q1, "churn", "monthly_churn_events.csv")

    # Q2: Churn by reason code, ranked (mirrors 09 Q2)
    total_events = len(ce)
    q2 = (
        ce.groupby("reason_code")
        .agg(
            churn_events=("churn_event_id", "count"),
            unique_accounts=("account_id", "nunique"),
        )
        .reset_index()
        .sort_values("churn_events", ascending=False)
    )
    q2["pct_of_all_churn_events"] = (q2["churn_events"] / total_events * 100).round(1)
    q2["reason_rank"] = q2["churn_events"].rank(method="min", ascending=False).astype(int)
    write(q2, "churn", "by_reason_code.csv")

    # Q3: Churn by account plan tier (mirrors 09 Q3)
    ce_with_plan = ce.merge(acc[["account_id", "plan_tier"]], on="account_id", how="left")
    plan_totals = acc.groupby("plan_tier")["account_id"].count().rename("accounts_on_this_plan")
    q3 = (
        ce_with_plan.groupby("plan_tier")
        .agg(
            churn_events=("churn_event_id", "count"),
            unique_churned_accounts=("account_id", "nunique"),
        )
        .reset_index()
        .sort_values("churn_events", ascending=False)
    )
    q3 = q3.merge(plan_totals, on="plan_tier")
    q3["pct_of_plan_accounts_with_churn_event"] = (
        q3["unique_churned_accounts"] / q3["accounts_on_this_plan"] * 100
    ).round(1)
    write(q3, "churn", "by_plan_tier.csv")

    # Q5: Repeat churn summary (mirrors 09 Q5)
    events_per_account = ce.groupby("account_id")["churn_event_id"].count()
    repeat_churn_accounts = int((events_per_account > 1).sum())
    q5 = pd.DataFrame([{
        "total_churn_events": len(ce),
        "reactivation_events": int(ce["is_reactivation"].sum()),
        "pct_reactivation_events": round(100.0 * ce["is_reactivation"].sum() / len(ce), 1),
        "unique_churned_accounts": ce["account_id"].nunique(),
        "repeat_churn_accounts": repeat_churn_accounts,
    }])
    write(q5, "churn", "repeat_churn_summary.csv")


# ---------------------------------------------------------------------------
# 10_support_vs_churn.sql
# ---------------------------------------------------------------------------

def run_support(tables: dict) -> None:
    tix = tables["support_tickets"].copy()
    ce = tables["churn_events"].copy()

    churned_accounts = set(ce["account_id"].unique())
    tix["is_churned_account"] = tix["account_id"].isin(churned_accounts)

    # Q1: Ticket volume and resolution metrics — churned vs non-churned (mirrors 10 Q1)
    q1 = (
        tix.groupby("is_churned_account")
        .agg(
            accounts=("account_id", "nunique"),
            tickets=("ticket_id", "count"),
            avg_resolution_time_hours=("resolution_time_hours", "mean"),
            avg_first_response_minutes=("first_response_time_minutes", "mean"),
            escalated_tickets=("escalation_flag", "sum"),
        )
        .reset_index()
    )
    q1["tickets_per_account"] = (q1["tickets"] / q1["accounts"]).round(2)
    q1["avg_resolution_time_hours"] = q1["avg_resolution_time_hours"].round(2)
    q1["avg_first_response_minutes"] = q1["avg_first_response_minutes"].round(1)
    q1["escalated_tickets"] = q1["escalated_tickets"].astype(int)
    q1["escalation_rate_pct"] = (q1["escalated_tickets"] / q1["tickets"] * 100).round(1)
    write(
        q1[["is_churned_account", "accounts", "tickets", "tickets_per_account",
            "avg_resolution_time_hours", "avg_first_response_minutes",
            "escalated_tickets", "escalation_rate_pct"]],
        "support",
        "volume_and_resolution_by_churn_status.csv",
    )

    # Q2: Ticket priority mix — churned vs non-churned (mirrors 10 Q2)
    q2 = (
        tix.groupby("is_churned_account")
        .agg(
            low_priority_tickets=("priority", lambda x: (x == "low").sum()),
            medium_priority_tickets=("priority", lambda x: (x == "medium").sum()),
            high_priority_tickets=("priority", lambda x: (x == "high").sum()),
            urgent_priority_tickets=("priority", lambda x: (x == "urgent").sum()),
            total_tickets=("ticket_id", "count"),
        )
        .reset_index()
    )
    q2["pct_high_or_urgent"] = (
        (q2["high_priority_tickets"] + q2["urgent_priority_tickets"])
        / q2["total_tickets"] * 100
    ).round(1)
    write(q2, "support", "priority_mix_by_churn_status.csv")


# ---------------------------------------------------------------------------
# 08_feature_engagement.sql — Q1 Top features
# ---------------------------------------------------------------------------

def run_engagement(tables: dict) -> None:
    fu = tables["feature_usage"].copy()
    sub = tables["subscriptions"][["subscription_id", "account_id"]].copy()

    # Join to get account_id (structural FK, not temporal — mirrors 08 method)
    fu_acc = fu.merge(sub, on="subscription_id", how="left")

    # Q1: Most-used features by total usage volume and duration (mirrors 08 Q1)
    q1 = (
        fu_acc.groupby("feature_name")
        .agg(
            usage_events=("usage_id", "count"),
            distinct_accounts_using=("account_id", "nunique"),
            total_usage_count=("usage_count", "sum"),
            total_duration_secs=("usage_duration_secs", "sum"),
            avg_duration_secs_per_event=("usage_duration_secs", "mean"),
        )
        .reset_index()
        .sort_values("total_usage_count", ascending=False)
    )
    q1["avg_duration_secs_per_event"] = q1["avg_duration_secs_per_event"].round(1)
    q1["usage_volume_rank"] = q1["total_usage_count"].rank(
        method="min", ascending=False
    ).astype(int)
    write(q1, "engagement", "top_features_by_usage.csv")

    # Q5: Overall engagement summary -- churned vs non-churned accounts
    # (mirrors 08 Q5). Uses ALL observed usage history per account, joined
    # to account_id via the subscription FK bridge only (not scoped to
    # subscription periods -- see data quality check 11).
    churned_ids = set(tables["churn_events"]["account_id"].unique())
    fu_status = fu_acc.copy()
    fu_status["is_churned_account"] = fu_status["account_id"].isin(churned_ids)

    q5 = (
        fu_status.groupby("is_churned_account")
        .agg(
            accounts=("account_id", "nunique"),
            usage_events=("usage_id", "count"),
            usage_count_sum=("usage_count", "sum"),
            error_count_sum=("error_count", "sum"),
        )
        .reset_index()
        .sort_values("is_churned_account")
    )
    q5["usage_events_per_account"] = (
        q5["usage_events"] / q5["accounts"]
    ).round(1)
    q5["usage_count_per_account"] = (
        q5["usage_count_sum"] / q5["accounts"]
    ).round(1)
    q5["errors_per_account"] = (
        q5["error_count_sum"] / q5["accounts"]
    ).round(2)
    q5 = q5[
        [
            "is_churned_account",
            "accounts",
            "usage_events",
            "usage_events_per_account",
            "usage_count_per_account",
            "errors_per_account",
        ]
    ]
    write(q5, "engagement", "churn_status_engagement_summary.csv")


# ---------------------------------------------------------------------------
# Validation spot-checks
# ---------------------------------------------------------------------------

def validate(tables: dict) -> None:
    acc = tables["accounts"]
    ce = tables["churn_events"]

    # Monthly acquisition sum should equal 500
    acq_csv = OUT / "acquisition" / "monthly_new_accounts.csv"
    acq = pd.read_csv(acq_csv)
    acq_total = acq["new_accounts"].sum()
    assert acq_total == len(acc), (
        f"Acquisition total mismatch: {acq_total} != {len(acc)}"
    )
    print(f"  [OK] acquisition total = {acq_total} (expected {len(acc)})")

    # Churn events sum should equal 600
    churn_csv = OUT / "churn" / "monthly_churn_events.csv"
    churn = pd.read_csv(churn_csv)
    churn_total = churn["churn_events"].sum()
    assert churn_total == len(ce), (
        f"Churn events total mismatch: {churn_total} != {len(ce)}"
    )
    print(f"  [OK] churn events total = {churn_total} (expected {len(ce)})")

    # CSV files created
    csv_files = list(OUT.rglob("*.csv"))
    print(f"  [OK] {len(csv_files)} CSV output files created")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading raw CSVs...")
    tables = load_raw()
    spine = calendar_month_spine(tables)

    print("\n03_account_acquisition.sql")
    run_acquisition(tables, spine)

    print("\n04_aggregate_mrr.sql")
    run_mrr(tables, spine)

    print("\n05_trial_conversion.sql")
    run_conversion(tables)

    print("\n06_cohort_retention.sql (Q2 pooled curve)")
    run_retention(tables, spine)

    print("\n09_churn_analysis.sql")
    run_churn(tables, spine)

    print("\n10_support_vs_churn.sql")
    run_support(tables)

    print("\n08_feature_engagement.sql (Q1, Q5)")
    run_engagement(tables)

    print("\nValidation checks...")
    validate(tables)

    print("\nDone. All output CSVs written to outputs/")


if __name__ == "__main__":
    main()