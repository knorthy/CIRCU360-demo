"""CIRCU360 - monitoring dashboard (Streamlit + Plotly).

Run:   streamlit run dashboard.py
Then start belt_sim.py in a second terminal: the live section refreshes every 2 s from events.csv.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from decision import decide, CONTAMINANTS, POLYOLEFINS

ROOT = Path(__file__).resolve().parent
EVENTS_CSV = ROOT / "events.csv"
RUN_DIR = ROOT / "runs" / "circu360"

# Fixed colours: classes keep the same colour everywhere; decisions use status colours + text labels
CLASS_COLORS = {"HDPE": "#2a78d6", "PET": "#eb6834", "OTHER": "#1baf7a",
                "LDPE": "#eda100", "PP": "#e87ba4", "PVC": "#008300"}
DECISION_COLORS = {"ACCEPT": "#0ca30c", "REJECT": "#d03b3b", "REMOVE": "#8a8984", "UNCERTAIN": "#fab219"}
DECISIONS = list(DECISION_COLORS)
PROB_COLS = ["P_HDPE", "P_LDPE", "P_PP", "P_PET", "P_PVC", "P_OTHER"]

# Case numbers from the essay brief (kg/day)
FEED = {"HDPE": 700, "LDPE": 600, "PP": 400, "PET": 200, "Dirt / non-plastic": 100}
REACTOR_FEED = 1700
YIELDS = {"Liquid oil": 0.778, "Gas": 0.168, "Char (incl. wax, additives, dirt)": 0.054}
OIL_BAND = 0.09     # Belden et al. 2023 model error, read here as +/- 9 percentage points of yield

st.set_page_config(page_title="CIRCU360 dashboard", page_icon="♻️", layout="wide")
st.title("CIRCU360 micro-plant monitor")
st.caption("Prototype for the essay \"CIRCU360: A Smart, Safety-First Circular Plastic Recovery Micro-Plant\". "
           "Live data comes from the belt simulation, not a real plant.")


def small_layout(fig, title, height=320):
    fig.update_layout(title=title, height=height, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.15))
    return fig


# ---------- 1. Live sorting ----------
@st.fragment(run_every="2s")
def live_section():
    st.header("Live sorting (belt simulation)")
    if not EVENTS_CSV.exists():
        st.info("No events.csv yet. Start the belt: `python belt_sim.py`")
        return
    try:
        ev = pd.read_csv(EVENTS_CSV)
    except pd.errors.EmptyDataError:
        ev = pd.DataFrame()
    if ev.empty:
        st.info("Waiting for the first item to reach the camera...")
        return

    counts = ev["decision"].value_counts()
    leaked = ev[ev["true_class"].isin(CONTAMINANTS) & (ev["decision"] == "ACCEPT")]
    cols = st.columns(6)
    cols[0].metric("Items seen", len(ev))
    for col, d in zip(cols[1:5], DECISIONS):
        col.metric(d, int(counts.get(d, 0)))
    cols[5].metric("⚠ PET/PVC leaked to reactor", len(leaked),
                   help="Contaminant items that were ACCEPTed. This is the safety metric and should stay 0.")

    c1, c2, c3 = st.columns(3)
    true_counts = ev["true_class"].value_counts()
    pie = go.Figure(go.Pie(labels=true_counts.index, values=true_counts.values, hole=0.55, sort=False,
                           marker=dict(colors=[CLASS_COLORS.get(c, "#888") for c in true_counts.index],
                                       line=dict(color="white", width=2)),
                           textinfo="label+percent"))
    c1.plotly_chart(small_layout(pie, "Items by true class"), width="stretch")

    # decisions per true class, stacked
    tab = pd.crosstab(ev["true_class"], ev["decision"]).reindex(columns=DECISIONS, fill_value=0)
    bars = go.Figure()
    for d in DECISIONS:
        bars.add_bar(name=d, x=tab.index, y=tab[d], marker_color=DECISION_COLORS[d],
                     marker_line=dict(color="white", width=2),
                     hovertemplate="%{x}: %{y} " + d + "<extra></extra>")
    bars.update_layout(barmode="stack", yaxis_title="items")
    c2.plotly_chart(small_layout(bars, "Decision by true class"), width="stretch")

    hist = go.Figure(go.Histogram(x=ev["latency_ms"], nbinsx=30, marker_color=CLASS_COLORS["HDPE"],
                                  marker_line=dict(color="white", width=1), name="latency"))
    hist.add_vline(x=35, line_dash="dash", line_color="#52514e",
                   annotation_text="35 ms spec", annotation_position="top")
    hist.update_layout(xaxis_title="inference latency (ms, this laptop)", yaxis_title="items", showlegend=False)
    c3.plotly_chart(small_layout(hist, f"Latency: mean {ev['latency_ms'].mean():.1f} ms, "
                                       f"p95 {ev['latency_ms'].quantile(0.95):.1f} ms"), width="stretch")

    with st.expander("Last 20 events (table view)"):
        st.dataframe(ev.tail(20).iloc[::-1], width="stretch", hide_index=True)


live_section()


# ---------- 2. Model test results and reject threshold ----------
st.header("Model test results and reject threshold")
pred_csv, sweep_csv = RUN_DIR / "test_predictions.csv", RUN_DIR / "threshold_sweep.csv"
if pred_csv.exists() and sweep_csv.exists():
    pred = pd.read_csv(pred_csv)
    sweep = pd.read_csv(sweep_csv)
    reject_t = st.slider("Reject threshold: REJECT if P(PET) + P(PVC) > reject_t", 0.05, 0.95, 0.30, 0.05,
                         help="A process-safety parameter: lower means more cautious.")

    # re-run the shared decision rule on the saved test-set probabilities
    P = pred[[c for c in pred.columns if c.startswith("P_")]].rename(columns=lambda c: c[2:])
    dec = pd.Series([decide(row, reject_t=reject_t) for row in P.to_dict("records")])
    contam, poly = pred["true"].isin(CONTAMINANTS), pred["true"].isin(POLYOLEFINS)
    m = st.columns(4)
    m[0].metric("PET/PVC leaked", f"{(dec[contam] == 'ACCEPT').sum()} of {contam.sum()}")
    m[1].metric("PET/PVC recall (rejected)", f"{(dec[contam] == 'REJECT').mean():.1%}")
    m[2].metric("Polyolefin false-reject", f"{(dec[poly] == 'REJECT').mean():.1%}")
    m[3].metric("Sent to manual check", f"{(dec == 'UNCERTAIN').mean():.1%}")
    if (dec[contam] == "ACCEPT").sum() == 0 and contam.sum():
        st.caption(f"0 leaks in {contam.sum()} test items: the true leak rate is below "
                   f"~{3 / contam.sum():.1%} with 95% confidence (rule of three).")

    c1, c2 = st.columns([3, 2])
    line = go.Figure()
    for col, name, color in [("polyolefin_false_reject", "Polyolefin false-reject", CLASS_COLORS["HDPE"]),
                             ("uncertain_frac", "Sent to manual check", CLASS_COLORS["PET"]),
                             ("pet_leak_rate", "PET/PVC leak rate", CLASS_COLORS["OTHER"])]:
        line.add_scatter(x=sweep["reject_t"], y=sweep[col] * 100, name=name, mode="lines+markers",
                         line=dict(color=color, width=2), marker=dict(size=8),
                         hovertemplate="reject_t %{x:.2f}: %{y:.1f}%<extra>" + name + "</extra>")
    line.add_vline(x=reject_t, line_dash="dash", line_color="#52514e")
    line.update_layout(xaxis_title="reject_t", yaxis_title="% of test items", hovermode="x unified")
    c1.plotly_chart(small_layout(line, "Threshold sweep on the test set", 380), width="stretch")
    if (RUN_DIR / "confusion_matrix_test.png").exists():
        c2.image(str(RUN_DIR / "confusion_matrix_test.png"), caption="Confusion matrix (argmax, test set)")
    st.caption("Limitation: the test images come from the same photo set as the training images, and the "
               "dataset has no LDPE, PP or PVC yet. RGB cannot reliably separate clear PET from clear PVC; "
               "NIR is the proposed upgrade.")
else:
    st.info("No training results yet. Run `python circu360_train_local.py`.")


# ---------- 3. Mass flow ----------
st.header("Daily mass flow (case numbers)")
nodes = ["Mixed coastal plastic"] + list(FEED) + ["Pyrolysis reactor", "Mechanical recyclers", "Residue"] + list(YIELDS)
idx = {n: i for i, n in enumerate(nodes)}
src, dst, val = [], [], []
for name, kg in FEED.items():
    src.append(idx["Mixed coastal plastic"]); dst.append(idx[name]); val.append(kg)
for name in ["HDPE", "LDPE", "PP"]:
    src.append(idx[name]); dst.append(idx["Pyrolysis reactor"]); val.append(FEED[name])
src += [idx["PET"], idx["Dirt / non-plastic"]]; dst += [idx["Mechanical recyclers"], idx["Residue"]]
val += [FEED["PET"], FEED["Dirt / non-plastic"]]
for name, y in YIELDS.items():
    src.append(idx["Pyrolysis reactor"]); dst.append(idx[name]); val.append(round(REACTOR_FEED * y, 1))

node_colors = ["#8a8984"] + [CLASS_COLORS.get(n, "#8a8984") for n in FEED] + ["#52514e"] * (len(nodes) - 1 - len(FEED))
sankey = go.Figure(go.Sankey(
    node=dict(label=[f"{n}" for n in nodes], color=node_colors, pad=18, thickness=16),
    link=dict(source=src, target=dst, value=val, color="rgba(138,137,132,0.35)",
              hovertemplate="%{source.label} → %{target.label}: %{value:,.1f} kg/day<extra></extra>"),
    valueformat=",.1f", valuesuffix=" kg/day"))
st.plotly_chart(small_layout(sankey, "2,000 kg/day feed → 1,700 kg/day reactor feed → products", 460),
                width="stretch")

oil = REACTOR_FEED * YIELDS["Liquid oil"]
lo, hi = REACTOR_FEED * (YIELDS["Liquid oil"] - OIL_BAND), REACTOR_FEED * (YIELDS["Liquid oil"] + OIL_BAND)
c = st.columns(3)
c[0].metric("Liquid oil", f"{oil:,.1f} kg/day", help=f"Model uncertainty band: {lo:,.0f}–{hi:,.0f} kg/day")
c[1].metric("Gas", f"{REACTOR_FEED * YIELDS['Gas']:,.1f} kg/day")
c[2].metric("Char", f"{REACTOR_FEED * YIELDS['Char (incl. wax, additives, dirt)']:,.1f} kg/day")
st.caption(f"Oil band {lo:,.0f}–{hi:,.0f} kg/day: ±9 wt% model error (Belden et al. 2023), applied as ±9 "
           "percentage points of the 77.8% yield. The 5.4% char is high for clean polyolefins (literature "
           "0.4–2%), so it is read as including wax, additives and dirt.")


# ---------- 4. Energy balance ----------
st.header("Energy balance (editable inputs)")
st.caption("The gas heating value and the reactor heat demand are **not verified**. Enter values with a "
           "source; nothing is computed from them until you do.")
e = st.columns(3)
oil_hv = e[0].number_input("Oil heating value (MJ/kg)", 30.0, 50.0, 43.4, 0.1,
                           help="HDPE oil 43.4–46.5 MJ/kg (Shah et al. 2023)")
gas_hv = e[1].number_input("Pyrolysis gas heating value (MJ/kg) — ASSUMPTION", 0.0, 100.0, value=None,
                           placeholder="enter a sourced value")
demand = e[2].number_input("Reactor heat demand (MJ per kg feed) — ASSUMPTION", 0.0, 20.0, value=None,
                           placeholder="enter a sourced value")

oil_mj = oil * oil_hv
r = st.columns(3)
r[0].metric("Energy in oil", f"{oil_mj:,.0f} MJ/day", f"{oil_mj / 3.6:,.0f} kWh/day", delta_color="off")
if gas_hv is not None and demand is not None:
    gas_mj = REACTOR_FEED * YIELDS["Gas"] * gas_hv
    need_mj = REACTOR_FEED * demand
    r[1].metric("Energy in gas", f"{gas_mj:,.0f} MJ/day", f"{gas_mj / 3.6:,.0f} kWh/day", delta_color="off")
    r[2].metric("Gas covers reactor demand", f"{gas_mj / need_mj:.0%}" if need_mj else "n/a",
                f"{gas_mj - need_mj:+,.0f} MJ/day surplus" if need_mj else None)
else:
    r[1].info("Enter both assumption values to compute the gas energy and the reactor balance.")
