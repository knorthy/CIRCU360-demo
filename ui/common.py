"""Shared constants, data loaders and small HTML pieces for every dashboard page."""
import base64
import inspect
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from decision import decide, CONTAMINANTS, POLYOLEFINS

ROOT = Path(__file__).resolve().parent.parent
EVENTS_CSV = ROOT / "events.csv"
RUN_DIR = ROOT / "runs" / "circu360"
TEST_DIR = ROOT / "data" / "split" / "test"

INK, RULE, PAPER = "#141414", "#d6d6d0", "#f1f1ee"

# Fixed colours: classes keep the same colour everywhere; decisions use status colours + text labels
CLASS_COLORS = {"HDPE": "#2a78d6", "PET": "#eb6834", "OTHER": "#1baf7a",
                "LDPE": "#eda100", "PP": "#e87ba4", "PVC": "#008300"}
DECISION_COLORS = {"ACCEPT": "#0ca30c", "REJECT": "#d03b3b", "REMOVE": "#8a8984", "UNCERTAIN": "#fab219"}
DECISION_INK = {"ACCEPT": "#0a7a0a", "REJECT": "#c0302f", "REMOVE": "#5c5b57", "UNCERTAIN": "#875c00"}  # darker, readable as text
DECISIONS = list(DECISION_COLORS)

# Resin identification codes (the numbers moulded on bottles); OTHER = cans and glass, no code
RESIN_CODE = {"PET": 1, "HDPE": 2, "PVC": 3, "LDPE": 4, "PP": 5, "OTHER": None}
CLASS_ORDER = ["PET", "HDPE", "PVC", "LDPE", "PP", "OTHER"]
IN_MODEL = ["HDPE", "PET", "OTHER"]                     # classes the current model was trained on
CLASS_ITEMS = {"PET": "drink bottles", "HDPE": "milk bottles", "PVC": "pipe offcuts, blister packs",
               "LDPE": "film, sachets", "PP": "team photos planned", "OTHER": "aluminium cans, glass"}
CLASS_ROUTE = {"PET": "Mechanical recyclers", "HDPE": "Pyrolysis reactor", "PVC": "Specialist disposal",
               "LDPE": "Pyrolysis reactor", "PP": "Pyrolysis reactor", "OTHER": "Non-plastic residue"}
DECISION_ROUTE = {"ACCEPT": "Pyrolysis reactor", "REJECT": "Ejected: recyclers / disposal",
                  "REMOVE": "Non-plastic residue", "UNCERTAIN": "Manual check"}
CLASS_DECISION = {"PET": "REJECT", "PVC": "REJECT", "HDPE": "ACCEPT", "LDPE": "ACCEPT", "PP": "ACCEPT",
                  "OTHER": "REMOVE"}   # the decision each class should get

# Thresholds come from decide()'s own defaults, so they are never copied here
DECIDE_DEFAULTS = {k: p.default for k, p in inspect.signature(decide).parameters.items() if k != "P"}

# Case numbers from the essay brief (kg/day)
FEED = {"HDPE": 700, "LDPE": 600, "PP": 400, "PET": 200, "Dirt / non-plastic": 100}
REACTOR_FEED = 1700
YIELDS = {"Liquid oil": 0.778, "Gas": 0.168, "Char": 0.054}
OIL_BAND = 0.09     # Belden et al. 2023 model error, read here as +/- 9 percentage points of yield
SORT_RATE_KG_H = 150

# Where a number comes from; shown as a tag beside it
BASIS = {"measured": ("MEASURED", "#0e5a8a"), "case": ("CASE BRIEF", "#5c5b57"),
         "sourced": ("SOURCED", "#5a3e9e"), "assumption": ("ASSUMPTION", "#875c00")}


# ---------- data ----------
def load_events():
    """Live belt events, or an empty frame while belt_sim.py has not written anything."""
    if not EVENTS_CSV.exists():
        return None
    try:
        return pd.read_csv(EVENTS_CSV)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


@st.cache_data
def load_predictions():
    path = RUN_DIR / "test_predictions.csv"
    return pd.read_csv(path) if path.exists() else None


@st.cache_data
def load_sweep():
    path = RUN_DIR / "threshold_sweep.csv"
    return pd.read_csv(path) if path.exists() else None


def probs(row):
    """Probability dict {class: p} from a row with P_<class> columns."""
    return {k[2:]: float(v) for k, v in row.items() if k.startswith("P_") and pd.notna(v)}


def decide_all(df, reject_t):
    P = df[[c for c in df.columns if c.startswith("P_")]].rename(columns=lambda c: c[2:]).fillna(0)
    return pd.Series([decide(p, reject_t=reject_t) for p in P.to_dict("records")], index=df.index)


def image_path(true_class, file):
    path = TEST_DIR / str(true_class) / str(file)
    return path if path.exists() else None


def reject_t():
    return st.session_state.get("reject_t", DECIDE_DEFAULTS["reject_t"])


