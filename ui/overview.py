"""Plant overview: live view of the belt, organised by resin code."""
import streamlit as st

from decision import CONTAMINANTS, POLYOLEFINS
from ui.common import (CLASS_ORDER, CLASS_ITEMS, CLASS_ROUTE, CLASS_DECISION, DECISION_COLORS, DECISION_INK,
                       DECISIONS, IN_MODEL, load_events, resin_badge, decision_tag, basis_tag, reject_t)

CSS = """
<style>
.c3-live { display:flex; align-items:center; gap:.5rem; font-weight:700; font-size:.95rem; margin:.2rem 0 .8rem; }
.c3-live i { width:.7rem; height:.7rem; border-radius:50%; background:#0ca30c; display:inline-block;
             animation: c3pulse 1.6s ease-out infinite; }
.c3-live.idle i { background:#b9b9b2; animation:none; }
@keyframes c3pulse { 0% { box-shadow:0 0 0 0 rgba(12,163,12,.55); } 100% { box-shadow:0 0 0 .6rem rgba(12,163,12,0); } }
@media (prefers-reduced-motion: reduce) { .c3-live i { animation:none; } }

.c3-resins { display:grid; grid-template-columns:repeat(6, minmax(0,1fr)); border-top:3px solid #141414; border-bottom:1px solid #141414; }
.c3-res { padding:1rem 1rem 1.1rem; border-right:1px solid #d6d6d0; display:flex; flex-direction:column; gap:.35rem; }
.c3-res:last-child { border-right:0; }
.c3-res h3 { font-size:1.5rem; font-weight:800; margin:.3rem 0 0; padding:0; line-height:1; }
.c3-res .items { font-size:.85rem; color:#3d3d3a; min-height:2.3em; }
.c3-res .count { font-size:2.6rem; font-weight:800; line-height:1; letter-spacing:-0.02em; }
.c3-res .count small { font-size:.85rem; font-weight:600; letter-spacing:0; color:#3d3d3a; margin-left:.3rem; }
.c3-res .count.none { color:#8a8984; }
.c3-res .pending { font-size:.82rem; color:#4a4a46; min-height:1.2em; }
.c3-mix { display:flex; height:.55rem; background:#ececE8; }
.c3-mix span { display:block; height:100%; }
.c3-route { margin-top:auto; border:2px solid #141414; padding:.35rem .5rem; font-weight:800; font-size:.85rem; line-height:1.2; }
.c3-route.reactor { background:#141414; color:#ffffff; }

.c3-split { display:grid; grid-template-columns:minmax(260px, 1fr) 2.2fr; gap:2.2rem; margin-top:1.4rem; }
.c3-leak { border-top:3px solid #141414; padding-top:.6rem; }
.c3-leak .num { font-size:8.5rem; font-weight:800; line-height:.9; letter-spacing:-0.04em; }
.c3-leak .num.bad { color:#c0302f; }
.c3-leak h2 { font-size:1.3rem; font-weight:800; margin:.5rem 0 .3rem; padding:0; line-height:1.2; }
.c3-leak p { font-size:.92rem; color:#3d3d3a; margin:.2rem 0; }
.c3-log { border-top:3px solid #141414; padding-top:.6rem; }
.c3-log h2 { font-size:1.3rem; font-weight:800; margin:0 0 .4rem; padding:0; }
.c3-empty { padding:1.2rem 0; font-size:1rem; color:#3d3d3a; }
.c3-empty code { background:#f1f1ee; padding:.1rem .35rem; color:#141414; }
@media (max-width: 1100px) { .c3-resins { grid-template-columns:repeat(3, minmax(0,1fr)); }
                             .c3-res:nth-child(3n) { border-right:0; } .c3-res { border-bottom:1px solid #d6d6d0; }
                             .c3-split { grid-template-columns:1fr; } }
@media (max-width: 640px) { .c3-resins { grid-template-columns:repeat(2, minmax(0,1fr)); } }
</style>
"""

STAGES = [("ui/feed.py", "Mixed feed", "What comes in and where each plastic should go"),
          ("ui/sorting.py", "AI sorting", "Walk one item through decide(), tune reject_t"),
          ("ui/belt.py", "Belt & ejector", "Camera-to-ejector timing and latency"),
          ("ui/reactor.py", "Reactor & yields", "1,700 kg/day of polyolefins to oil, gas and char"),
          ("ui/energy.py", "Energy balance", "Editable heating values, nothing assumed")]


