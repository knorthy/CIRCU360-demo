"""01 Mixed feed: what arrives at the plant and where each plastic must go."""
import plotly.graph_objects as go
import streamlit as st

from ui.common import (CLASS_COLORS, CLASS_ITEMS, CLASS_ROUTE, CLASS_DECISION, CLASS_ORDER, IN_MODEL, FEED,
                       SORT_RATE_KG_H, INK, page_title, section, stat, stat_row, resin_badge, decision_tag,
                       basis_tag, chart)

WHY = {"PET": "Recycled mechanically instead; kept out of the reactor.",
       "HDPE": "Polyolefin: the reactor's intended feed.",
       "PVC": "Releases about 58 wt% of its mass as HCl when heated; goes to specialist disposal.",
       "LDPE": "Polyolefin: the reactor's intended feed.",
       "PP": "Polyolefin: the reactor's intended feed.",
       "OTHER": "Cans, glass and dirt are not plastic."}
FEED_KEY = {"PET": "PET", "HDPE": "HDPE", "LDPE": "LDPE", "PP": "PP", "OTHER": "Dirt / non-plastic"}

page_title("Mixed feed", "Mixed plastic collected from the coast in Indonesia and the Philippines. "
           "Only the polyolefins (HDPE, LDPE, PP) may enter the pyrolysis reactor.")

total = st.number_input("Daily feed (kg/day)", 200, 10000, 2000, 100,
                        help="The case brief uses 2,000 kg/day. Change it to see how the streams and shift hours scale.")
share = {k: v / sum(FEED.values()) for k, v in FEED.items()}
reactor = sum(share[c] for c in ["HDPE", "LDPE", "PP"]) * total
hours = total / SORT_RATE_KG_H
stat_row(stat("Mixed feed", f"{total:,.0f} kg/day", "case"),
         stat("To the reactor", f"{reactor:,.0f} kg/day", "case", f"≈{reactor / 24:,.0f} kg/h, running continuously"),
         stat("Sorting line", f"{hours:,.1f} h/day", "case", f"at {SORT_RATE_KG_H} kg/h, two shifts"))

section("Feed composition", "Share of each class in the case feed, by mass.")
fig = go.Figure()
for name, s in share.items():
    color = CLASS_COLORS.get(name, CLASS_COLORS["OTHER"])
    fig.add_bar(y=["feed"], x=[s * total], orientation="h", name=name, marker=dict(color=color, line=dict(color="#ffffff", width=2)),
                text=f"{name}  {s:.0%}", textposition="inside", insidetextanchor="start",
                textfont=dict(color="#ffffff" if name in ("HDPE", "PET") else INK, size=14),
                hovertemplate=f"{name}: %{{x:,.0f}} kg/day ({s:.0%})<extra></extra>")
fig.update_layout(barmode="stack", showlegend=False, yaxis=dict(visible=False),
                  xaxis=dict(title="kg/day", gridcolor="#ececE8"), margin=dict(l=10, r=10, t=10, b=40))
chart(fig, 150)

section("Where each class must go",
        "The routing the AI sorter has to achieve. PVC is not in the case feed, but any piece that turns up is rejected.")
rows = []
for cls in CLASS_ORDER:
    kg = share.get(FEED_KEY.get(cls, ""), 0) * total
    model = "yes" if cls in IN_MODEL else "<b>not yet</b>: team photos needed"
    rows.append(f'<tr><td><div class="c3-cls">{resin_badge(cls, 34)}{cls}</div></td><td>{CLASS_ITEMS[cls]}</td>'
                f'<td class="n">{f"{kg:,.0f}" if kg else "—"}</td>'
                f'<td>{decision_tag(CLASS_DECISION[cls], route=False)} → {CLASS_ROUTE[cls]}</td>'
                f'<td>{WHY[cls]}</td><td>{model}</td></tr>')
st.html('<table class="c3-table"><tr><th>Resin code</th><th>Typical items</th><th class="n">kg/day</th>'
        f'<th>Decision and route</th><th>Why</th><th>In the model</th></tr>{"".join(rows)}</table>')
st.html(f'<p style="margin-top:.6rem;font-size:.9rem">All kg/day values: {basis_tag("case")} '
        f'scaled from the essay feed (HDPE 35%, LDPE 30%, PP 20%, PET 10%, dirt/non-plastic 5%).</p>')