# ---------- HTML pieces ----------
def resin_badge(cls, size=44):
    """Outlined resin-code triangle (or a dashed square for non-plastic) in the class colour."""
    color, code = CLASS_COLORS.get(cls, INK), RESIN_CODE.get(cls)
    if code is None:
        shape = f'<rect x="10" y="10" width="80" height="80" fill="none" stroke="{color}" stroke-width="7" stroke-dasharray="14 8"/>'
        label = ""
    else:
        shape = f'<path d="M50 8 L94 88 H6 Z" fill="none" stroke="{color}" stroke-width="8" stroke-linejoin="round"/>'
        label = (f'<text x="50" y="76" text-anchor="middle" font-family="Arial, sans-serif" font-size="40" '
                 f'font-weight="700" fill="{INK}">{code}</text>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{shape}{label}</svg>'
    # st.html strips inline <svg>, so the badge is passed as an image
    src = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return (f'<img class="c3-resin" src="{src}" width="{size}" height="{size}" '
            f'alt="{cls}, resin code {code or "none"}">')


def decision_tag(decision, route=True):
    ink = DECISION_INK.get(decision, INK)
    dest = f' <span class="c3-dest">→ {DECISION_ROUTE[decision]}</span>' if route else ""
    return f'<span class="c3-tag" style="color:{ink}">{decision}</span>{dest}'


def basis_tag(kind, text=None):
    label, color = BASIS[kind]
    return f'<span class="c3-basis" style="color:{color}">{text or label}</span>'


def stat(label, value, basis=None, note=""):
    tag = basis_tag(basis) if basis else ""
    note = f'<div class="c3-stat-note">{note}</div>' if note else ""
    return (f'<div class="c3-stat"><div class="c3-stat-label">{label} {tag}</div>'
            f'<div class="c3-stat-value">{value}</div>{note}</div>')


def stat_row(*stats):
    st.html(f'<div class="c3-stats">{"".join(stats)}</div>')


def page_title(title, lead):
    st.html(f'<div class="c3-title"><h1>{title}</h1><p>{lead}</p></div>')


def section(title, lead=""):
    lead = f"<p>{lead}</p>" if lead else ""
    st.html(f'<div class="c3-section"><h2>{title}</h2>{lead}</div>')


# ---------- charts ----------
pio.templates["circu360"] = go.layout.Template(layout=dict(
    font=dict(family="Archivo, sans-serif", color=INK, size=14),
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    xaxis=dict(gridcolor="#ececE8", linecolor=INK, zeroline=False, ticks="outside", tickcolor=INK),
    yaxis=dict(gridcolor="#ececE8", linecolor=INK, zeroline=False),
    hoverlabel=dict(font=dict(family="Archivo, sans-serif"), bgcolor="#ffffff", bordercolor=INK),
    legend=dict(orientation="h", y=-0.2, x=0),
    margin=dict(l=10, r=10, t=10, b=10)))


def chart(fig, height=320):
    fig.update_layout(template="circu360", height=height, plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    if fig.layout.margin.l is not None and fig.layout.margin.l < 60:
        fig.update_layout(margin_l=60)
    st.plotly_chart(fig, theme=None, width="stretch", config={"displayModeBar": False})


# ---------- global styles ----------
CSS = """
<style>
html, body, [class*="st-"] { font-variant-numeric: tabular-nums; }
::selection { background: #141414; color: #ffffff; }
:focus-visible { outline: 3px solid #2a78d6 !important; outline-offset: 2px; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #b9b9b2; }
::-webkit-scrollbar-track { background: #f1f1ee; }
.block-container { padding-top: 4.2rem; max-width: 1480px; }
[data-testid="stCaptionContainer"] { color: #4a4a46; }
section[data-testid="stSidebar"] { border-right: 1px solid #141414; }

.c3-title { border-bottom: 3px solid #141414; padding-bottom: .6rem; margin-bottom: .4rem; }
.c3-title h1 { font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em; margin: 0; padding: 0; line-height: 1.1; }
.c3-title p { margin: .35rem 0 0; font-size: 1.05rem; color: #3d3d3a; max-width: 72ch; }
.c3-section { margin-top: 1.6rem; border-top: 1px solid #141414; padding-top: .7rem; }
.c3-section h2 { font-size: 1.35rem; font-weight: 800; margin: 0; padding: 0; }
.c3-section p { margin: .25rem 0 0; color: #3d3d3a; max-width: 75ch; }

.c3-tag { display: inline-block; font-weight: 800; font-size: .8rem; letter-spacing: .06em;
          border: 2px solid currentColor; padding: .05rem .4rem; line-height: 1.3; }
.c3-dest { font-weight: 600; font-size: .85rem; color: #3d3d3a; }
.c3-basis { display: inline-block; font-weight: 700; font-size: .66rem; letter-spacing: .07em;
            border: 1px solid currentColor; padding: 0 .3rem; vertical-align: middle; line-height: 1.5; }
.c3-resin { display: block; }

.c3-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); border-top: 1px solid #141414; }
.c3-stat { padding: .7rem 1rem .8rem 0; border-bottom: 1px solid #d6d6d0; }
.c3-stat-label { font-size: .85rem; font-weight: 600; color: #3d3d3a; }
.c3-stat-value { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.01em; line-height: 1.15; margin-top: .15rem; }
.c3-stat-note { font-size: .82rem; color: #4a4a46; margin-top: .1rem; }

.c3-table { width: 100%; border-collapse: collapse; font-size: .95rem; }
.c3-table th { text-align: left; font-size: .75rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
               color: #3d3d3a; border-bottom: 2px solid #141414; padding: .4rem .6rem .4rem 0; }
.c3-table td { border-bottom: 1px solid #d6d6d0; padding: .45rem .6rem .45rem 0; vertical-align: middle; }
.c3-table td.n { text-align: right; font-weight: 600; }
.c3-table th.n { text-align: right; }
.c3-cls { display: flex; align-items: center; gap: .45rem; font-weight: 700; }

.c3-note { border: 1px solid #141414; padding: .7rem .9rem; font-size: .92rem; background: #f1f1ee; max-width: 80ch; }
.c3-note b { font-weight: 800; }
</style>
"""


def inject_css():
    st.html(CSS)
