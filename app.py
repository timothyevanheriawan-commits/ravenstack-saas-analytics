"""
RavenStack SaaS Analytics. Streamlit Dashboard
================================================

Visualizes the validated outputs of the RavenStack SQL analytics project.
This file does not compute any metric itself; it reads CSVs from outputs/
that are produced by sql/*.sql (via psql) or python/generate_outputs.py
(a pandas reimplementation used when psql is unavailable), and renders them.

No SQL is modified or re-run from this app. No new metrics, business logic,
or numbers are introduced here. Interpretation text is drawn directly from
docs/results_review.md, docs/data_audit.md, docs/project_spec.md, and
docs/chart_notes.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"

# ---------------------------------------------------------------------------
# Palette. restrained blue, steel, and slate, deepened slightly for contrast
# ---------------------------------------------------------------------------

INK = "#16212F"           # primary text, near-black slate
SLATE = "#33538A"         # primary accent
STEEL = "#54749E"         # secondary accent
STEEL_LIGHT = "#83A0C2"   # tertiary accent
STEEL_PALE = "#B7C8DC"    # quaternary accent, low-emphasis fills
MUTED = "#7C8AA0"         # muted gray-blue, captions and low-emphasis labels
BG = "#F6F7FA"            # page background
SURFACE = "#ECEFF4"       # subtle panel background
BORDER = "#DBE1EA"        # hairline borders
CAVEAT = "#96650F"        # muted amber, reserved for caveat and warning accents
CAVEAT_BG = "#FAF3E3"
SIDEBAR_BG = "#101A26"    # sidebar background, darker than INK for contrast

CHART_SEQUENCE = [SLATE, STEEL, STEEL_LIGHT, MUTED, INK, STEEL_PALE, "#64748B"]

# Editorial serif for headings, clean technical sans for body and UI chrome.
# Both stacks lead with a distinctive webfont and fall back to characterful
# system fonts (never a bare "serif" or "sans-serif" default) so the design
# holds up even if the webfonts are blocked by a privacy-hardened browser.
HEADING_FONT = (
    "'IBM Plex Sans', -apple-system, 'Segoe UI Variable Display', "
    "'Segoe UI', system-ui, sans-serif"
)

BODY_FONT = (
    "'IBM Plex Sans', -apple-system, 'Segoe UI Variable Display', "
    "'Segoe UI', system-ui, sans-serif"
)

st.set_page_config(
    page_title="RavenStack SaaS Analytics",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Fonts and CSS
# ---------------------------------------------------------------------------


def inject_fonts() -> None:
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap"
          rel="stylesheet">
        """,
        unsafe_allow_html=True,
    )


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --rs-ink: {INK};
            --rs-slate: {SLATE};
            --rs-steel: {STEEL};
            --rs-steel-light: {STEEL_LIGHT};
            --rs-steel-pale: {STEEL_PALE};
            --rs-muted: {MUTED};
            --rs-bg: {BG};
            --rs-surface: {SURFACE};
            --rs-border: {BORDER};
            --rs-caveat: {CAVEAT};
            --rs-caveat-bg: {CAVEAT_BG};
            --rs-heading-font: {HEADING_FONT};
            --rs-body-font: {BODY_FONT};
        }}

        html, body, [class*="css"] {{
            font-family: var(--rs-body-font);
        }}

        .stApp {{
            background-color: var(--rs-bg);
        }}

        /* Hide default Streamlit chrome */
        #MainMenu, footer {{visibility: hidden;}}
        div[data-testid="stDecoration"] {{display: none;}}

        /* ---------------- Sidebar ---------------- */
        section[data-testid="stSidebar"] {{
            background-color: var(--rs-sidebar-bg, {SIDEBAR_BG});
            border-right: 1px solid #1F2C3D;
        }}
        section[data-testid="stSidebar"] > div {{
            padding-top: 1.6rem;
        }}
        section[data-testid="stSidebar"] * {{
            color: #DCE4F0;
        }}

        .rs-wordmark {{
            font-family: var(--rs-heading-font);
            font-size: 1.55rem;
            font-weight: 600;
            color: #FFFFFF;
            line-height: 1.1;
            margin-bottom: 0.05rem;
        }}
        .rs-wordmark-sub {{
            font-size: 0.74rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: #7C8FAE;
            margin-bottom: 1.4rem;
        }}

        /* Nav buttons: flatten Streamlit's default button chrome into a
           left-aligned nav list, with the active page filled in solid. */
        section[data-testid="stSidebar"] div[data-testid="stButton"] {{
            margin-bottom: 0.15rem;
        }}
        section[data-testid="stSidebar"] button {{
            width: 100%;
            justify-content: flex-start !important;
            text-align: left;
            font-family: var(--rs-body-font);
            font-size: 0.93rem;
            font-weight: 500;
            letter-spacing: 0.01em;
            border-radius: 7px;
            padding: 0.55rem 0.8rem;
            transition: background-color 0.12s ease, color 0.12s ease;
            box-shadow: none !important;
        }}
        section[data-testid="stSidebar"] button:focus {{
            box-shadow: none !important;
            outline: none !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{
            background-color: transparent;
            border: 1px solid transparent;
            color: #AEBEDA;
        }}
        section[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{
            background-color: rgba(255,255,255,0.07);
            color: #FFFFFF;
            border-color: rgba(255,255,255,0.08);
        }}
        section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
            background-color: var(--rs-slate);
            border: 1px solid rgba(255,255,255,0.14);
            color: #FFFFFF;
            font-weight: 600;
        }}
        section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {{
            background-color: var(--rs-slate);
            color: #FFFFFF;
        }}

        section[data-testid="stSidebar"] hr {{
            border-color: #24334A;
            margin: 1.1rem 0;
        }}
        .rs-sidebar-note {{
            font-size: 0.76rem;
            line-height: 1.5;
            color: #7C8FAE;
        }}

        /* ---------------- Headings and body copy ---------------- */
        h1, h2, h3 {{
            font-family: var(--rs-heading-font);
            color: var(--rs-ink);
            font-weight: 600;
            letter-spacing: -0.01em;
        }}
        h1 {{ font-size: 2.2rem; margin-bottom: 0.15rem; }}
        h2 {{ font-size: 1.4rem; margin-top: 1.7rem; margin-bottom: 0.35rem; }}
        h3 {{ font-size: 1.08rem; margin-top: 1.1rem; }}

        p, li, span, label {{
            color: var(--rs-ink);
        }}

        .rs-lede {{
            font-size: 1.04rem;
            line-height: 1.55;
            color: #3B4A5E;
            max-width: 62rem;
            margin-bottom: 0.6rem;
        }}

        /* Section dividers instead of wrapping everything in cards */
        .rs-divider {{
            border: none;
            border-top: 1px solid var(--rs-border);
            margin: 1.5rem 0 1.3rem 0;
        }}

        /* Eyebrow / kicker label above each page title */
        .rs-kicker {{
            display: flex;
            align-items: center;
            gap: 0.55rem;
            font-size: 0.76rem;
            font-weight: 600;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            color: var(--rs-steel);
            margin-bottom: 0.4rem;
        }}
        .rs-kicker-num {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 1.7rem;
            height: 1.3rem;
            padding: 0 0.4rem;
            border-radius: 4px;
            background: var(--rs-slate);
            color: #FFFFFF;
            font-size: 0.7rem;
            letter-spacing: 0.02em;
        }}

        /* Metric strip: compact figures in a row, not oversized KPI cards */
        .rs-metric-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0;
            border-top: 1px solid var(--rs-border);
            border-bottom: 1px solid var(--rs-border);
            margin: 0.7rem 0 1.1rem 0;
        }}
        .rs-metric {{
            flex: 1 1 200px;
            padding: 0.9rem 1.15rem;
            border-right: 1px solid var(--rs-border);
        }}
        .rs-metric:last-child {{
            border-right: none;
        }}
        .rs-metric-value {{
            font-family: var(--rs-heading-font);
            font-size: 1.7rem;
            font-weight: 600;
            color: var(--rs-ink);
            line-height: 1.15;
        }}
        .rs-metric-label {{
            font-size: 0.79rem;
            color: var(--rs-muted);
            margin-top: 0.25rem;
            line-height: 1.35;
        }}

        /* Caveat callouts: reserved for the amber accent, used sparingly */
        .rs-callout {{
            border-left: 3px solid var(--rs-caveat);
            background-color: var(--rs-caveat-bg);
            padding: 0.8rem 1.05rem;
            margin: 0.9rem 0;
            font-size: 0.93rem;
            line-height: 1.55;
            color: var(--rs-ink);
        }}
        .rs-callout-title {{
            font-weight: 600;
            font-size: 0.79rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--rs-caveat);
            margin-bottom: 0.35rem;
        }}

        /* Neutral notes: for context that isn't a warning */
        .rs-note {{
            border-left: 3px solid var(--rs-steel-pale);
            background-color: var(--rs-surface);
            padding: 0.8rem 1.05rem;
            margin: 0.9rem 0;
            font-size: 0.93rem;
            line-height: 1.55;
            color: var(--rs-ink);
        }}
        .rs-note-title {{
            font-weight: 600;
            font-size: 0.79rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--rs-steel);
            margin-bottom: 0.35rem;
        }}

        .rs-caption {{
            font-size: 0.81rem;
            color: var(--rs-muted);
            margin-top: -0.3rem;
            margin-bottom: 0.9rem;
            line-height: 1.5;
        }}

        .rs-footer {{
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid var(--rs-border);
            font-size: 0.79rem;
            color: var(--rs-muted);
            line-height: 1.6;
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--rs-border);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# UI helper components
# ---------------------------------------------------------------------------


def kicker(num: str, label: str) -> None:
    st.markdown(
        f'<div class="rs-kicker"><span class="rs-kicker-num">{num}</span>{label}</div>',
        unsafe_allow_html=True,
    )


def lede(text: str) -> None:
    st.markdown(f'<div class="rs-lede">{text}</div>', unsafe_allow_html=True)


def divider() -> None:
    st.markdown('<hr class="rs-divider" />', unsafe_allow_html=True)


def caption(text: str) -> None:
    st.markdown(f'<div class="rs-caption">{text}</div>', unsafe_allow_html=True)


def caveat(title: str, body: str) -> None:
    st.markdown(
        f'<div class="rs-callout"><div class="rs-callout-title">{title}</div>{body}</div>',
        unsafe_allow_html=True,
    )


def note(title: str, body: str) -> None:
    st.markdown(
        f'<div class="rs-note"><div class="rs-note-title">{title}</div>{body}</div>',
        unsafe_allow_html=True,
    )


def metric_row(items: list[tuple[str, str]]) -> None:
    """items: list of (value, label) pairs, rendered as a compact strip."""
    cells = "".join(
        f'<div class="rs-metric"><div class="rs-metric-value">{value}</div>'
        f'<div class="rs-metric-label">{label}</div></div>'
        for value, label in items
    )
    st.markdown(f'<div class="rs-metric-row">{cells}</div>', unsafe_allow_html=True)


def apply_layout(fig: go.Figure, height: int = 380, show_legend: bool = False) -> go.Figure:
    """Shared Plotly styling. Legends are off by default: most charts here
    have a single series and a legend would only repeat the title. The two
    charts that genuinely need one pass show_legend=True and get extra top
    margin so the legend never overlaps the title."""
    top_margin = 78 if show_legend else 46
    fig.update_layout(
        font=dict(family=BODY_FONT, color=INK, size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=20, t=top_margin, b=10),
        height=height,
        showlegend=show_legend,
        title=dict(font=dict(size=15, color=INK), x=0, xanchor="left", y=0.97, yanchor="top"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.06,
            xanchor="left",
            x=0,
            font=dict(size=12),
        ),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family=BODY_FONT),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor=BORDER, ticks="outside", tickcolor=BORDER)
    fig.update_yaxes(showgrid=True, gridcolor=BORDER, zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@st.cache_data
def load_csv(relative_path: str) -> pd.DataFrame | None:
    path = OUTPUTS_DIR / relative_path
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def missing(relative_path: str) -> None:
    st.warning(
        f"Expected output file not found: `outputs/{relative_path}`. "
        f"Run `python python/generate_outputs.py` from the project root "
        f"(or the SQL pipeline in `sql/`) to regenerate `outputs/`, then reload this page."
    )


FILES = {
    "monthly_new_accounts": "acquisition/monthly_new_accounts.csv",
    "by_referral_source": "acquisition/by_referral_source.csv",
    "by_plan_tier_acq": "acquisition/by_plan_tier.csv",
    "by_industry": "acquisition/by_industry.csv",
    "by_country": "acquisition/by_country.csv",
    "monthly_mrr": "mrr/monthly_aggregate_mrr.csv",
    "mrr_by_tier": "mrr/monthly_mrr_by_plan_tier.csv",
    "conversion_overall": "conversion/subscription_level_overall.csv",
    "conversion_by_tier": "conversion/subscription_level_by_plan_tier.csv",
    "conversion_account": "conversion/account_level_overall.csv",
    "retention_curve": "retention/pooled_retention_curve.csv",
    "top_features": "engagement/top_features_by_usage.csv",
    "engagement_churn_status": "engagement/churn_status_engagement_summary.csv",
    "monthly_churn": "churn/monthly_churn_events.csv",
    "churn_by_reason": "churn/by_reason_code.csv",
    "churn_by_plan": "churn/by_plan_tier.csv",
    "repeat_churn": "churn/repeat_churn_summary.csv",
    "support_volume": "support/volume_and_resolution_by_churn_status.csv",
    "support_priority": "support/priority_mix_by_churn_status.csv",
}


@st.cache_data
def load_all() -> dict[str, pd.DataFrame | None]:
    return {key: load_csv(path) for key, path in FILES.items()}


# ===========================================================================
# PAGE 01. OVERVIEW
# ===========================================================================


def page_overview(data: dict) -> None:
    kicker("01", "Overview")
    st.title("RavenStack SaaS Analytics")
    lede(
        "A SQL-first analysis of a synthetic SaaS dataset called RavenStack, covering "
        "January 2023 through December 2024: 500 accounts, about 5,000 subscription "
        "records, 25,000 feature-usage events, 2,000 support tickets, and 600 churn "
        "events. This page explains what is in the dataset and what to know before "
        "reading the numbers on the pages that follow."
    )

    monthly_acc = data["monthly_new_accounts"]
    repeat_churn = data["repeat_churn"]
    conv = data["conversion_overall"]
    mrr = data["monthly_mrr"]
    retention = data["retention_curve"]

    if monthly_acc is None or repeat_churn is None or conv is None:
        missing("acquisition/monthly_new_accounts.csv (or related files)")
        return

    total_accounts = int(monthly_acc["new_accounts"].sum())
    total_churn_events = int(repeat_churn["total_churn_events"].iloc[0])
    unique_churned = int(repeat_churn["unique_churned_accounts"].iloc[0])
    conv_rate = conv["subscription_level_conversion_rate_pct"].iloc[0]
    latest_mrr_row = mrr.sort_values("month_start").iloc[-1] if mrr is not None else None
    ret_month6 = (
        retention.loc[retention["months_since_signup"] == 6, "retention_rate_pct_eligible_cohorts_only"].iloc[0]
        if retention is not None
        else None
    )

    st.markdown("### At a glance")
    row1 = [
        (f"{total_accounts:,}", "Total accounts, January 2023 through December 2024"),
        (f"{total_churn_events:,} events", f"Churn events, from {unique_churned:,} unique accounts"),
        (f"{conv_rate:.1f}%", "Trial to paid conversion, subscription-level proxy"),
    ]
    if latest_mrr_row is not None:
        row1.append((f"${latest_mrr_row['aggregate_subscription_mrr']:,.0f}", "Aggregate subscription-record MRR, December 2024"))
    metric_row(row1)
    caption(
        "Every figure above is defined precisely on its own page, together with the caveat "
        "that applies to it. None of these numbers are meant to be quoted on their own."
    )

    caveat(
        "Interpretation notes: please read before the rest of this dashboard",
        "RavenStack is a <strong>synthetic</strong> dataset built for portfolio purposes, not a real "
        "company's data. Several of its structural properties change how the headline metrics should "
        "be read: accounts routinely hold between 5 and 14 concurrently open subscription records, "
        "about 90% of subscription records never receive an end date, and roughly 70% of accounts "
        "have at least one churn event on file. These properties are documented in full on the "
        "<strong>Data Quality</strong> page. None of the figures on this dashboard have been adjusted "
        "to compensate for them. They are shown exactly as computed, with the caveat that explains them "
        "placed right next to the number.",
    )

    divider()
    st.markdown("### What the data suggests")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Acquisition and revenue**")
        st.write(
            "Account acquisition is spread across five referral channels with no single channel "
            "dominating volume. Aggregate subscription-record MRR grows steadily across the "
            "observation window. That growth is driven by the accumulation of open subscription "
            "records over time, not by a conventional net-new-revenue signal. The Revenue page "
            "explains why."
        )
    with col2:
        st.markdown("**Retention, churn, and support**")
        ret_text = f"{ret_month6:.1f}%" if ret_month6 is not None else "n/a"
        st.write(
            f"The observed six-month account subscription retention rate is high, at {ret_text}, "
            "but this reflects a structural ceiling effect rather than genuinely low attrition. "
            "The Conversion & Retention page walks through why. Support activity, meanwhile, shows "
            "no meaningful difference between churned and non-churned accounts when compared across "
            "each account's whole history."
        )

    divider()
    st.markdown("### How to read this dashboard")
    st.write(
        "Each page below states the precise metric definition next to the number, not just the "
        "number by itself. Where a figure could be mistaken for a standard business KPI, such as "
        "\"MRR\" or \"retention,\" this dashboard uses the project's exact terminology, for example "
        "\"Aggregate Subscription-Record MRR,\" and puts the relevant caveat directly beside the "
        "chart rather than in a footnote you might skip. If you only have time for one other page, "
        "make it Data Quality: it explains the structural quirks that shape almost everything else "
        "here."
    )


# ===========================================================================
# PAGE 02. ACQUISITION
# ===========================================================================


def page_acquisition(data: dict) -> None:
    kicker("02", "Acquisition")
    st.title("Account Acquisition")
    lede(
        "How the 500 RavenStack accounts were acquired, broken down by signup month, "
        "referral channel, plan tier, industry, and country. These are simple counts of "
        "accounts, not a measure of revenue quality or long-term value by channel."
    )

    monthly = data["monthly_new_accounts"]
    if monthly is not None:
        st.markdown("### Monthly new account acquisition")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=monthly["month_label"],
                y=monthly["new_accounts"],
                mode="lines+markers",
                line=dict(color=SLATE, width=2.5),
                marker=dict(size=5, color=SLATE),
                fill="tozeroy",
                fillcolor="rgba(51,83,138,0.09)",
                name="New accounts",
            )
        )
        fig.update_layout(title="New accounts by signup month, January 2023 through December 2024")
        fig.update_yaxes(title="New accounts")
        st.plotly_chart(apply_layout(fig), width="stretch")
        caption(
            "Counted by calendar month of signup_date, joined to the full calendar spine so months "
            "with zero signups are shown as zero rather than omitted. Monthly totals sum to 500 "
            "accounts, the full account base."
        )
    else:
        missing(FILES["monthly_new_accounts"])

    divider()
    st.write(
        "The next four charts break the same 500 accounts down by referral source, plan tier, "
        "industry, and country, so you can see how acquisition is distributed along each dimension "
        "separately."
    )
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Referral source")
        ref = data["by_referral_source"]
        if ref is not None:
            ref_sorted = ref.sort_values("accounts_acquired")
            fig = go.Figure(
                go.Bar(
                    x=ref_sorted["accounts_acquired"],
                    y=ref_sorted["referral_source"],
                    orientation="h",
                    marker_color=SLATE,
                    text=ref_sorted["pct_of_total_accounts"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Accounts acquired by referral source")
            fig.update_xaxes(title="Accounts")
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
            st.write(
                "Acquisition is fairly evenly spread across the five recorded referral sources, "
                "with organic in the lead but no single source dominating account volume. This "
                "reflects account counts only. The dataset does not support attributing revenue "
                "quality or retention to any particular channel."
            )
        else:
            missing(FILES["by_referral_source"])

    with col2:
        st.markdown("### Plan tier at signup")
        tier = data["by_plan_tier_acq"]
        if tier is not None:
            tier_sorted = tier.sort_values("account_count")
            fig = go.Figure(
                go.Bar(
                    x=tier_sorted["account_count"],
                    y=tier_sorted["plan_tier"],
                    orientation="h",
                    marker_color=STEEL,
                    text=tier_sorted["pct_of_total_accounts"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Accounts by plan tier")
            fig.update_xaxes(title="Accounts")
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
            st.write(
                "Plan tier distribution at the account level is fairly even across Basic, Pro, and "
                "Enterprise. This is the account's recorded plan_tier field, which is a separate, "
                "simpler concept from the many subscription-record-level plan tiers a single account "
                "can hold over time. Revenue by plan tier is covered on the Revenue page."
            )
        else:
            missing(FILES["by_plan_tier_acq"])

    divider()
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("### Industry")
        ind = data["by_industry"]
        if ind is not None:
            ind_sorted = ind.sort_values("account_count")
            fig = go.Figure(
                go.Bar(
                    x=ind_sorted["account_count"],
                    y=ind_sorted["industry"],
                    orientation="h",
                    marker_color=STEEL_LIGHT,
                    text=ind_sorted["pct_of_total_accounts"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Accounts by industry")
            fig.update_xaxes(title="Accounts")
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
            st.write(
                "DevTools and FinTech account for the largest shares of accounts, with the remaining "
                "three industries close behind. The spread across industries is moderate in both "
                "directions, without an extreme concentration in any one vertical."
            )
        else:
            missing(FILES["by_industry"])

    with col4:
        st.markdown("### Country")
        country = data["by_country"]
        if country is not None:
            country_sorted = country.sort_values("account_count")
            fig = go.Figure(
                go.Bar(
                    x=country_sorted["account_count"],
                    y=country_sorted["country"],
                    orientation="h",
                    marker_color=MUTED,
                    text=country_sorted["pct_of_total_accounts"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Accounts by country")
            fig.update_xaxes(title="Accounts")
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
            st.write(
                "The account base is concentrated in the United States, at 58.2% of all accounts, "
                "with the United Kingdom, India, Australia, Germany, Canada, and France making up "
                "the rest. This concentration is a property of how the dataset was generated, not a "
                "finding about acquisition strategy."
            )
        else:
            missing(FILES["by_country"])


# ===========================================================================
# PAGE 03. REVENUE
# ===========================================================================


def page_revenue(data: dict) -> None:
    kicker("03", "Revenue")
    st.title("Aggregate Subscription-Record MRR")
    lede(
        "This page shows the project's revenue metric exactly as it is defined in the SQL "
        "layer. Read the note below before looking at the chart: the metric's name is "
        "deliberately precise, because the plain phrase \"MRR\" would be misleading here."
    )

    caveat(
        "This is not company MRR",
        "This metric sums <code>mrr_amount</code> across every subscription record that is open in a "
        "given month. It does <strong>not</strong> deduplicate by account. Because accounts routinely "
        "hold between 5 and 14 concurrently open subscription records, this figure counts revenue "
        "two, three, or more times over for any account with multiple open records in the same month. "
        "Throughout this project it is called <strong>Aggregate Subscription-Record MRR</strong> and "
        "is never referred to as \"Company MRR,\" \"Account MRR,\" or \"ARR.\" No ARR, no net revenue "
        "retention, no expansion revenue, and no customer lifetime value figures are computed "
        "anywhere in this project.",
    )

    mrr = data["monthly_mrr"]
    if mrr is not None:
        latest = mrr.sort_values("month_start").iloc[-1]
        metric_row(
            [
                (f"${latest['aggregate_subscription_mrr']:,.0f}", f"Aggregate Subscription-Record MRR, {latest['month_label']}"),
                (f"{int(latest['active_subscription_records']):,}", "Open subscription records counted that month"),
            ]
        )

        st.markdown("### Aggregate Subscription-Record MRR over time")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=mrr["month_label"],
                y=mrr["aggregate_subscription_mrr"],
                mode="lines",
                line=dict(color=SLATE, width=2.5),
                fill="tozeroy",
                fillcolor="rgba(51,83,138,0.09)",
                name="Aggregate Subscription-Record MRR",
            )
        )
        fig.update_layout(title="Sum of mrr_amount across all open subscription records, by month")
        fig.update_yaxes(title="USD", tickprefix="$", tickformat=",.0f")
        st.plotly_chart(apply_layout(fig), width="stretch")
        caption(
            "The line climbs continuously because open subscription records accumulate over time: "
            "about 90% of them never receive an end date. That upward slope is a property of the "
            "data model, not evidence of net revenue growth in the conventional sense."
        )
    else:
        missing(FILES["monthly_mrr"])

    divider()
    st.markdown("### Aggregate Subscription-Record MRR by plan tier")
    st.write(
        "The chart below breaks the same total down by plan tier, so you can see which tier "
        "contributes the most to the aggregate figure over time. It is a composition view of the "
        "same double-counted metric shown above, not a separate or more reliable revenue number."
    )
    mrr_tier = data["mrr_by_tier"]
    if mrr_tier is not None:
        fig = go.Figure()
        for col, color, label in [
            ("basic_mrr", STEEL_PALE, "Basic"),
            ("pro_mrr", STEEL, "Pro"),
            ("enterprise_mrr", SLATE, "Enterprise"),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=mrr_tier["month_label"],
                    y=mrr_tier[col],
                    mode="lines",
                    stackgroup="mrr",
                    line=dict(width=0.5, color=color),
                    fillcolor=color,
                    name=label,
                )
            )
        fig.update_layout(title="Aggregate Subscription-Record MRR composition by plan tier")
        fig.update_yaxes(title="USD", tickprefix="$", tickformat=",.0f")
        st.plotly_chart(apply_layout(fig, show_legend=True), width="stretch")
        st.write(
            "Enterprise-tier subscription records make up a growing majority of aggregate MRR by "
            "the end of the observation window. That is consistent with Enterprise records carrying "
            "the highest per-record mrr_amount of the three tiers, and says nothing about how many "
            "distinct Enterprise accounts exist."
        )
    else:
        missing(FILES["mrr_by_tier"])


# ===========================================================================
# PAGE 04. CONVERSION & RETENTION
# ===========================================================================


def page_conversion_retention(data: dict) -> None:
    kicker("04", "Conversion & Retention")
    st.title("Conversion & Retention")
    lede(
        "These are two of the most important analyses in the project, and also the two "
        "easiest to misread as conventional SaaS KPIs. Both sections below lead with the "
        "number, then explain exactly what it does and does not mean before you draw any "
        "conclusions from it."
    )

    st.markdown("### Trial to paid conversion")
    st.write(
        "The dataset has no explicit \"trial converted to paid\" event, so this metric is "
        "built as a proxy: it checks whether an account that once held a trial subscription "
        "record later also held a paid one."
    )
    conv = data["conversion_overall"]
    conv_acct = data["conversion_account"]
    if conv is not None:
        row = conv.iloc[0]
        metric_row(
            [
                (f"{row['subscription_level_conversion_rate_pct']:.1f}%", "Subscription-level proxy conversion rate"),
                (f"{int(row['total_trial_subscription_records']):,}", "Total trial subscription records"),
                (f"{int(row['trial_records_with_later_paid_record']):,}", "Records with a later paid record on the same account"),
            ]
        )
        caveat(
            "This is a proxy, not a certified causal funnel",
            "A trial subscription record counts as \"converted\" if the same account holds at least "
            "one paid subscription record with a start date on or after the trial's start date. "
            "Because accounts hold many concurrently open subscriptions, a trial record and a paid "
            "record can coexist without one having actually caused the other. For example, a trial "
            "for a new seat might open while an existing paid plan is already active on the same "
            "account. That is why this is reported as a <strong>subscription-level proxy</strong>, "
            "and why the account-level figure below is not treated as the headline conversion metric.",
        )

        if conv_acct is not None:
            acct_row = conv_acct.iloc[0]
            st.markdown("#### Account-level conversion, shown for completeness rather than as a KPI")
            st.write(
                f"Of {int(acct_row['accounts_with_any_trial'])} accounts that ever held a trial "
                f"subscription record, {int(acct_row['accounts_with_trial_and_paid'])} also held a "
                f"paid record at some point: a **{acct_row['account_level_conversion_rate_pct']:.1f}%** "
                "rate. This number is structurally close to meaningless as a KPI, because accounts "
                "can hold many subscription records over time regardless of order. Almost any "
                "account that ever had a trial will eventually also show a paid record somewhere in "
                "its history, so it is not presented as a real business conversion rate."
            )

        conv_tier = data["conversion_by_tier"]
        if conv_tier is not None:
            st.markdown("#### By plan tier")
            tier_sorted = conv_tier.sort_values("conversion_rate_pct")
            fig = go.Figure(
                go.Bar(
                    x=tier_sorted["conversion_rate_pct"],
                    y=tier_sorted["plan_tier"],
                    orientation="h",
                    marker_color=SLATE,
                    text=tier_sorted["conversion_rate_pct"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Subscription-level conversion proxy by plan tier")
            fig.update_xaxes(title="Conversion rate (%)", range=[0, 100])
            st.plotly_chart(apply_layout(fig, height=280), width="stretch")
            st.write(
                "The proxy conversion rate is broadly similar across Basic, Pro, and Enterprise plan "
                "tiers. No tier stands out as meaningfully stronger or weaker at converting trials."
            )
    else:
        missing(FILES["conversion_overall"])

    divider()
    st.markdown("### Observed account subscription retention")
    st.write(
        "This is the single most important chart to read carefully on this dashboard. The number "
        "looks impressive on its own, and that is exactly why the explanation below it matters."
    )
    retention = data["retention_curve"]
    if retention is not None:
        m0 = retention.loc[retention["months_since_signup"] == 0, "retention_rate_pct_eligible_cohorts_only"].iloc[0]
        m6 = retention.loc[retention["months_since_signup"] == 6, "retention_rate_pct_eligible_cohorts_only"].iloc[0]
        metric_row(
            [
                (f"{m0:.1f}%", "Observed retention at month 0"),
                (f"{m6:.1f}%", "Observed retention at month 6"),
            ]
        )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=retention["months_since_signup"],
                y=retention["retention_rate_pct_eligible_cohorts_only"],
                mode="lines+markers",
                line=dict(color=SLATE, width=2.5),
                marker=dict(size=6, color=SLATE),
                name="Observed retention",
            )
        )
        fig.add_vrect(
            x0=-0.4, x1=3.4,
            fillcolor=CAVEAT, opacity=0.07, line_width=0,
            annotation_text="onboarding ramp, not attrition",
            annotation_position="top left",
            annotation_font_size=11,
            annotation_font_color=CAVEAT,
        )
        fig.update_layout(title="Pooled observed account subscription retention by months since signup")
        fig.update_xaxes(title="Months since signup")
        fig.update_yaxes(title="Retention rate (%, eligible cohorts only)", range=[0, 105])
        st.plotly_chart(apply_layout(fig), width="stretch")

        caveat(
            "This is not \"98.9% customer retention\"",
            "What this chart shows is <strong>observed account-subscription retention</strong> under "
            "the project's specific definition of active: an account counts as retained in a given "
            "month if it holds at least one open subscription record at that time. The rate is "
            "measured only against the eligible cohort, meaning accounts old enough to have reached "
            "that month. Two documented, structural mechanisms explain the shape of this curve.<br><br>"
            "First, about 90% of subscription records never receive an end date. Once an account has "
            "any open record, it keeps registering as active under this definition indefinitely, "
            "regardless of what else happens to the account.<br>"
            "Second, there is often a substantial gap between an account's signup date and its first "
            "subscription start date, sometimes more than a year. That gap is why the curve rises "
            "from about 44% at month 0 to about 99% by month 6, instead of starting near 100% and "
            "declining the way a typical retention curve does: the early months mostly reflect "
            "accounts still arriving at their first open subscription record, not customers leaving.<br><br>"
            "Read this curve as a demonstration of how the dataset is structured, not as a claim that "
            "RavenStack retains 98.9% of its customers after six months.",
        )
    else:
        missing(FILES["retention_curve"])


# ===========================================================================
# PAGE 05. ENGAGEMENT
# ===========================================================================


def page_engagement(data: dict) -> None:
    kicker("05", "Engagement")
    st.title("Feature Engagement")
    lede(
        "This page looks at how the 40 tracked product features are used across all "
        "25,000 feature-usage events, and whether usage differs between accounts that "
        "have churned and accounts that have not."
    )

    note(
        "Scope of this analysis",
        "Only about 22% of feature-usage rows fall inside their linked subscription's active date "
        "window, a finding documented as data quality check 11. Because of that, feature engagement "
        "here is analyzed at the account level across an account's whole history, using the "
        "subscription foreign key purely as a technical bridge to reach <code>account_id</code>, "
        "rather than to scope usage to a specific subscription period.",
    )

    top_features = data["top_features"]
    if top_features is not None:
        st.markdown("### Usage volume by feature")
        top15 = top_features.sort_values("total_usage_count", ascending=False).head(15)
        top15_sorted = top15.sort_values("total_usage_count")
        fig = go.Figure(
            go.Bar(
                x=top15_sorted["total_usage_count"],
                y=top15_sorted["feature_name"],
                orientation="h",
                marker_color=SLATE,
            )
        )
        fig.update_layout(title="Top 15 of 40 features by total usage_count")
        fig.update_xaxes(title="Total usage count")
        st.plotly_chart(apply_layout(fig, height=460), width="stretch")

        top_row = top_features.sort_values("total_usage_count", ascending=False).iloc[0]
        bottom_of_top15 = top15["total_usage_count"].min()
        spread_pct = 100 * (top_row["total_usage_count"] - bottom_of_top15) / top_row["total_usage_count"]
        st.write(
            f"**{top_row['feature_name']}** has the highest total usage_count, at "
            f"{int(top_row['total_usage_count']):,}, but usage across the top 15 features is tightly "
            f"clustered: the 15th-ranked feature is within {spread_pct:.0f}% of the top. This is a "
            "ranking of usage volume, and it should be read as one. It is not a claim about which "
            "feature users value most."
        )
    else:
        missing(FILES["top_features"])

    divider()
    st.markdown("### Engagement: churned versus non-churned accounts")
    st.write(
        "The comparison below asks a simple question: across each account's entire recorded "
        "history, do accounts that eventually churned use features any differently than accounts "
        "that never churned?"
    )
    eng_status = data["engagement_churn_status"]
    if eng_status is not None:
        eng_status = eng_status.copy()
        eng_status["label"] = eng_status["is_churned_account"].map({True: "Churned", False: "Non-churned"})
        fig = go.Figure(
            go.Bar(
                x=eng_status["label"],
                y=eng_status["usage_count_per_account"],
                marker_color=[STEEL_PALE, SLATE],
                text=eng_status["usage_count_per_account"].map(lambda v: f"{v:,.0f}"),
                textposition="outside",
            )
        )
        fig.update_layout(title="Whole-history usage_count per account, by churn status")
        fig.update_yaxes(title="Usage count per account")
        st.plotly_chart(apply_layout(fig, height=340), width="stretch")

        row_c = eng_status.loc[eng_status["is_churned_account"] == True].iloc[0]
        row_n = eng_status.loc[eng_status["is_churned_account"] == False].iloc[0]
        diff_pct = 100 * abs(row_c["usage_count_per_account"] - row_n["usage_count_per_account"]) / row_n["usage_count_per_account"]
        st.write(
            f"Non-churned accounts average {row_n['usage_count_per_account']:,.0f} usage_count across "
            f"their full observed history. Churned accounts average {row_c['usage_count_per_account']:,.0f}, "
            f"a difference of only {diff_pct:.1f}%."
        )
        caveat(
            "No material difference is observed",
            "No material difference is observed in whole-history feature engagement between churned "
            "and non-churned accounts. This is an observed null result under a whole-history "
            "comparison. It does not mean that feature engagement has no effect on churn, because no "
            "causal analysis was performed here and usage is not scoped to the period before or after "
            "any specific churn event.",
        )
    else:
        missing(FILES["engagement_churn_status"])


# ===========================================================================
# PAGE 06. CHURN & SUPPORT
# ===========================================================================


def page_churn_support(data: dict) -> None:
    kicker("06", "Churn & Support")
    st.title("Churn & Support")
    lede(
        "This page combines two related questions: how churn behaves across the account "
        "base over time, and whether support activity looks any different for accounts "
        "that eventually churn. Read the two callouts closely: both sections have a "
        "distinction that is easy to gloss over."
    )

    st.markdown("### Churn: events versus unique accounts")
    st.write(
        "The first thing to know about churn in this dataset is that \"a churn event\" and \"a "
        "churned account\" are not the same thing, because some accounts churn more than once."
    )
    repeat = data["repeat_churn"]
    if repeat is not None:
        r = repeat.iloc[0]
        metric_row(
            [
                (f"{int(r['total_churn_events']):,}", "Total churn events"),
                (f"{int(r['unique_churned_accounts']):,}", "Unique churned accounts"),
                (f"{int(r['repeat_churn_accounts']):,}", "Accounts with 2 or more churn events"),
                (f"{int(r['reactivation_events']):,}", "Explicit reactivation events"),
            ]
        )
        caveat(
            "Events and accounts are not the same number",
            "There were <strong>600 churn events</strong> across <strong>352 unique accounts</strong>. "
            "Of those 352 accounts, 175 churned more than once, and 61 events are explicitly flagged "
            "as reactivations, meaning the account came back after churning. "
            "<code>raw_churn_events</code> is used as the sole source of truth for churn throughout "
            "this project. <code>raw_accounts.churn_flag</code> is not used anywhere downstream, "
            "because the two signals conflict substantially, a finding documented as data quality "
            "check 9.",
        )
    else:
        missing(FILES["repeat_churn"])

    monthly_churn = data["monthly_churn"]
    if monthly_churn is not None:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=monthly_churn["month_label"],
                y=monthly_churn["churn_events"],
                marker_color=STEEL_PALE,
                name="Churn events",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=monthly_churn["month_label"],
                y=monthly_churn["unique_churned_accounts"],
                mode="lines+markers",
                line=dict(color=SLATE, width=2.5),
                marker=dict(size=5, color=SLATE),
                name="Unique churned accounts",
            )
        )
        fig.update_layout(title="Monthly churn events compared with unique churned accounts")
        fig.update_yaxes(title="Count")
        st.plotly_chart(apply_layout(fig, show_legend=True), width="stretch")
        caption(
            "The gap between each bar and the line beneath it is repeat churn within that same "
            "month: accounts that churned more than once in the same 30-day window. Both series "
            "climb toward the end of the observation window, which makes sense since more accounts "
            "have had time to churn, and in some cases to churn again, as the dataset progresses."
        )
    else:
        missing(FILES["monthly_churn"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### By reason code")
        reason = data["churn_by_reason"]
        if reason is not None:
            reason_sorted = reason.sort_values("churn_events")
            fig = go.Figure(
                go.Bar(
                    x=reason_sorted["churn_events"],
                    y=reason_sorted["reason_code"],
                    orientation="h",
                    marker_color=SLATE,
                    text=reason_sorted["pct_of_all_churn_events"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Churn events by reason code")
            fig.update_xaxes(title="Churn events")
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
            caption(
                "These are event-level counts, out of 600 total, not account-level counts. An "
                "account with three churn events logged for the same reason contributes three to "
                "that reason's total."
            )
        else:
            missing(FILES["churn_by_reason"])

    with col2:
        st.markdown("#### By plan tier")
        plan = data["churn_by_plan"]
        if plan is not None:
            plan_sorted = plan.sort_values("pct_of_plan_accounts_with_churn_event")
            fig = go.Figure(
                go.Bar(
                    x=plan_sorted["pct_of_plan_accounts_with_churn_event"],
                    y=plan_sorted["plan_tier"],
                    orientation="h",
                    marker_color=STEEL,
                    text=plan_sorted["pct_of_plan_accounts_with_churn_event"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Share of plan-tier accounts with a churn event")
            fig.update_xaxes(title="Percent of accounts on that plan", range=[0, 100])
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
            caption(
                "All three plan tiers show a similar churned-account share, ranging from the high "
                "60s to the low 70s percent."
            )
        else:
            missing(FILES["churn_by_plan"])

    divider()
    st.markdown("### Support activity: churned versus non-churned accounts")
    st.write(
        "If poor support experiences were driving churn in this dataset, you would expect to see "
        "churned accounts show up with worse support outcomes. Here is what the data actually shows."
    )
    support_vol = data["support_volume"]
    if support_vol is not None:
        sv = support_vol.copy()
        sv["label"] = sv["is_churned_account"].map({True: "Churned", False: "Non-churned"})
        col3, col4 = st.columns(2)
        with col3:
            fig = go.Figure(
                go.Bar(
                    x=sv["label"],
                    y=sv["escalation_rate_pct"],
                    marker_color=[STEEL_PALE, SLATE],
                    text=sv["escalation_rate_pct"].map(lambda v: f"{v:.1f}%"),
                    textposition="outside",
                )
            )
            fig.update_layout(title="Escalation rate by churn status")
            fig.update_yaxes(title="Escalation rate (%)")
            st.plotly_chart(apply_layout(fig, height=320), width="stretch")
        with col4:
            fig2 = go.Figure(
                go.Bar(
                    x=sv["label"],
                    y=sv["avg_resolution_time_hours"],
                    marker_color=[STEEL_PALE, SLATE],
                    text=sv["avg_resolution_time_hours"].map(lambda v: f"{v:.1f}h"),
                    textposition="outside",
                )
            )
            fig2.update_layout(title="Average resolution time by churn status")
            fig2.update_yaxes(title="Hours")
            st.plotly_chart(apply_layout(fig2, height=320), width="stretch")

        row_c = sv.loc[sv["is_churned_account"] == True].iloc[0]
        row_n = sv.loc[sv["is_churned_account"] == False].iloc[0]
        st.write(
            f"Churned accounts, {int(row_c['accounts'])} accounts and {int(row_c['tickets'])} tickets "
            f"in total, show a {row_c['escalation_rate_pct']:.1f}% escalation rate, compared with "
            f"{row_n['escalation_rate_pct']:.1f}% for non-churned accounts "
            f"({int(row_n['accounts'])} accounts, {int(row_n['tickets'])} tickets). Average "
            f"resolution time is nearly identical between the two groups, at "
            f"{row_c['avg_resolution_time_hours']:.2f} hours for churned accounts versus "
            f"{row_n['avg_resolution_time_hours']:.2f} hours for non-churned accounts."
        )
        caveat(
            "An observed association, not a causal effect",
            "No meaningful difference is observed in support activity between the two groups under "
            "this whole-history comparison. Ticket timing is not scoped to before or after any "
            "specific churn event: a ticket submitted after an account reactivated is still counted "
            "in the \"churned\" group for that account's entire lifetime. Treat this as an observed "
            "null result, not as a causal conclusion about whether support quality affects churn.",
        )
    else:
        missing(FILES["support_volume"])


# ===========================================================================
# PAGE 07. DATA QUALITY
# ===========================================================================


def page_data_quality(data: dict) -> None:
    kicker("07", "Data Quality")
    st.title("Data Quality")
    lede(
        "This page summarizes the 16 diagnostic checks run in "
        "`sql/01_data_quality_checks.sql`, documented in full in `docs/data_audit.md`, "
        "along with the suspicious patterns flagged in `docs/results_review.md`. Nothing "
        "here has been corrected in the raw data. Each finding is treated as a fact about "
        "the dataset that every downstream analysis on this dashboard is built to account for."
    )

    st.markdown("### Dataset health")
    st.write("All five raw tables loaded at their expected row counts, with no rows dropped or duplicated.")
    health_cols = st.columns(5)
    health = [
        ("raw_accounts", "500", True),
        ("raw_subscriptions", "5,000", True),
        ("raw_feature_usage", "25,000", True),
        ("raw_support_tickets", "2,000", True),
        ("raw_churn_events", "600", True),
    ]
    for col, (table, actual, ok) in zip(health_cols, health):
        with col:
            st.markdown(f"**{table}**")
            st.write(f"{actual} rows")
            st.caption("matches expected count" if ok else "mismatch")

    st.write(
        "All four foreign key relationships (subscriptions to accounts, feature usage to "
        "subscriptions, support tickets to accounts, and churn events to accounts) have zero orphan "
        "rows. Every primary key is confirmed unique except `raw_feature_usage.usage_id`, which has "
        "21 duplicate values and is therefore never used as a row-identity key."
    )

    divider()
    st.markdown("### Structural flags")
    st.write(
        "These are the properties of the dataset that most directly shape how the metrics on other "
        "pages should be interpreted. Expand each one for the full finding."
    )

    flags = [
        (
            "Subscription overlap",
            "Accounts hold between 5 and 14 concurrently open subscription records at once, with an "
            "average of about 9. This is the single most consequential constraint in the dataset: it "
            "rules out computing a meaningful \"current plan per account\" or a conventional net-MRR-"
            "retention metric anywhere in the project.",
        ),
        (
            "Open-ended subscriptions",
            "About 90.3% of subscription records have no end date recorded. A missing end date means "
            "the record is still open, not that the date is simply unknown. This is the main driver "
            "behind the shape of the retention curve on the Conversion & Retention page.",
        ),
        (
            "Signup-to-first-subscription gap",
            "The gap between an account's signup date and its first subscription start date is often "
            "substantial, in some cases exceeding a year. This depresses the earliest months of "
            "retention figures, and is documented as a structural property of the dataset rather than "
            "an error.",
        ),
        (
            "Feature usage temporal mismatch",
            "Only about 22% of feature usage rows fall inside their linked subscription's active date "
            "window. Because of that, feature engagement is analyzed at the account and global level "
            "rather than scoped to individual subscription periods.",
        ),
        (
            "Churn events versus unique accounts",
            "600 churn events span 352 unique accounts, and 175 of those accounts have two or more "
            "events each. Event counts and account counts are always reported separately in this "
            "project, since conflating them would overstate how concentrated churn actually is.",
        ),
        (
            "raw_accounts.churn_flag is unreliable",
            "The churn_flag field on raw_accounts conflicts substantially with whether the same "
            "account actually appears in raw_churn_events. Because of that conflict, raw_churn_events "
            "is used as the sole source of truth for churn throughout this project. The churn_flag "
            "field is retained in the raw table as-is, but it is never queried downstream.",
        ),
        (
            "Satisfaction score bias",
            "About 41.3% of support tickets have no satisfaction_score at all, and where a score is "
            "present, it only ever falls between 3.0 and 5.0. That combination points to selection "
            "bias in how the score gets recorded, so this field is never treated as representative of "
            "overall support quality.",
        ),
    ]
    for title, body in flags:
        with st.expander(title):
            st.markdown(body, unsafe_allow_html=True)

    divider()
    st.markdown("### Suspicious patterns noticed during analysis")
    st.write(
        "These four patterns were flagged during results review specifically because, taken at face "
        "value, they could be misread as strong business signals. None of them have been \"fixed\" "
        "here. The point of this section is to show that they were noticed, investigated, and traced "
        "back to a specific mechanism in the data."
    )

    patterns = [
        (
            "Aggregate MRR never declines across the full 24-month window",
            "This follows directly from the near-90% NULL end-date rate: once a subscription record "
            "opens, it almost always stays open, so the sum of open-record mrr_amount can only "
            "accumulate upward.",
        ),
        (
            "Retention reaches close to 100% even though 70.4% of accounts have a churn event",
            "The retention metric is defined by whether an account has an open subscription record, "
            "not by whether the account is absent from raw_churn_events. An account can have a churn "
            "event on file and still hold an open subscription record under this definition, which "
            "means the two metrics are simply not measuring the same underlying thing.",
        ),
        (
            "Feature usage looks unusually uniform across all 40 features",
            "Total usage_count across the top 15 features clusters tightly within a narrow band. This "
            "is a property of how the synthetic dataset was generated, rather than a real "
            "differentiated usage pattern you would expect to see among a live product's features.",
        ),
        (
            "Observed six-month cumulative value per account rises roughly tenfold across cohorts",
            "This is consistent with the same open-record accumulation mechanism driving both the "
            "MRR and retention patterns above: later cohorts have simply had more subscription "
            "records accumulate by the six-month mark.",
        ),
    ]
    for title, body in patterns:
        note(title, body)


# ===========================================================================
# Navigation
# ===========================================================================

NAV_ITEMS: list[tuple[str, str]] = [
    ("01", "Overview"),
    ("02", "Acquisition"),
    ("03", "Revenue"),
    ("04", "Conversion & Retention"),
    ("05", "Engagement"),
    ("06", "Churn & Support"),
    ("07", "Data Quality"),
]

PAGE_FUNCTIONS = {
    "Overview": page_overview,
    "Acquisition": page_acquisition,
    "Revenue": page_revenue,
    "Conversion & Retention": page_conversion_retention,
    "Engagement": page_engagement,
    "Churn & Support": page_churn_support,
    "Data Quality": page_data_quality,
}


def render_footer() -> None:
    st.markdown(
        """
        <div class="rs-footer">
        RavenStack SaaS Analytics is a SQL-first portfolio project. All figures are read
        directly from generated CSVs under <code>outputs/</code>; no metric is computed by this
        application itself. Methodology, caveats, and full query definitions live in
        <code>sql/</code> and <code>docs/</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> str:
    if "rs_page" not in st.session_state:
        st.session_state.rs_page = "Overview"

    with st.sidebar:
        st.markdown('<div class="rs-wordmark">RavenStack</div>', unsafe_allow_html=True)
        st.markdown('<div class="rs-wordmark-sub">SaaS Analytics Workspace</div>', unsafe_allow_html=True)

        for num, label in NAV_ITEMS:
            is_active = st.session_state.rs_page == label
            if st.button(
                f"{num}   {label}",
                key=f"nav_{label}",
                type="primary" if is_active else "secondary",
                width="stretch",
            ):
                st.session_state.rs_page = label

        st.markdown("<hr />", unsafe_allow_html=True)
        st.markdown(
            '<div class="rs-sidebar-note">Synthetic dataset. Please read each page\'s '
            "caveats before quoting a number from it.</div>",
            unsafe_allow_html=True,
        )

    return st.session_state.rs_page


def main() -> None:
    inject_fonts()
    inject_css()
    data = load_all()
    current_page = render_sidebar()
    PAGE_FUNCTIONS[current_page](data)
    render_footer()


if __name__ == "__main__":
    main()