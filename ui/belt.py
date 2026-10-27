"""03 Belt & ejector: how long the sorter has between the camera and the air jet."""
import plotly.graph_objects as go
import streamlit as st

from decision import (belt_timing, BELT_SPEED_M_S, CAMERA_FPS, INFERENCE_MS, EJECTOR_DISTANCE_M, VALVE_DELAY_MS)
from ui.common import (CLASS_COLORS, DECISION_COLORS, INK, load_events, page_title, section, stat, stat_row,
                       basis_tag, chart)

page_title("Belt & ejector", f"Items ride the belt at {BELT_SPEED_M_S} m/s. The camera photographs each one, the model "
           f"decides, and an air jet {EJECTOR_DISTANCE_M * 1000:.0f} mm downstream blows REJECT items off the belt.")

ev = load_events()
measured = ev["latency_ms"] if ev is not None and len(ev) else None

options = {f"Spec: {INFERENCE_MS} ms": float(INFERENCE_MS)}
if measured is not None:
    options[f"Measured mean: {measured.mean():.1f} ms"] = float(measured.mean())
    options[f"Measured p95: {measured.quantile(0.95):.1f} ms"] = float(measured.quantile(0.95))
choice = st.segmented_control("Inference time to use", list(options), default=list(options)[0], key="belt_lat")
lat = options.get(choice, float(INFERENCE_MS))
t = belt_timing(lat)

stat_row(stat("Belt travel per frame", f"{t['mm_per_frame']:.1f} mm", "case", f"{CAMERA_FPS} fps camera"),
         stat("Belt travel while deciding", f"{t['mm_during_inference']:.0f} mm", "measured" if lat != INFERENCE_MS else "case"),
         stat("Ejector fires after capture", f"{t['fire_after_capture_ms']:.0f} ms", "assumption",
              f"{EJECTOR_DISTANCE_M * 1000:.0f} mm ÷ {BELT_SPEED_M_S} m/s − {VALVE_DELAY_MS} ms valve"),
         stat("Slack after the decision", f"{t['slack_ms']:.0f} ms", "assumption", "time left before the jet must fire"))

section("Timeline of one item", "From the moment the camera captures the item to the moment it reaches the ejector.")
fig = go.Figure()
lanes = [("Belt carries item to ejector", 0, t["travel_time_ms"], "#d6d6d0"),
         ("Model decides", 0, lat, CLASS_COLORS["HDPE"]),
         ("Slack (waiting)", lat, t["fire_after_capture_ms"], "#ececE8"),
         ("Air valve opens", t["fire_after_capture_ms"], t["travel_time_ms"], DECISION_COLORS["REJECT"])]
for name, start, end, color in lanes:
    fig.add_bar(y=[name], x=[end - start], base=[start], orientation="h", marker=dict(color=color, line=dict(color=INK, width=1)),
                hovertemplate=f"{name}: {start:.0f}–{end:.0f} ms<extra></extra>", showlegend=False)
fig.add_vline(x=t["fire_after_capture_ms"], line_color=INK, line_dash="dash",
              annotation_text=f"fire at {t['fire_after_capture_ms']:.0f} ms", annotation_position="top")
fig.update_layout(xaxis=dict(title="ms after capture", range=[0, t["travel_time_ms"] * 1.04]),
                  yaxis=dict(autorange="reversed"), bargap=0.35, margin=dict(l=10, r=10, t=44, b=40))
chart(fig, 280)
st.html(f'<p style="font-size:.92rem;max-width:80ch">Ejector distance ({EJECTOR_DISTANCE_M * 1000:.0f} mm) and valve '
        f'delay ({VALVE_DELAY_MS} ms) are {basis_tag("assumption")} values, not sourced. They live in '
        '<code>decision.py</code>, so changing them there updates the belt simulation and this page together.</p>')

section("Measured latency on this laptop",
        "End-to-end time per item in the belt simulation: pre-processing, model and post-processing.")
if measured is None:
    st.info("No belt data yet. Start the belt: `python belt_sim.py`")
else:
    stat_row(stat("Items", f"{len(measured)}", "measured"),
             stat("Mean", f"{measured.mean():.1f} ms", "measured"),
             stat("p95", f"{measured.quantile(0.95):.1f} ms", "measured"),
             stat("Over the 35 ms spec", f"{(measured > INFERENCE_MS).sum()}", "measured"))
    hist = go.Figure(go.Histogram(x=measured, nbinsx=30, marker=dict(color=CLASS_COLORS["HDPE"], line=dict(color="#ffffff", width=1)),
                                  hovertemplate="%{x} ms: %{y} items<extra></extra>"))
    hist.add_vline(x=INFERENCE_MS, line_dash="dash", line_color=INK, annotation_text="35 ms spec", annotation_position="top")
    hist.update_layout(xaxis_title="latency (ms)", yaxis_title="items", margin=dict(l=10, r=10, t=44, b=40))
    chart(hist, 300)
