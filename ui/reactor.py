"""04 Reactor & yields: the daily mass flow from mixed feed to oil, gas and char."""
import plotly.graph_objects as go
import streamlit as st

from ui.common import (CLASS_COLORS, FEED, REACTOR_FEED, YIELDS, OIL_BAND, INK, page_title, section, stat, stat_row,
                       basis_tag, chart)

PRODUCT_COLORS = {"Liquid oil": "#141414", "Gas": "#8a8984", "Char": "#5c5b57"}


def hex_rgba(color, alpha):
    color = color.lstrip("#")
    return f"rgba({int(color[0:2], 16)},{int(color[2:4], 16)},{int(color[4:6], 16)},{alpha})"


page_title("Reactor & yields", "Only polyolefins enter the containerized screw pyrolysis reactor, which runs "
           "continuously at about 430 °C and turns them into liquid oil, gas and char.")

feed_kg = st.number_input("Reactor feed (kg/day)", 100, 5000, REACTOR_FEED, 50,
                          help="The case brief gives 1,700 kg/day (HDPE + LDPE + PP). Change it to see the products scale.")
oil = feed_kg * YIELDS["Liquid oil"]
band = feed_kg * OIL_BAND
stat_row(stat("Reactor feed", f"{feed_kg:,.0f} kg/day", "case", f"≈{feed_kg / 24:,.0f} kg/h, continuous"),
         stat("Liquid oil", f"{oil:,.1f} kg/day", "case", f"model band {oil - band:,.0f}–{oil + band:,.0f} kg/day"),
         stat("Gas", f"{feed_kg * YIELDS['Gas']:,.1f} kg/day", "case", "16.8% of feed"),
         stat("Char", f"{feed_kg * YIELDS['Char']:,.1f} kg/day", "case", "5.4% of feed"))

section("Daily mass flow", "Hover a band to read its kg/day. Mixed feed → sorted streams → reactor → products.")
scale = feed_kg / REACTOR_FEED          # keep the case shares, scaled to the chosen reactor feed
nodes = ["Mixed coastal plastic"] + list(FEED) + ["Pyrolysis reactor", "Mechanical recyclers", "Residue"] + list(YIELDS)
idx = {n: i for i, n in enumerate(nodes)}
src, dst, val, col = [], [], [], []
for name, kg in FEED.items():
    src.append(idx["Mixed coastal plastic"]); dst.append(idx[name]); val.append(kg * scale)
    col.append(hex_rgba(CLASS_COLORS.get(name, CLASS_COLORS["OTHER"]), 0.35))
for name in ["HDPE", "LDPE", "PP"]:
    src.append(idx[name]); dst.append(idx["Pyrolysis reactor"]); val.append(FEED[name] * scale)
    col.append(hex_rgba(CLASS_COLORS[name], 0.35))
for name, target in [("PET", "Mechanical recyclers"), ("Dirt / non-plastic", "Residue")]:
    src.append(idx[name]); dst.append(idx[target]); val.append(FEED[name] * scale)
    col.append(hex_rgba(CLASS_COLORS.get(name, CLASS_COLORS["OTHER"]), 0.35))
for name, y in YIELDS.items():
    src.append(idx["Pyrolysis reactor"]); dst.append(idx[name]); val.append(feed_kg * y)
    col.append(hex_rgba(PRODUCT_COLORS[name], 0.25))
node_colors = ["#b9b9b2"] + [CLASS_COLORS.get(n, CLASS_COLORS["OTHER"]) for n in FEED] + [INK, "#8a8984", "#8a8984"] \
              + [PRODUCT_COLORS[n] for n in YIELDS]
sankey = go.Figure(go.Sankey(
    node=dict(label=nodes, color=node_colors, pad=20, thickness=18, line=dict(color=INK, width=0.5)),
    link=dict(source=src, target=dst, value=val, color=col,
              hovertemplate="%{source.label} → %{target.label}: %{value:,.1f} kg/day<extra></extra>"),
    valueformat=",.1f", valuesuffix=" kg/day", textfont=dict(family="Archivo, sans-serif", size=14, color=INK)))
chart(sankey, 460)

section("Product yields with the model error band", "Oil carries a ±9 percentage-point band (Belden et al. 2023).")
names = list(YIELDS)
fig = go.Figure(go.Bar(x=[feed_kg * YIELDS[n] for n in names], y=names, orientation="h",
                       marker=dict(color=[PRODUCT_COLORS[n] for n in names]),
                       error_x=dict(type="data", array=[band, 0, 0], color="#c0302f", thickness=2, width=8),
                       text=[f"{feed_kg * YIELDS[n]:,.0f} kg/day" for n in names], textposition="outside",
                       hovertemplate="%{y}: %{x:,.1f} kg/day<extra></extra>"))
fig.update_layout(xaxis=dict(title="kg/day", range=[0, (oil + band) * 1.15]), yaxis=dict(autorange="reversed"),
                  margin=dict(l=10, r=10, t=10, b=40))
chart(fig, 230)
st.html(f'<div class="c3-note">Yields 77.8 / 16.8 / 5.4% are {basis_tag("case")} values. The ±9 wt% model error '
        f'({basis_tag("sourced", "BELDEN 2023")}) is applied here as ±9 percentage points of the oil yield. The 5.4% '
        'char is high for clean polyolefins (literature 0.4–2%), so it is read as including wax, additives and dirt.</div>')
