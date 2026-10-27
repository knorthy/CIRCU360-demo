"""02 AI sorting: walk one item through decide(), then tune reject_t on the whole test set."""
import random

import plotly.graph_objects as go
import streamlit as st

from decision import decide, CLASSES, CONTAMINANTS, POLYOLEFINS
from ui.common import (CLASS_COLORS, DECIDE_DEFAULTS, DECISION_INK, DECISION_ROUTE, RUN_DIR, INK, load_predictions,
                       load_sweep, probs, decide_all, image_path, reject_t, page_title, section, stat, stat_row,
                       resin_badge, decision_tag, chart)

CSS = """
<style>
.c3-trace { border-top:3px solid #141414; }
.c3-rule { display:grid; grid-template-columns:2rem 1fr auto; gap:.8rem; align-items:center;
           padding:.65rem 0; border-bottom:1px solid #d6d6d0; }
.c3-rule .k { font-weight:800; font-size:1.1rem; }
.c3-rule .q { font-size:1rem; }
.c3-rule .q b { font-weight:800; }
.c3-rule .q small { display:block; color:#3d3d3a; font-size:.85rem; margin-top:.1rem; }
.c3-rule.skip { color:#8a8984; }
.c3-rule.skip .q small { color:#8a8984; }
.c3-rule.hit { background:#f1f1ee; box-shadow: inset 0 0 0 2px #141414; padding-left:.6rem; padding-right:.6rem; }
.c3-rule .res { font-weight:800; font-size:.85rem; letter-spacing:.05em; }
.c3-verdict { display:flex; align-items:center; gap:.8rem; margin:.9rem 0 .2rem; font-size:1.05rem; }
.c3-verdict .c3-tag { font-size:1.4rem; padding:.15rem .6rem; border-width:3px; }
.c3-itemhead { display:flex; align-items:center; gap:.6rem; font-size:1.1rem; font-weight:800; margin-bottom:.4rem; }
</style>
"""


def trace_html(P, decision, rt):
    """Show the four rules of decide() in order; the one that produced the decision is boxed."""
    a_t, o_t = DECIDE_DEFAULTS["accept_t"], DECIDE_DEFAULTS["other_t"]
    bad = sum(P.get(c, 0) for c in CONTAMINANTS)
    poly = sum(P.get(c, 0) for c in POLYOLEFINS)
    other = P.get("OTHER", 0)
    rules = [("REJECT", f"P(PET) + P(PVC) = <b>{bad:.3f}</b> &gt; {rt:.2f}?", "Checked first: PET/PVC can never be accepted"),
             ("ACCEPT", f"P(HDPE) + P(LDPE) + P(PP) = <b>{poly:.3f}</b> ≥ {a_t:.2f}?", "Polyolefins are the only reactor feed"),
             ("REMOVE", f"P(OTHER) = <b>{other:.3f}</b> ≥ {o_t:.2f}?", "Cans and glass go to the non-plastic stream"),
             ("UNCERTAIN", "Otherwise", "Manual inspection or float-sink test")]
    hit = [r[0] for r in rules].index(decision)
    rows = []
    for i, (outcome, q, why) in enumerate(rules):
        state = "hit" if i == hit else ("skip" if i > hit else "")
        res = (f'<span class="res" style="color:{DECISION_INK[outcome]}">YES → {outcome}</span>' if i == hit
               else "not reached" if i > hit else '<span class="res">NO</span>')
        rows.append(f'<div class="c3-rule {state}"><span class="k">{i + 1}</span>'
                    f'<span class="q">{q}<small>{why}</small></span>{res}</div>')
    return (f'<div class="c3-trace">{"".join(rows)}</div><div class="c3-verdict">{decision_tag(decision, route=False)}'
            f'<span>→ {DECISION_ROUTE[decision]}</span></div>')


