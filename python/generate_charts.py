"""
python/generate_charts.py
-------------------------
Reads ONLY from outputs/ CSV files (never from data/raw/).
Produces 5 static PNG charts in charts/.

SQL remains the analytical engine. This script is presentation-only.
Run from the repository root:
    python python/generate_charts.py
"""

import pathlib
import warnings

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
CHARTS = ROOT / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared style
# ---------------------------------------------------------------------------
PALETTE = {
    "blue":       "#3B82F6",
    "indigo":     "#6366F1",
    "violet":     "#8B5CF6",
    "emerald":    "#10B981",
    "rose":       "#F43F5E",
    "amber":      "#F59E0B",
    "slate":      "#64748B",
    "slate_dark": "#1E293B",
    "slate_bg":   "#0F172A",
    "grid":       "#1E293B",
    "text_main":  "#F1F5F9",
    "text_muted": "#94A3B8",
}

REASON_COLORS = {
    "features":   "#6366F1",
    "budget":     "#F59E0B",
    "support":    "#F43F5E",
    "unknown":    "#64748B",
    "competitor": "#3B82F6",
    "pricing":    "#10B981",
}


def apply_style(fig: plt.Figure, ax: plt.Axes) -> None:
    fig.patch.set_facecolor(PALETTE["slate_bg"])
    ax.set_facecolor("#0F172A")
    ax.tick_params(colors=PALETTE["text_muted"], labelsize=9)
    ax.xaxis.label.set_color(PALETTE["text_muted"])
    ax.yaxis.label.set_color(PALETTE["text_muted"])
    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["grid"])
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.6, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)


def title_block(
    fig: plt.Figure,
    ax: plt.Axes,
    title: str,
    subtitle: str,
    source: str,
) -> None:
    ax.set_title(
        title,
        color=PALETTE["text_main"],
        fontsize=13,
        fontweight="bold",
        pad=22,
        loc="left",
    )
    fig.text(
        0.125, 0.925,
        subtitle,
        color=PALETTE["text_muted"],
        fontsize=8.5,
        style="italic",
    )
    fig.text(
        0.125, 0.015,
        f"Source: {source}",
        color=PALETTE["text_muted"],
        fontsize=7.5,
    )


def save(fig: plt.Figure, name: str) -> None:
    path = CHARTS / name
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  saved charts/{name}")


# ---------------------------------------------------------------------------
# Chart 1 — Monthly New Account Acquisition
# (source: outputs/acquisition/monthly_new_accounts.csv
#  mirrors: sql/03_account_acquisition.sql Q1)
# ---------------------------------------------------------------------------

