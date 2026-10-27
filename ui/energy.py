"""05 Energy balance: heating values are inputs; nothing unverified is computed until it is entered."""
import plotly.graph_objects as go
import streamlit as st

from ui.common import (REACTOR_FEED, YIELDS, INK, page_title, section, stat, stat_row, basis_tag, chart)

page_title("Energy balance", "How much energy the products carry, and whether the pyrolysis gas could heat the "
           "reactor. The gas heating value and the reactor heat demand are not verified yet, so you enter them.")

oil_kg, gas_kg = REACTOR_FEED * YIELDS["Liquid oil"], REACTOR_FEED * YIELDS["Gas"]
st.html(f'<p style="font-size:.92rem">Based on the case reactor feed of {REACTOR_FEED:,} kg/day {basis_tag("case")}: '
        f'{oil_kg:,.1f} kg/day oil and {gas_kg:,.1f} kg/day gas.</p>')

c = st.columns(3)
oil_hv = c[0].number_input("Oil heating value (MJ/kg)", 30.0, 50.0, 43.4, 0.1,
                           help="Sourced: HDPE oil 43.4–46.5 MJ/kg (Shah et al. 2023)")
gas_hv = c[1].number_input("Pyrolysis gas heating value (MJ/kg)", 0.0, 100.0, value=None,
                           placeholder="Enter a sourced value", help="ASSUMPTION until you cite a source")
demand = c[2].number_input("Reactor heat demand (MJ per kg feed)", 0.0, 20.0, value=None,
                           placeholder="Enter a sourced value", help="ASSUMPTION until you cite a source")

oil_mj = oil_kg * oil_hv
section("Results")
if gas_hv is None or demand is None:
    stat_row(stat("Energy in oil", f"{oil_mj:,.0f} MJ/day", "sourced", f"{oil_mj / 3.6:,.0f} kWh/day"))
    st.html('<div class="c3-note">Enter <b>both</b> the gas heating value and the reactor heat demand, each with a '
            'source, to compute the gas energy and whether it covers the reactor.</div>')
else:
    gas_mj, need_mj = gas_kg * gas_hv, REACTOR_FEED * demand
    cover = f"{gas_mj / need_mj:.0%}" if need_mj else "n/a"
    stat_row(stat("Energy in oil", f"{oil_mj:,.0f} MJ/day", "sourced", f"{oil_mj / 3.6:,.0f} kWh/day"),
             stat("Energy in gas", f"{gas_mj:,.0f} MJ/day", "assumption", f"{gas_mj / 3.6:,.0f} kWh/day"),
             stat("Reactor heat demand", f"{need_mj:,.0f} MJ/day", "assumption"),
             stat("Gas covers demand", cover, "assumption",
                  f"{gas_mj - need_mj:+,.0f} MJ/day surplus" if need_mj else ""))
    fig = go.Figure()
    fig.add_bar(x=["Energy in gas", "Reactor demand"], y=[gas_mj, need_mj], marker=dict(color=["#8a8984", INK]),
                text=[f"{gas_mj:,.0f}", f"{need_mj:,.0f}"], textposition="outside",
                hovertemplate="%{x}: %{y:,.0f} MJ/day<extra></extra>")
    fig.update_layout(yaxis=dict(title="MJ/day"), margin=dict(l=10, r=10, t=20, b=30))
    chart(fig, 300)