def resin_row(ev):
    cols = []
    for cls in CLASS_ORDER:
        sub = ev[ev["true_class"] == cls] if ev is not None and len(ev) else ev
        n = 0 if sub is None else len(sub)
        if cls in IN_MODEL:
            count = f'<div class="count">{n}<small>items</small></div>'
            pending = "&nbsp;"
        else:
            count = '<div class="count none">—</div>'
            pending = "Not in the model yet"
        mix = ""
        if n:
            counts = sub["decision"].value_counts()
            mix = "".join(f'<span style="width:{counts.get(d, 0) / n:.1%};background:{DECISION_COLORS[d]}" '
                          f'title="{d}: {counts.get(d, 0)}"></span>' for d in DECISIONS)
        reactor = " reactor" if CLASS_ROUTE[cls] == "Pyrolysis reactor" else ""
        cols.append(f'<div class="c3-res">{resin_badge(cls, 52)}<h3>{cls}</h3>'
                    f'<div class="items">{CLASS_ITEMS[cls]}</div>{count}<div class="pending">{pending}</div>'
                    f'<div class="c3-mix">{mix}</div>'
                    f'<div class="c3-route{reactor}">{CLASS_DECISION[cls]} → {CLASS_ROUTE[cls]}</div></div>')
    return f'<div class="c3-resins">{"".join(cols)}</div>'


def leak_block(ev):
    contam = ev[ev["true_class"].isin(CONTAMINANTS)]
    leaked = int((contam["decision"] == "ACCEPT").sum())
    n = len(contam)
    bound = (f"<p>With 0 leaks in {n} contaminant items, the true leak rate is below about {3 / n:.0%} "
             f"(95% confidence, rule of three).</p>" if leaked == 0 and n else "")
    return (f'<div class="c3-leak"><div class="num{" bad" if leaked else ""}">{leaked}</div>'
            f'<h2>PET/PVC items accepted into the reactor</h2>'
            f'<p>{n} PET/PVC items have reached the camera this run. {basis_tag("measured")}</p>{bound}'
            f'<p>On the 226 PET test images: 0 leaks at every reject_t from 0.05 to 0.95.</p></div>')


def log_block(ev):
    rows = []
    for _, r in ev.tail(10).iloc[::-1].iterrows():
        bad = r["true_class"] in CONTAMINANTS and r["decision"] == "ACCEPT"
        style = ' style="background:#fbe9e8"' if bad else ""
        p_bad = sum(r.get(f"P_{c}", 0) or 0 for c in CONTAMINANTS)
        p_poly = sum(r.get(f"P_{c}", 0) or 0 for c in POLYOLEFINS)
        rows.append(f'<tr{style}><td class="n">{int(r["item"])}</td>'
                    f'<td><div class="c3-cls">{resin_badge(r["true_class"], 22)}{r["true_class"]}</div></td>'
                    f'<td class="n">{p_bad:.3f}</td><td class="n">{p_poly:.3f}</td>'
                    f'<td class="n">{r["latency_ms"]:.1f} ms</td><td>{decision_tag(r["decision"])}</td></tr>')
    return ('<div class="c3-log"><h2>Latest items on the belt</h2><table class="c3-table"><tr><th class="n">Item</th>'
            '<th>True class</th><th class="n">P(PET+PVC)</th><th class="n">P(polyolefin)</th><th class="n">Latency</th>'
            f'<th>Decision and route</th></tr>{"".join(rows)}</table></div>')


@st.fragment(run_every="2s")
def live():
    ev = load_events()
    if ev is None or ev.empty:
        st.html('<div class="c3-live idle"><i></i>Belt idle</div>' + resin_row(None) +
                '<div class="c3-empty">No items have reached the camera yet. Start the belt in a second terminal: '
                '<code>python belt_sim.py</code>. This page refreshes every 2 seconds.</div>')
        return
    counts = ev["decision"].value_counts()
    summary = " · ".join(f'<span style="color:{DECISION_INK[d]}">{counts.get(d, 0)} {d}</span>' for d in DECISIONS)
    st.html(f'<div class="c3-live"><i></i>Live from belt_sim.py · {len(ev)} items · {summary}</div>'
            + resin_row(ev) + f'<div class="c3-split">{leak_block(ev)}{log_block(ev)}</div>')


st.html(CSS)
st.html('<div class="c3-title"><h1>Plant overview</h1><p>Every plastic is shown under the resin code moulded on '
        'its bottle, with the route it must take. PET and PVC are checked first and can never be sent to the '
        f'reactor. Reject threshold now: <b>{reject_t():.2f}</b> (set it in the sidebar).</p></div>')
live()
st.html('<div class="c3-section"><h2>Walk through the process</h2>'
        '<p>Each stage has its own page with the details and controls.</p></div>')
for col, (page, title, blurb) in zip(st.columns(len(STAGES)), STAGES):
    with col:
        st.page_link(page, label=title, icon=":material/arrow_forward:")
        st.caption(blurb)