def chart_01_monthly_acquisition() -> None:
    df = pd.read_csv(OUT / "acquisition" / "monthly_new_accounts.csv",
                     parse_dates=["month_start"])

    fig, ax = plt.subplots(figsize=(11, 5))
    apply_style(fig, ax)

    bars = ax.bar(
        df["month_start"],
        df["new_accounts"],
        width=22,
        color=PALETTE["indigo"],
        alpha=0.85,
        zorder=3,
    )

    # 3-month rolling average overlay
    rolling = df["new_accounts"].rolling(3, center=True).mean()
    ax.plot(
        df["month_start"],
        rolling,
        color=PALETTE["amber"],
        linewidth=1.8,
        linestyle="--",
        label="3-month rolling avg",
        zorder=4,
    )

    ax.legend(
        facecolor=PALETTE["slate_dark"],
        edgecolor=PALETTE["grid"],
        labelcolor=PALETTE["text_muted"],
        fontsize=8.5,
    )

    ax.set_xlabel("Month", labelpad=8)
    ax.set_ylabel("New Accounts", labelpad=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    # x-axis: show every 3rd month label
    xticks = df["month_start"].iloc[::3]
    ax.set_xticks(xticks)
    ax.set_xticklabels(
        [t.strftime("%b %Y") for t in xticks],
        rotation=35, ha="right", fontsize=8,
    )

    # Annotate total
    total = df["new_accounts"].sum()
    ax.text(
        0.99, 0.96,
        f"Total: {total:,} accounts",
        transform=ax.transAxes,
        ha="right", va="top",
        color=PALETTE["text_muted"],
        fontsize=8.5,
    )

    title_block(
        fig, ax,
        title="Monthly New Account Acquisition  (Jan 2023 – Dec 2024)",
        subtitle="Count of accounts by raw_accounts.signup_date month  |  Raw data: 500 accounts",
        source="sql/03_account_acquisition.sql Q1  →  outputs/acquisition/monthly_new_accounts.csv",
    )

    save(fig, "01_monthly_account_acquisition.png")


# ---------------------------------------------------------------------------
# Chart 2 — Aggregate Subscription-Record MRR
# (source: outputs/mrr/monthly_aggregate_mrr.csv
#  mirrors: sql/04_aggregate_mrr.sql Q1)
# ---------------------------------------------------------------------------

def chart_02_aggregate_mrr() -> None:
    df = pd.read_csv(OUT / "mrr" / "monthly_aggregate_mrr.csv",
                     parse_dates=["month_start"])

    fig, ax = plt.subplots(figsize=(11, 5))
    apply_style(fig, ax)

    ax.fill_between(
        df["month_start"],
        df["aggregate_subscription_mrr"],
        alpha=0.18,
        color=PALETTE["emerald"],
        zorder=2,
    )
    ax.plot(
        df["month_start"],
        df["aggregate_subscription_mrr"],
        color=PALETTE["emerald"],
        linewidth=2.2,
        zorder=3,
    )

    # Mark last point
    last = df.iloc[-1]
    ax.scatter(last["month_start"], last["aggregate_subscription_mrr"],
               color=PALETTE["emerald"], s=55, zorder=5)
    ax.annotate(
        f'${last["aggregate_subscription_mrr"]:,.0f}\n({last["month_label"]})',
        xy=(last["month_start"], last["aggregate_subscription_mrr"]),
        xytext=(10, -25),
        textcoords="offset points",
        color=PALETTE["text_muted"],
        fontsize=7.5,
        arrowprops=dict(arrowstyle="-", color=PALETTE["grid"], lw=0.8),
    )

    ax.set_xlabel("Month", labelpad=8)
    ax.set_ylabel("Aggregate MRR (USD)", labelpad=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f"${x/1_000_000:.1f}M"
    ))

    xticks = df["month_start"].iloc[::3]
    ax.set_xticks(xticks)
    ax.set_xticklabels(
        [t.strftime("%b %Y") for t in xticks],
        rotation=35, ha="right", fontsize=8,
    )

    title_block(
        fig, ax,
        title="Aggregate Subscription-Record MRR by Month",
        subtitle=(
            "Sum of mrr_amount across all open subscription records per month  "
            "|  NOT per-customer MRR  |  Accounts hold avg ~9 concurrent open records"
        ),
        source="sql/04_aggregate_mrr.sql Q1  ->  outputs/mrr/monthly_aggregate_mrr.csv",
    )

    save(fig, "02_aggregate_subscription_mrr.png")


# ---------------------------------------------------------------------------
# Chart 3 — Churn Events Over Time (Monthly)
# (source: outputs/churn/monthly_churn_events.csv
#  mirrors: sql/09_churn_analysis.sql Q1)
# ---------------------------------------------------------------------------

