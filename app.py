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
# Palette. "Audit memo" identity: every figure on this dashboard is treated
# as a claim that needs a citation, so color is used to mark THAT distinction
# rather than to decorate. Three semantic accents, each with one job:
#   SLATE (indigo)  -> brand / structural chrome, the dashboard's own voice
#   DEFINE (green)  -> "here is what this term means" -- glossary material
#   CAVEAT (amber)  -> "read this before you trust the number above it"
# NOTE (steel) is a fourth, quieter tone for context that is neither.
# ---------------------------------------------------------------------------

INK = "#141A22"            # primary text, near-black ink
SLATE = "#28407A"          # primary accent: deep indigo, the dashboard's voice
STEEL = "#4B6E93"          # secondary accent, chart series & neutral notes
STEEL_LIGHT = "#7B9AB8"    # tertiary accent
STEEL_PALE = "#B9C9D9"     # quaternary accent, low-emphasis fills
MUTED = "#5E6C7F"          # muted gray-blue, captions and low-emphasis labels
BG = "#EEF1F3"             # page background, cool paper
SURFACE = "#E2E8EE"        # subtle panel background
BORDER = "#C7D1DC"         # hairline borders
CAVEAT = "#8C5A0E"         # muted amber, reserved for caveat and warning accents
CAVEAT_BG = "#FAF1DF"
DEFINE = "#2C6B4F"         # muted green, reserved for glossary/definition material
DEFINE_BG = "#E6F0EA"
SIDEBAR_BG = "#0C121C"     # sidebar background, near-black navy
SIDEBAR_SPINE = "#28407A"  # accent bar down the sidebar's edge, ledger-spine motif

CHART_SEQUENCE = [SLATE, STEEL, STEEL_LIGHT, MUTED, INK, STEEL_PALE, DEFINE]

# Three type roles instead of one sans font doing every job:
#   display serif  -> headings, carries the "memo" editorial voice
#   body sans      -> running prose, stays quiet and legible
#   data mono      -> every number, metric value, and code-like label, so
#                     figures always read as measured data, not typeset copy
# All three come from the IBM Plex superfamily (Serif / Sans / Mono) so the
# three roles read as one coherent type system rather than three unrelated
# typefaces stitched together. Each stack falls back to characterful system
# fonts (never a bare "serif"/"sans-serif" default) so the design holds up
# even if the webfonts are blocked by a privacy-hardened browser.
HEADING_FONT = (
    "'IBM Plex Serif', 'Iowan Old Style', 'Palatino Linotype', "
    "Palatino, Georgia, serif"
)

BODY_FONT = (
    "'IBM Plex Sans', -apple-system, 'Segoe UI Variable Display', "
    "'Segoe UI', system-ui, sans-serif"
)