def prob_chart(P, height=230):
    classes = [c for c in CLASSES if c in P]
    fig = go.Figure(go.Bar(x=[P[c] for c in classes], y=classes, orientation="h",
                           marker=dict(color=[CLASS_COLORS[c] for c in classes], line=dict(color=INK, width=1)),
                           text=[f"{P[c]:.3f}" for c in classes], textposition="outside",
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.update_layout(xaxis=dict(range=[0, 1.12], tickformat=".1f", title="probability"),
                      yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=40))
    chart(fig, height)


st.html(CSS)
page_title("AI sorting", "A YOLO11n-cls classifier looks at each item and gives a probability for every class. "
           "The shared decide() rule then turns those probabilities into one of four decisions.")
rt = reject_t()
pred = load_predictions()

# ---------- 1. one item ----------
section("Follow one item through decide()",
        "Pick a photo from the test set. These images were never used in training.")
if pred is None:
    st.info("No test predictions yet. Run `python circu360_train_local.py` first.")
else:
    c1, c2 = st.columns([1, 2])
    cls = c1.segmented_control("Class", ["Any", "HDPE", "PET", "OTHER"], default="Any", key="item_class")
    pool = pred if cls in (None, "Any") else pred[pred["true"] == cls]
    hard = c2.toggle("Only borderline items (not 99% sure)", key="item_hard",
                     help="Items whose top probability is below 0.99: the interesting cases for the thresholds.")
    if hard:
        pool = pool[pool[[c for c in pool.columns if c.startswith("P_")]].max(axis=1) < 0.99]
    if pool.empty:
        st.info("No items match these filters. Switch off 'Only borderline items' or pick another class.")
    else:
        if st.session_state.get("item_idx") not in pool.index:
            st.session_state.item_idx = pool.index[0]
        if st.button("Show another item", icon=":material/shuffle:", type="primary"):
            st.session_state.item_idx = random.choice(list(pool.index))
        row = pred.loc[st.session_state.item_idx]
        P = probs(row)
        decision = decide(P, reject_t=rt)
        left, right = st.columns([1, 1.6], gap="large")
        with left:
            st.html(f'<div class="c3-itemhead">{resin_badge(row["true"], 30)}True class: {row["true"]}</div>')
            img = image_path(row["true"], row["file"])
            if img:
                st.image(str(img), width="stretch")
            else:
                st.caption("Image not found in data/split/test (rebuild the split to see it).")
            st.caption(f'{row["file"]} · model latency {row["latency_ms"]:.1f} ms')
        with right:
            prob_chart(P)
            st.html(trace_html(P, decision, rt))

# ---------- 2. try your own ----------
section("Try your own probabilities",
        "Drag the sliders to see how decide() reacts near the thresholds. The values are rescaled to add up to 1.")
cols = st.columns(len(CLASSES))
raw = {c: col.slider(c, 0.0, 1.0, {"HDPE": 0.6, "PET": 0.25}.get(c, 0.05), 0.01, key=f"try_{c}")
       for col, c in zip(cols, CLASSES)}
total = sum(raw.values()) or 1
P_try = {c: v / total for c, v in raw.items()}
l, r = st.columns([1, 1.6], gap="large")
with l:
    prob_chart(P_try, 260)
with r:
    st.html(trace_html(P_try, decide(P_try, reject_t=rt), rt))
st.caption("The current model only knows HDPE, PET and OTHER. LDPE, PP and PVC wait for the team's own photos, "
           "but decide() already handles them.")

# ---------- 3. threshold on the test set ----------
section("Reject threshold on the whole test set",
        f"The sidebar threshold re-runs decide() on every saved test prediction. Now: reject_t = {rt:.2f}.")
sweep = load_sweep()
if pred is None or sweep is None:
    st.info("No training results yet. Run `python circu360_train_local.py`.")
else:
    dec = decide_all(pred, rt)
    contam, poly = pred["true"].isin(CONTAMINANTS), pred["true"].isin(POLYOLEFINS)
    leaked, n = int((dec[contam] == "ACCEPT").sum()), int(contam.sum())
    note = f"95% upper bound ≈ {3 / n:.1%} (rule of three)" if leaked == 0 and n else ""
    stat_row(stat("PET/PVC leaked into reactor", f"{leaked} of {n}", "measured", note),
             stat("PET/PVC recall (rejected)", f"{(dec[contam] == 'REJECT').mean():.1%}", "measured"),
             stat("Polyolefin false-reject", f"{(dec[poly] == 'REJECT').mean():.1%}", "measured"),
             stat("Sent to manual check", f"{(dec == 'UNCERTAIN').mean():.1%}", "measured"))
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        fig = go.Figure()
        for col, name, color in [("polyolefin_false_reject", "Polyolefin false-reject", CLASS_COLORS["HDPE"]),
                                 ("uncertain_frac", "Sent to manual check", CLASS_COLORS["LDPE"]),
                                 ("pet_leak_rate", "PET/PVC leak rate", CLASS_COLORS["PET"])]:
            fig.add_scatter(x=sweep["reject_t"], y=sweep[col] * 100, name=name, mode="lines+markers",
                            line=dict(color=color, width=2.5), marker=dict(size=7),
                            hovertemplate="reject_t %{x:.2f}: %{y:.1f}%<extra>" + name + "</extra>")
        fig.add_vline(x=rt, line_dash="dash", line_color=INK, annotation_text=f"now {rt:.2f}",
                      annotation_position="top right")
        fig.update_layout(xaxis_title="reject_t", yaxis_title="% of test items", hovermode="x unified")
        chart(fig, 360)
    with c2:
        cm = RUN_DIR / "confusion_matrix_test.png"
        if cm.exists():
            st.image(str(cm), caption="Confusion matrix (argmax, test set)", width="stretch")
    st.html('<div class="c3-note"><b>Limitations.</b> The test images come from the same photo set as the training '
            'images (clean, single objects), so real coastal waste will score lower. RGB cannot reliably separate '
            'clear PET from clear PVC, or HDPE from PP; NIR is the proposed upgrade. One can or glass bottle was '
            'ACCEPTed in the first test run.</div>')