def chart_03_monthly_churn() -> None:
    df = pd.read_csv(OUT / "churn" / "monthly_churn_events.csv",
                     parse_dates=["month_start"])

    fig, ax = plt.subplots(figsize=(11, 5))
    apply_style(fig, ax)

    # Events bars
    ax.bar(
        df["month_start"],
        df["churn_events"],
        width=22,
        color=PALETTE["rose"],
        alpha=0.80,
        label="Churn events",
        zorder=3,
    )

    # Unique churned accounts line
    ax2 = ax.twinx()
    ax2.set_facecolor("none")
    ax2.plot(
        df["month_start"],
        df["unique_churned_accounts"],
        color=PALETTE["amber"],
        linewidth=1.6,
        linestyle="--",
        marker="o",
        markersize=3.5,
        label="Unique churned accounts",
        zorder=4,
    )
    ax2.tick_params(colors=PALETTE["text_muted"], labelsize=9)
    ax2.yaxis.label.set_color(PALETTE["text_muted"])
    ax2.set_ylabel("Unique Churned Accounts", labelpad=8, color=PALETTE["text_muted"])
    ax2.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    for spine in ax2.spines.values():
        spine.set_edgecolor(PALETTE["grid"])

    # Combined legend
    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(
        handles1 + handles2, labels1 + labels2,
        facecolor=PALETTE["slate_dark"],
        edgecolor=PALETTE["grid"],
        labelcolor=PALETTE["text_muted"],
        fontsize=8.5,
        loc="upper left",
    )

    ax.set_xlabel("Month", labelpad=8)
    ax.set_ylabel("Churn Events", labelpad=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    xticks = df["month_start"].iloc[::3]
    ax.set_xticks(xticks)
    ax.set_xticklabels(
        [t.strftime("%b %Y") for t in xticks],
        rotation=35, ha="right", fontsize=8,
    )

    total_events = df["churn_events"].sum()
    ax.text(
        0.99, 0.96,
        f"Total: {total_events} events  |  352 unique accounts",
        transform=ax.transAxes,
        ha="right", va="top",
        color=PALETTE["text_muted"],
        fontsize=8.5,
    )

    title_block(
        fig, ax,
        title="Churn Events Over Time  (Monthly)",
        subtitle=(
            "Source of truth: raw_churn_events  |  Events != accounts  "
            "(175 accounts have 2+ events)"
        ),
        source="sql/09_churn_analysis.sql Q1  ->  outputs/churn/monthly_churn_events.csv",
    )

    save(fig, "03_monthly_churn_events.png")


# ---------------------------------------------------------------------------
# Chart 4 — Churn Events by Reason Code
# (source: outputs/churn/by_reason_code.csv
#  mirrors: sql/09_churn_analysis.sql Q2)
# ---------------------------------------------------------------------------

def chart_04_churn_reasons() -> None:
    df = pd.read_csv(OUT / "churn" / "by_reason_code.csv").sort_values(
        "churn_events", ascending=True
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    apply_style(fig, ax)

    colors = [REASON_COLORS.get(r, PALETTE["slate"]) for r in df["reason_code"]]
    bars = ax.barh(
        df["reason_code"],
        df["churn_events"],
        color=colors,
        alpha=0.88,
        height=0.6,
        zorder=3,
    )

    # Inline labels: events + pct
    for bar, events, pct in zip(bars, df["churn_events"], df["pct_of_all_churn_events"]):
        ax.text(
            bar.get_width() + 1.5,
            bar.get_y() + bar.get_height() / 2,
            f"{events}  ({pct}%)",
            va="center",
            color=PALETTE["text_muted"],
            fontsize=9,
        )

    ax.set_xlabel("Churn Events", labelpad=8)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.set_xlim(right=df["churn_events"].max() * 1.22)

    title_block(
        fig, ax,
        title="Churn Events by Reason Code",
        subtitle=(
            "Counts churn EVENTS (600 total), not unique accounts (352)  "
            "|  Source: raw_churn_events.reason_code"
        ),
        source="sql/09_churn_analysis.sql Q2  ->  outputs/churn/by_reason_code.csv",
    )

    save(fig, "04_churn_by_reason_code.png")


# ---------------------------------------------------------------------------
# Chart 5 — Support Escalation Rate: Churned vs Non-Churned (Observational)
# (source: outputs/support/volume_and_resolution_by_churn_status.csv
#  mirrors: sql/10_support_vs_churn.sql Q1)
# ---------------------------------------------------------------------------

def chart_05_support_escalation() -> None:
    df = pd.read_csv(OUT / "support" / "volume_and_resolution_by_churn_status.csv")

    labels = ["Non-Churned Accounts", "Churned Accounts"]
    esc_rates = df["escalation_rate_pct"].tolist()
    ticket_counts = df["tickets"].tolist()
    acct_counts = df["accounts"].tolist()
    colors = [PALETTE["blue"], PALETTE["rose"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    apply_style(fig, ax)

    x = [0, 1]
    bars = ax.bar(x, esc_rates, width=0.45, color=colors, alpha=0.87, zorder=3)

    # Value labels on bars
    for bar, rate, tickets, accts in zip(bars, esc_rates, ticket_counts, acct_counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.08,
            f"{rate}%",
            ha="center", va="bottom",
            color=PALETTE["text_main"],
            fontsize=12,
            fontweight="bold",
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"{accts} accounts\n{tickets:,} tickets",
            ha="center", va="center",
            color="white",
            fontsize=8,
            alpha=0.75,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, color=PALETTE["text_main"], fontsize=10)
    ax.set_ylabel("Escalation Rate (%)", labelpad=8)
    ax.set_ylim(0, max(esc_rates) * 1.35)

    # Resolution time comparison note
    res_times = df["avg_resolution_time_hours"].tolist()
    fig.text(
        0.5, 0.01,
        f"Avg resolution time: {res_times[0]}h (non-churned) vs {res_times[1]}h (churned)  "
        f"|  Difference is negligible",
        ha="center",
        color=PALETTE["text_muted"],
        fontsize=7.5,
    )

    title_block(
        fig, ax,
        title="Support Escalation Rate:  Churned vs Non-Churned Accounts",
        subtitle=(
            "Observational association only  |  Ticket timing not scoped to pre-/post-churn  "
            "|  'Churned' = any row in raw_churn_events"
        ),
        source="sql/10_support_vs_churn.sql Q1  ->  outputs/support/volume_and_resolution_by_churn_status.csv",
    )

    save(fig, "05_support_escalation_by_churn_status.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Generating charts from outputs/ CSVs...\n")

    chart_01_monthly_acquisition()
    chart_02_aggregate_mrr()
    chart_03_monthly_churn()
    chart_04_churn_reasons()
    chart_05_support_escalation()

    pngs = list(CHARTS.glob("*.png"))
    print(f"\nDone. {len(pngs)} charts written to charts/")


if __name__ == "__main__":
    main()