MONO_FONT = (
    "'IBM Plex Mono', 'SFMono-Regular', ui-monospace, 'Cascadia Mono', "
    "Consolas, monospace"
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
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
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
            --rs-define: {DEFINE};
            --rs-define-bg: {DEFINE_BG};
            --rs-sidebar-spine: {SIDEBAR_SPINE};
            --rs-heading-font: {HEADING_FONT};
            --rs-body-font: {BODY_FONT};
            --rs-mono-font: {MONO_FONT};
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
            border-right: 3px solid var(--rs-sidebar-spine);
        }}
        section[data-testid="stSidebar"] > div {{
            padding-top: 1.5rem;
        }}
        section[data-testid="stSidebar"] * {{
            color: #DCE4F0;
        }}

        /* Masthead: reads like the front matter of a report, not app chrome */
        .rs-masthead-eyebrow {{
            font-family: var(--rs-mono-font);
            font-size: 0.68rem;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            color: #6B84A8;
            margin-bottom: 0.35rem;
        }}
        .rs-wordmark {{
            font-family: var(--rs-heading-font);
            font-size: 1.7rem;
            font-weight: 600;
            color: #FFFFFF;
            line-height: 1.08;
            margin-bottom: 0.15rem;
        }}
        .rs-wordmark-sub {{
            font-size: 0.78rem;
            line-height: 1.45;
            color: #8DA0BE;
            max-width: 15.5rem;
            margin-bottom: 1.1rem;
        }}
        .rs-sidebar-rule {{
            border: none;
            border-top: 1px solid #212E42;
            margin: 1rem 0;
        }}

        /* Nav: table-of-contents styling, left-aligned. Streamlit centers
           button labels by default via flex containers *inside* the
           button (not the button element itself), so justify-content on
           the button alone is not enough -- the inner wrapper and the <p>
           it renders into both need the override. Section numbers use
           backtick-code in the label text itself (Streamlit renders that
           as a real monospace chip; a hand-rolled HTML span won't render
           at all, since button labels don't support raw HTML). */
        section[data-testid="stSidebar"] div[data-testid="stButton"] {{
            margin-bottom: 0.15rem;
        }}
        section[data-testid="stSidebar"] button {{
            width: 100%;
            display: flex !important;
            justify-content: flex-start !important;
            font-family: var(--rs-body-font);
            font-size: 0.91rem;
            font-weight: 500;
            letter-spacing: 0.01em;
            border-radius: 6px;
            padding: 0.55rem 0.75rem;
            transition: background-color 0.12s ease, color 0.12s ease;
            box-shadow: none !important;
        }}
        section[data-testid="stSidebar"] button > div,
        section[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {{
            width: 100%;
            justify-content: flex-start !important;
            text-align: left !important;
        }}
        section[data-testid="stSidebar"] button p {{
            width: 100%;
            text-align: left !important;
        }}
        section[data-testid="stSidebar"] button code {{
            font-family: var(--rs-mono-font);
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            background: rgba(255,255,255,0.1);
            color: #C3D2E8;
            border-radius: 4px;
            padding: 0.12rem 0.4rem;
            margin-right: 0.5rem;
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
            border: 1px solid rgba(255,255,255,0.16);
            color: #FFFFFF;
            font-weight: 600;
        }}
        section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {{
            background-color: var(--rs-slate);
            color: #FFFFFF;
        }}
        section[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] code {{
            background: rgba(255,255,255,0.18);
            color: #FFFFFF;
        }}

        /* Active-page description: a single line that updates with the
           current page, rather than eight stacked paragraphs under every
           nav item. More informative in practice, since it's the one line
           you're actually likely to read, and it sidesteps Streamlit's
           default per-element spacing entirely. */
        .rs-nav-active-desc {{
            font-size: 0.78rem;
            line-height: 1.45;
            color: #8DA0BE;
            border-left: 2px solid var(--rs-sidebar-spine);
            padding: 0.1rem 0 0.1rem 0.65rem;
            margin: 0.5rem 0 0.2rem 0;
        }}

        section[data-testid="stSidebar"] hr {{
            border-color: #212E42;
            margin: 1.1rem 0;
        }}
        .rs-sidebar-note {{
            font-size: 0.76rem;
            line-height: 1.5;
            color: #7C8FAE;
        }}

        /* Reading key: explains what the three callout colors mean, once,
           so the color system means something instead of decorating. */
        .rs-legend-title {{
            font-family: var(--rs-mono-font);
            font-size: 0.68rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #6B84A8;
            margin-bottom: 0.5rem;
        }}
        .rs-legend-row {{
            display: flex;
            align-items: flex-start;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        .rs-legend-swatch {{
            flex: none;
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 2px;
            margin-top: 0.28rem;
        }}
        .rs-legend-text {{
            font-size: 0.75rem;
            line-height: 1.4;
            color: #96A9C7;
        }}
        .rs-legend-text strong {{
            color: #C9D5E6;
            font-weight: 600;
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
            font-family: var(--rs-mono-font);
            font-size: 0.72rem;
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
            font-family: var(--rs-mono-font);
            font-size: 1.6rem;
            font-weight: 600;
            color: var(--rs-ink);
            line-height: 1.2;
        }}
        .rs-metric-label {{
            font-size: 0.79rem;
            color: var(--rs-muted);
            margin-top: 0.3rem;
            line-height: 1.35;
        }}

        /* Pull-quote: the dashboard's single most important sentence, set
           in the heading serif at a larger size so it reads as a claim to
           be defended, not a caption to skim past. */
        .rs-pullquote {{
            font-family: var(--rs-heading-font);
            font-size: 1.3rem;
            font-weight: 600;
            line-height: 1.45;
            color: var(--rs-ink);
            border-left: 3px solid var(--rs-slate);
            padding: 0.2rem 0 0.2rem 1.1rem;
            margin: 1.1rem 0 1.3rem 0;
            max-width: 46rem;
        }}

        /* Three-up finding grid: the "dataset is unusual" visual summary on
           Overview. Amber-topped, since these are framed as facts to keep
           in mind rather than decorative stats. */
        .rs-finding-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1.2rem;
            margin: 1rem 0 1.2rem 0;
        }}
        .rs-finding {{
            border-top: 3px solid var(--rs-caveat);
            padding-top: 0.7rem;
        }}
        .rs-finding-stat {{
            font-family: var(--rs-mono-font);
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--rs-ink);
            line-height: 1.2;
            margin-bottom: 0.35rem;
        }}
        .rs-finding-title {{
            font-family: var(--rs-body-font);
            font-size: 0.86rem;
            font-weight: 600;
            color: var(--rs-ink);
            margin-bottom: 0.35rem;
        }}
        .rs-finding-body {{
            font-size: 0.85rem;
            line-height: 1.5;
            color: var(--rs-muted);
        }}
        @media (max-width: 900px) {{
            .rs-finding-grid {{ grid-template-columns: 1fr; }}
        }}

        /* Headline stat: a large number with its interpretive qualifier
           immediately beneath it -- used where a figure could otherwise be
           mistaken for an unqualified, triumphant KPI (e.g. retention). */
        .rs-headline {{
            margin: 0.6rem 0 0.2rem 0;
        }}
        .rs-headline-value {{
            font-family: var(--rs-heading-font);
            font-size: 2.6rem;
            font-weight: 600;
            color: var(--rs-ink);
            line-height: 1.05;
        }}
        .rs-headline-qualifier {{
            font-family: var(--rs-body-font);
            font-size: 0.92rem;
            font-style: italic;
            color: var(--rs-steel);
            margin-top: 0.3rem;
            max-width: 40rem;
        }}

        /* Proxy-vs-degenerate comparison, used on Conversion & Retention so
           the subscription-level proxy and the account-level figure are
           never read as two versions of the same KPI. */
        .rs-compare-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
            border: 1px solid var(--rs-border);
            margin: 0.9rem 0 1rem 0;
        }}
        .rs-compare-cell {{
            padding: 1rem 1.2rem;
        }}
        .rs-compare-cell + .rs-compare-cell {{
            border-left: 1px solid var(--rs-border);
        }}
        .rs-compare-eyebrow {{
            font-family: var(--rs-mono-font);
            font-size: 0.68rem;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }}
        .rs-compare-value {{
            font-family: var(--rs-heading-font);
            font-size: 2.1rem;
            font-weight: 600;
            line-height: 1.1;
        }}
        .rs-compare-note {{
            font-size: 0.83rem;
            line-height: 1.5;
            color: var(--rs-muted);
            margin-top: 0.45rem;
        }}
        .rs-compare-cell.is-proxy .rs-compare-eyebrow {{ color: var(--rs-steel); }}
        .rs-compare-cell.is-proxy .rs-compare-value {{ color: var(--rs-ink); }}
        .rs-compare-cell.is-degenerate {{
            background: var(--rs-surface);
        }}
        .rs-compare-cell.is-degenerate .rs-compare-eyebrow {{ color: var(--rs-caveat); }}
        .rs-compare-cell.is-degenerate .rs-compare-value {{
            color: var(--rs-muted);
            text-decoration: line-through;
            text-decoration-color: var(--rs-caveat);
            text-decoration-thickness: 2px;
        }}
        @media (max-width: 900px) {{
            .rs-compare-grid {{ grid-template-columns: 1fr; }}
            .rs-compare-cell + .rs-compare-cell {{ border-left: none; border-top: 1px solid var(--rs-border); }}
        }}

        /* Route-in buttons on Overview's "Continue the investigation"
           section: plain, bordered, left-aligned -- a list of next steps
           rather than a row of call-to-action buttons. st.container(key=...)
           (Streamlit >= 1.32) adds the .st-key-route_nav class used to
           scope this without touching any other button in the app. */
        .st-key-route_nav button {{
            width: 100%;
            white-space: normal;
            text-align: left !important;
            justify-content: flex-start !important;
            background: transparent;
            border: 1px solid var(--rs-border);
            border-radius: 4px;
            color: var(--rs-ink);
            font-family: var(--rs-body-font);
            font-size: 0.85rem;
            font-weight: 500;
            line-height: 1.4;
            padding: 0.65rem 0.85rem;
            height: auto;
            box-shadow: none !important;
        }}
        .st-key-route_nav button:hover {{
            border-color: var(--rs-slate);
            color: var(--rs-slate);
            background: var(--rs-surface);
        }}
        .st-key-route_nav button code {{
            font-family: var(--rs-mono-font);
            font-size: 0.72rem;
        }}

        /* Caveat callouts: reserved for the amber accent, used sparingly,
           for "read this before you trust the number above it." */
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

        /* Definition callouts: the green accent, reserved for "here is what
           this term means" -- distinct from a warning and from a neutral
           note, so a reader can tell at a glance which kind of aside it is. */
        .rs-define {{
            border-left: 3px solid var(--rs-define);
            background-color: var(--rs-define-bg);
            padding: 0.8rem 1.05rem;
            margin: 0.9rem 0;
            font-size: 0.93rem;
            line-height: 1.55;
            color: var(--rs-ink);
        }}
        .rs-define-title {{
            font-weight: 600;
            font-size: 0.79rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--rs-define);
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

        /* Inline glossary terms: a dotted underline that reveals a short
           definition on hover, so jargon is explained where it appears
           instead of only in a footnote the reader might skip. Every term
           also appears in full on the Glossary page for anyone on touch. */
        .rs-term {{
            border-bottom: 1.5px dotted var(--rs-define);
            color: var(--rs-ink);
            font-weight: 600;
            cursor: help;
            position: relative;
            white-space: nowrap;
        }}
        .rs-term:hover, .rs-term:focus {{
            border-bottom-style: solid;
        }}
        .rs-term::after {{
            content: attr(data-tip);
            position: absolute;
            left: 0;
            bottom: 100%;
            margin-bottom: 0.4rem;
            width: max-content;
            max-width: 19rem;
            white-space: normal;
            background: var(--rs-ink);
            color: #F4F6F9;
            font-family: var(--rs-body-font);
            font-weight: 400;
            font-size: 0.78rem;
            line-height: 1.45;
            padding: 0.55rem 0.7rem;
            border-radius: 5px;
            box-shadow: 0 6px 18px rgba(20,26,34,0.22);
            opacity: 0;
            visibility: hidden;
            transform: translateY(3px);
            transition: opacity 0.12s ease, transform 0.12s ease;
            z-index: 50;
        }}
        .rs-term:hover::after, .rs-term:focus::after {{
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
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
# Glossary
# ---------------------------------------------------------------------------
# Short (tooltip-length) definitions, keyed by term. Each entry pairs the
# plain-language, textbook meaning with a clause on how RavenStack's own SQL
# actually measures it, since the two frequently diverge and that divergence
# is the point of this dashboard. The full-length version of each entry
# lives on the Glossary page (page_glossary); this dict is the compact
# version used for inline hover chips.

TERMS: dict[str, str] = {
    "mrr": (
        "Monthly Recurring Revenue: the revenue a subscription business expects to "
        "receive each month. RavenStack's version sums every open subscription "
        "record without removing duplicates per account, so see the Revenue page."
    ),
    "arr": (
        "Annual Recurring Revenue: MRR times twelve. Not computed anywhere in this "
        "project, because the underlying MRR figure isn't reliable enough to annualize."
    ),
    "cohort": (
        "A group of accounts bucketed by a shared starting point, usually signup "
        "month, so their behavior over time can be compared month-by-month."
    ),
    "churn": (
        "An account cancelling or leaving. RavenStack treats raw_churn_events as the "
        "sole source of truth for this, not the churn_flag column on accounts."
    ),
    "retention rate": (
        "The share of a cohort still active N months after their starting point. "
        "Sensitive to exactly how \"active\" is defined; see the Conversion & "
        "Retention page for RavenStack's definition."
    ),
    "trial conversion": (
        "The share of trial users who go on to become paying customers. "
        "RavenStack has no explicit conversion event, so this is built as a proxy."
    ),
    "plan tier": (
        "The pricing package a subscription belongs to: Basic, Pro, or Enterprise "
        "in this dataset. An account can hold subscription records on more than one "
        "tier at once."
    ),
    "escalation rate": (
        "The share of support tickets that get escalated past first-line handling, "
        "generally a signal of ticket severity or of first-contact resolution failing."
    ),
    "subscription record": (
        "One row in the subscriptions table: one plan tier, one price, a start date, "
        "and usually no end date. RavenStack accounts hold 5 to 14 of these open at "
        "once, so counting records is not the same as counting accounts."
    ),
    "referral channel": (
        "How an account says it found the product: organic search, paid ads, "
        "referral, content, or outbound, in this dataset's five categories."
    ),
    "net revenue retention": (
        "A measure of revenue kept and expanded within an existing customer base "
        "over time, commonly abbreviated NRR. Not computed anywhere in this project."
    ),
    "data quality check": (
        "One of 16 automated checks run against the raw CSVs before any metric is "
        "built on top of them, documented in full on the Data Quality page."
    ),
}


def term(key: str, display: str | None = None) -> str:
    """Return an inline glossary chip: a dotted-underline span that reveals
    a short definition on hover/focus. Must be placed inside HTML already
    rendered via st.markdown(..., unsafe_allow_html=True) -- it does not
    call st.markdown itself, so it can be composed into a larger string."""
    key_norm = key.lower()
    tip = TERMS.get(key_norm, "")
    label = display if display is not None else key
    tip_escaped = tip.replace('"', "&quot;")
    return f'<span class="rs-term" tabindex="0" data-tip="{tip_escaped}">{label}</span>'


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


def define(title: str, body: str) -> None:
    """A definition callout: the green accent, reserved for 'here is what
    this term means,' distinct from caveat() (amber, a warning) and note()
    (steel, neutral context)."""
    st.markdown(
        f'<div class="rs-define"><div class="rs-define-title">{title}</div>{body}</div>',
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


def pullquote(text: str) -> None:
    """The dashboard's central claim, set in the heading serif. Reserved
    for the one or two sentences per page that most need to be read."""
    st.markdown(f'<div class="rs-pullquote">{text}</div>', unsafe_allow_html=True)


def finding_grid(items: list[tuple[str, str, str]]) -> None:
    """items: list of (stat, title, body) tuples, rendered as a three-up
    grid. Used once, on Overview, as the visual explanation of the three
    most consequential data-quality issues in the dataset."""
    cells = "".join(
        f'<div class="rs-finding"><div class="rs-finding-stat">{stat}</div>'
        f'<div class="rs-finding-title">{title}</div>'
        f'<div class="rs-finding-body">{body}</div></div>'
        for stat, title, body in items
    )
    st.markdown(f'<div class="rs-finding-grid">{cells}</div>', unsafe_allow_html=True)


def headline_stat(value: str, qualifier: str) -> None:
    """A large serif number with its interpretive qualifier immediately
    beneath it -- used where a figure could otherwise read as an
    unqualified, triumphant KPI (observed retention, most notably)."""
    st.markdown(
        f'<div class="rs-headline"><div class="rs-headline-value">{value}</div>'
        f'<div class="rs-headline-qualifier">{qualifier}</div></div>',
        unsafe_allow_html=True,
    )


def compare_two(
    proxy_value: str, proxy_note: str, degenerate_value: str, degenerate_note: str
) -> None:
    """Side-by-side comparison used on Conversion & Retention to keep the
    subscription-level proxy and the account-level figure from ever being
    read as two versions of the same KPI."""
    st.markdown(
        f'''
        <div class="rs-compare-grid">
          <div class="rs-compare-cell is-proxy">
            <div class="rs-compare-eyebrow">Subscription-level proxy</div>
            <div class="rs-compare-value">{proxy_value}</div>
            <div class="rs-compare-note">{proxy_note}</div>
          </div>
          <div class="rs-compare-cell is-degenerate">
            <div class="rs-compare-eyebrow">Account-level result</div>
            <div class="rs-compare-value">{degenerate_value}</div>
            <div class="rs-compare-note">{degenerate_note}</div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


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

    pullquote(
        "These numbers are correct, but some do not mean what they would mean in a "
        "clean SaaS dataset."
    )

    st.write(
        "This dashboard exists to answer one question honestly: for each metric a SaaS "
        "business normally tracks, what does this specific, synthetic dataset actually "
        "support saying, and where does the usual definition break down? If a term below "
        "isn't familiar, most metric labels are underlined and explain themselves on "
        "hover; the Glossary page has the full version of every one of them."
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
        (f"{total_churn_events:,} events", f"{term('churn', 'Churn')} events, from {unique_churned:,} unique accounts"),
        (f"{conv_rate:.1f}%", f"{term('trial conversion', 'Trial to paid conversion')}, subscription-level proxy"),
    ]
    if latest_mrr_row is not None:
        row1.append((
            f"${latest_mrr_row['aggregate_subscription_mrr']:,.0f}",
            f"Aggregate subscription-record {term('mrr', 'MRR')}, December 2024",
        ))
    metric_row(row1)
    caption(
        "Every figure above is defined precisely on its own page, together with the caveat "
        "that applies to it. None of these numbers are meant to be quoted on their own. "
        "Hover an underlined term for a quick definition, or see the Glossary page for the "
        "full version."
    )

    define(
        "New to SaaS metrics? Start here",
        "<strong>MRR</strong> is monthly recurring revenue, <strong>churn</strong> is a customer "
        "leaving, and <strong>retention</strong> is the share of customers still active after some "
        "time. Those textbook definitions are the ones most business dashboards use. This dashboard "
        "computes the same-named metrics against RavenStack's data, but several of them turn out to "
        "measure something subtly different once you look at how the underlying tables are actually "
        "shaped. See the section below, and the full <strong>Glossary</strong> page, for specifics.",
    )

    divider()
    st.markdown("### The dataset is unusual")
    st.write(
        "RavenStack was built with structural properties that a production analytics stack "
        "would normally flag before anyone built a dashboard on top of it. They were kept "
        "deliberately, because working around imperfect data honestly is the point of this "
        "project. Three of them matter more than the rest:"
    )

    finding_grid(
        [
            (
                "5–14 per account",
                "Subscriptions overlap",
                "Accounts routinely hold multiple simultaneously open subscription records. "
                "There is no single \u201ccurrent plan\u201d to point to, which is why revenue is "
                "reported at the subscription-record level rather than per customer.",
            ),
            (
                "~90% no end date",
                "Subscriptions rarely close",
                "Most subscription records never receive an end date. An account with any open "
                "record keeps counting as \u201cactive\u201d indefinitely, which is most of the "
                "reason the retention curve rises instead of decaying.",
            ),
            (
                "600 events, 352 accounts",
                "Churn is an event log, not a flag",
                "The accounts table's own churn_flag disagrees with the churn events log, so "
                "this project treats raw_churn_events as the only source of truth, and reports "
                "events and unique accounts as two separate numbers, never one.",
            ),
        ]
    )

    caveat(
        "Interpretation notes: please read before the rest of this dashboard",
        "RavenStack is a <strong>synthetic</strong> dataset built for portfolio purposes, not a real "
        "company's data. The three properties above, and others documented in full on the "
        "<strong>Data Quality</strong> page, change how the headline metrics on this dashboard should "
        "be read. None of the figures shown here have been adjusted to compensate for them. They are "
        "shown exactly as computed, with the caveat that explains them placed right next to the "
        "number.",
    )

    divider()
    st.markdown("### What the data suggests")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Acquisition and revenue**")
        st.markdown(
            f"Account acquisition is spread across five {term('referral channel', 'referral channels')} "
            f"with no single channel dominating volume. Aggregate subscription-record "
            f"{term('mrr', 'MRR')} grows steadily across the observation window. That growth is driven "
            "by the accumulation of open subscription records over time, not by a conventional "
            "net-new-revenue signal. The Revenue page explains why.",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown("**Retention, churn, and support**")
        ret_text = f"{ret_month6:.1f}%" if ret_month6 is not None else "n/a"
        st.markdown(
            f"The observed six-month account subscription {term('retention rate', 'retention rate')} "
            f"is high, at {ret_text}, but this reflects a structural ceiling effect rather than "
            "genuinely low attrition. The Conversion & Retention page walks through why. Support "
            f"activity, meanwhile, shows no meaningful difference between {term('churn', 'churned')} "
            "and non-churned accounts when compared across each account's whole history.",
            unsafe_allow_html=True,
        )

    divider()
    st.markdown("### How to read this dashboard")
    st.write(
        "Each page below states the precise metric definition next to the number, not just the "
        "number by itself. Where a figure could be mistaken for a standard business KPI, such as "
        "\"MRR\" or \"retention,\" this dashboard uses the project's exact terminology, for example "
        "\"Aggregate Subscription-Record MRR,\" and puts the relevant caveat directly beside the "
        "chart rather than in a footnote you might skip."
    )

    divider()
    st.markdown("### Continue the investigation")
    mrr_millions = (
        f"${latest_mrr_row['aggregate_subscription_mrr'] / 1_000_000:.1f}M"
        if latest_mrr_row is not None
        else "the MRR figure"
    )
    st.write(
        "If you only have time for one other page, make it Data Quality: it explains the "
        "structural quirks that shape almost everything else here. The two pages below are "
        "where those quirks matter most."
    )
    with st.container(key="route_nav"):
        route_cols = st.columns(3)
        routes = [
            ("03", "Revenue", f"Why {mrr_millions} is not company MRR."),
            ("04", "Conversion & Retention", "Why 98.9% retention isn't what it looks like."),
            ("07", "Data Quality", "The 16 checks behind almost every number here."),
        ]
        for col, (num, label, desc) in zip(route_cols, routes):
            with col:
                if st.button(f"`{num}`  {label} — {desc}", key=f"route_{label}", width="stretch"):
                    st.session_state.rs_page = label
                    st.rerun()


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
    st.markdown(
        "The next four charts break the same 500 accounts down by "
        f"{term('referral channel', 'referral source')}, {term('plan tier', 'plan tier')}, industry, "
        "and country, so you can see how acquisition is distributed along each dimension separately.",
        unsafe_allow_html=True,
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
        f"Throughout this project it is called <strong>Aggregate Subscription-Record MRR</strong> and "
        f"is never referred to as \"Company MRR,\" \"Account MRR,\" or {term('arr', 'ARR')}. No ARR, no "
        f"{term('net revenue retention', 'net revenue retention')}, no expansion revenue, and no "
        "customer lifetime value figures are computed anywhere in this project.",
    )

    mrr = data["monthly_mrr"]
    if mrr is not None:
        latest = mrr.sort_values("month_start").iloc[-1]
        metric_row(
            [
                (f"${latest['aggregate_subscription_mrr']:,.0f}", f"Aggregate {term('subscription record', 'Subscription-Record')} {term('mrr', 'MRR')}, {latest['month_label']}"),
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
        acct_row = conv_acct.iloc[0] if conv_acct is not None else None

        metric_row(
            [
                (f"{row['subscription_level_conversion_rate_pct']:.1f}%", f"Subscription-level proxy {term('trial conversion', 'conversion rate')}"),
                (f"{int(row['total_trial_subscription_records']):,}", "Total trial subscription records"),
                (f"{int(row['trial_records_with_later_paid_record']):,}", "Records with a later paid record on the same account"),
            ]
        )

        if acct_row is not None:
            compare_two(
                proxy_value=f"{row['subscription_level_conversion_rate_pct']:.1f}%",
                proxy_note=(
                    "Trial subscription records followed by a paid record on the same account. "
                    "Still just a proxy, but it is the number reported as this project's "
                    "conversion metric."
                ),
                degenerate_value=f"{acct_row['account_level_conversion_rate_pct']:.1f}%",
                degenerate_note=(
                    "Almost any account that ever held a trial also shows a paid record "
                    "somewhere in its history, regardless of order or causation. Not usable "
                    "as a KPI \u2014 shown here so the degeneracy is visible, not hidden."
                ),
            )

        caveat(
            "This is a proxy, not a certified causal funnel",
            "A trial subscription record counts as \"converted\" if the same account holds at least "
            "one paid subscription record with a start date on or after the trial's start date. "
            "Because accounts hold many concurrently open subscriptions, a trial record and a paid "
            "record can coexist without one having actually caused the other. For example, a trial "
            "for a new seat might open while an existing paid plan is already active on the same "
            "account. That is why this is reported as a <strong>subscription-level proxy</strong>, "
            "and why the account-level figure above is shown only as a contrast, never as the "
            "headline conversion metric.",
        )

        if acct_row is not None:
            st.write(
                f"Of {int(acct_row['accounts_with_any_trial'])} accounts that ever held a trial "
                f"subscription record, {int(acct_row['accounts_with_trial_and_paid'])} also held a "
                "paid record at some point. With enough subscription history accumulated per "
                "account, nearly every account clears this bar \u2014 which is exactly why it isn't "
                "reported as a real business conversion rate."
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
        "looks impressive on its own, and that is exactly why the explanation directly beneath it "
        "matters."
    )
    retention = data["retention_curve"]
    if retention is not None:
        m0 = retention.loc[retention["months_since_signup"] == 0, "retention_rate_pct_eligible_cohorts_only"].iloc[0]
        m6 = retention.loc[retention["months_since_signup"] == 6, "retention_rate_pct_eligible_cohorts_only"].iloc[0]

        headline_stat(
            f"{m6:.1f}%",
            "Observed account-subscription retention at month 6 \u2014 under this project's "
            "open-subscription definition. Not a claim about customer loyalty; see the caveat below.",
        )
        caption(f"For reference, the same measure reads {m0:.1f}% at month 0, immediately after signup.")

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
        f"{term('subscription record', 'subscription')} foreign key purely as a technical bridge to "
        "reach <code>account_id</code>, rather than to scope usage to a specific subscription period. "
        f"\"{term('churn', 'Churned')}\" below follows the same account-level definition used "
        "throughout this dashboard.",
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
                (f"{int(r['total_churn_events']):,}", f"Total {term('churn', 'churn')} events"),
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
# PAGE 08. GLOSSARY
# ===========================================================================


def page_glossary(data: dict) -> None:
    kicker("08", "Glossary")
    st.title("Glossary")
    lede(
        "The pages before this one define each metric inline, right next to the number, "
        "because that is where a caveat is most likely to actually get read. This page "
        "collects those definitions in one place instead, for anyone who wants the "
        "vocabulary up front, or who is new to SaaS metrics generally. Every entry has two "
        "parts: what the term ordinarily means, and how RavenStack's own SQL measures it, "
        "which is not always the same thing."
    )

    note(
        "Why this project keeps saying \"that's not quite what it sounds like\"",
        "RavenStack is a synthetic dataset with some unusual structural properties, "
        "documented in full on the Data Quality page: accounts hold many overlapping "
        "subscription records, most records never close, and the churn flag on the "
        "accounts table disagrees with the churn events log. A metric computed correctly "
        "against this data can still look strange next to the textbook definition of that "
        "metric, simply because the textbook definition assumes a data shape this dataset "
        "doesn't quite have. Naming that gap, rather than quietly smoothing it over, is the "
        "whole premise of this dashboard.",
    )

    divider()
    st.markdown("### Revenue and plans")
    with st.expander("MRR — Monthly Recurring Revenue", expanded=True):
        st.markdown(
            "**Ordinarily:** the revenue a subscription business expects to collect in a "
            "typical month, usually counted once per paying customer.\n\n"
            "**In RavenStack:** summed across every subscription record open in a given "
            "month, with no deduplication by account. Because accounts here routinely hold "
            "5 to 14 concurrently open records, the same account's revenue can be counted "
            "several times over in the same month. This project calls the result "
            "**Aggregate Subscription-Record MRR** specifically so it is never mistaken for "
            "the standard, one-per-customer figure. See the Revenue page."
        )
    with st.expander("ARR — Annual Recurring Revenue"):
        st.markdown(
            "**Ordinarily:** MRR multiplied by twelve, used as a longer-horizon revenue "
            "benchmark.\n\n"
            "**In RavenStack:** not computed anywhere in this project. Annualizing a figure "
            "that already double-counts revenue within a single month would only compound "
            "the distortion, so this project stops at the monthly figure and explains its "
            "limits instead."
        )
    with st.expander("Plan tier"):
        st.markdown(
            "**Ordinarily:** the pricing package a customer is subscribed to.\n\n"
            "**In RavenStack:** Basic, Pro, or Enterprise, tracked at the subscription-record "
            "level rather than the account level. One account can hold open records on more "
            "than one tier at the same time, which is part of why per-account revenue "
            "figures aren't reported here."
        )
    with st.expander("Net revenue retention (NRR)"):
        st.markdown(
            "**Ordinarily:** the share of revenue kept and expanded within an existing "
            "customer base over a period, accounting for upgrades, downgrades, and churn.\n\n"
            "**In RavenStack:** not computed. It depends on a reliable per-account revenue "
            "figure over time, which the double-counted MRR metric above cannot supply."
        )

    st.markdown("### Conversion and retention")
    with st.expander("Trial conversion", expanded=True):
        st.markdown(
            "**Ordinarily:** the share of trial signups who become paying customers, "
            "usually tracked as an explicit event in the product.\n\n"
            "**In RavenStack:** there is no explicit conversion event in the data, so this "
            "is built as a proxy: an account's trial subscription record counts as "
            "\"converted\" if that same account also holds a paid record starting on or "
            "after the trial's start date. Because accounts can hold many unrelated "
            "subscription records over time, this proxy can register a conversion even when "
            "the trial didn't actually cause the paid subscription. See Conversion & "
            "Retention."
        )
    with st.expander("Cohort"):
        st.markdown(
            "**Ordinarily and in RavenStack, the same:** a group of accounts bucketed by a "
            "shared starting point, here the signup month, so their behavior can be lined up "
            "and compared month-by-month regardless of when each account actually signed up."
        )
    with st.expander("Retention rate"):
        st.markdown(
            "**Ordinarily:** the share of a cohort still active N months after joining, "
            "typically declining over time as customers leave.\n\n"
            "**In RavenStack:** an account counts as \"active\" in a given month if it holds "
            "at least one open subscription record then. Since about 90% of records never "
            "receive an end date, this curve rises toward ~99% rather than declining, "
            "which reflects the definition of \"active\" more than it reflects genuine "
            "customer loyalty. Read the full explanation on the Conversion & Retention page "
            "before quoting this figure."
        )

    st.markdown("### Churn and support")
    with st.expander("Churn", expanded=True):
        st.markdown(
            "**Ordinarily:** a customer cancelling or leaving a subscription business.\n\n"
            "**In RavenStack:** measured exclusively from the `raw_churn_events` table, "
            "which logs 600 discrete churn events across 352 unique accounts, some of them "
            "more than once. The `churn_flag` column on the accounts table exists but "
            "disagrees with the events log substantially, so it is not used anywhere in this "
            "project's downstream metrics."
        )
    with st.expander("Escalation rate"):
        st.markdown(
            "**Ordinarily and in RavenStack, the same:** the share of support tickets that "
            "get escalated past first-line handling. Generally read as a signal of ticket "
            "severity, or of first-contact resolution failing to hold. This project compares "
            "it between churned and non-churned accounts on the Churn & Support page and "
            "finds no material difference between the two groups."
        )

    st.markdown("### Acquisition, engagement, and data")
    with st.expander("Referral channel"):
        st.markdown(
            "**Ordinarily and in RavenStack, the same:** how an account reports finding the "
            "product. Five categories appear in this dataset: organic search, paid "
            "advertising, referral, content marketing, and outbound sales."
        )
    with st.expander("Subscription record"):
        st.markdown(
            "**Specific to this project's data model:** one row in the subscriptions table, "
            "with one plan tier, one price, a start date, and usually no end date. This is "
            "the unit almost every metric on this dashboard is actually computed against, "
            "which is why the distinction between \"a record\" and \"an account\" matters so "
            "much throughout the project."
        )
    with st.expander("Data quality check"):
        st.markdown(
            "**Specific to this project:** one of 16 automated checks run against the raw "
            "CSVs before any downstream metric is built, covering things like NULL rates, "
            "duplicate keys, and the churn-flag disagreement mentioned above. Full results "
            "are on the Data Quality page."
        )

    divider()
    caption(
        "Missing a term? Every metric on this dashboard is also defined, with full SQL, in "
        "the corresponding file under <code>sql/</code>, and documented further in "
        "<code>docs/</code>."
    )


# ===========================================================================
# Navigation
# ===========================================================================

# Each entry: (section number, label, one-line description of what the page
# actually answers). The description renders under the nav button so the
# sidebar functions as a real table of contents, not just a list of labels.
NAV_ITEMS: list[tuple[str, str, str]] = [
    ("01", "Overview", "What's in the dataset, and what to read first."),
    ("02", "Acquisition", "Where the 500 accounts came from, by channel and tier."),
    ("03", "Revenue", "Aggregate Subscription-Record MRR, and why that name."),
    ("04", "Conversion & Retention", "Trial-to-paid proxy and the retention curve."),
    ("05", "Engagement", "Feature usage volume, churned vs. non-churned."),
    ("06", "Churn & Support", "Events vs. accounts, reasons, and support activity."),
    ("07", "Data Quality", "16 checks behind almost every number here."),
    ("08", "Glossary", "Plain-language definitions for every metric used."),
]

PAGE_FUNCTIONS = {
    "Overview": page_overview,
    "Acquisition": page_acquisition,
    "Revenue": page_revenue,
    "Conversion & Retention": page_conversion_retention,
    "Engagement": page_engagement,
    "Churn & Support": page_churn_support,
    "Data Quality": page_data_quality,
    "Glossary": page_glossary,
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
        st.markdown(
            '<div class="rs-wordmark-sub">A SQL-first audit of a synthetic SaaS dataset. '
            "Every figure below is sourced to the query that produced it.</div>",
            unsafe_allow_html=True,
        )

        for num, label, desc in NAV_ITEMS:
            is_active = st.session_state.rs_page == label
            if st.button(
                f"`{num}`  {label}",
                key=f"nav_{label}",
                type="primary" if is_active else "secondary",
                width="stretch",
            ):
                st.session_state.rs_page = label

        active_desc = next(desc for _, label, desc in NAV_ITEMS if label == st.session_state.rs_page)
        st.markdown(f'<div class="rs-nav-active-desc">{active_desc}</div>', unsafe_allow_html=True)

        st.markdown('<hr class="rs-sidebar-rule" />', unsafe_allow_html=True)

        st.markdown('<div class="rs-legend-title">Reading key</div>', unsafe_allow_html=True)
        legend_items = [
            (DEFINE, "Definition", "what a term means, textbook vs. how RavenStack measures it."),
            (STEEL_PALE, "Note", "context worth knowing that isn't a warning."),
            (CAVEAT, "Caveat", "read this before you trust the number beside it."),
        ]
        legend_html = "".join(
            f'<div class="rs-legend-row"><span class="rs-legend-swatch" '
            f'style="background:{color}"></span><span class="rs-legend-text">'
            f"<strong>{name}.</strong> {desc}</span></div>"
            for color, name, desc in legend_items
        )
        st.markdown(legend_html, unsafe_allow_html=True)

        st.markdown('<hr class="rs-sidebar-rule" />', unsafe_allow_html=True)
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