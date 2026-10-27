"""CIRCU360 - monitoring dashboard (Streamlit + Plotly).

Run:   streamlit run dashboard.py
Then start belt_sim.py in a second terminal: the overview refreshes every 2 s from events.csv.

Pages live in ui/ (one file per process stage). Shared colours, case numbers and helpers are in ui/common.py.
"""
import streamlit as st

from ui.common import DECIDE_DEFAULTS, inject_css

st.set_page_config(page_title="CIRCU360", page_icon=":material/recycling:", layout="wide")
inject_css()

pages = {
    "Live": [st.Page("ui/overview.py", title="Plant overview", icon=":material/factory:", default=True)],
    "Process stages": [
        st.Page("ui/feed.py", title="1  Mixed feed", url_path="feed"),
        st.Page("ui/sorting.py", title="2  AI sorting", url_path="sorting"),
        st.Page("ui/belt.py", title="3  Belt & ejector", url_path="belt"),
        st.Page("ui/reactor.py", title="4  Reactor & yields", url_path="reactor"),
        st.Page("ui/energy.py", title="5  Energy balance", url_path="energy"),
    ],
}
nav = st.navigation(pages)

with st.sidebar:
    st.html('<div style="border-bottom:3px solid #141414;padding-bottom:.6rem">'
            '<div style="font-size:1.6rem;font-weight:800;letter-spacing:-0.01em;line-height:1">CIRCU360</div>'
            '<div style="font-size:.85rem;color:#3d3d3a;margin-top:.3rem">Safety-first plastic recovery micro-plant. '
            'Prototype: live data comes from the belt simulation, not a real plant.</div></div>')
    st.slider("Reject threshold (reject_t)", 0.05, 0.95, DECIDE_DEFAULTS["reject_t"], 0.05, key="reject_t",
              help="REJECT if P(PET) + P(PVC) > reject_t. A process-safety parameter: lower is more cautious. "
                   "Used on the AI sorting page and in the overview text; the belt simulation uses its own --reject-t.")

nav.run()
