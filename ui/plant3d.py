"""3D plant: a clickable model of the whole micro-plant (three.js scene in ui/plant3d.html)."""
import json
import subprocess
import sys
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from decision import belt_timing, BELT_SPEED_M_S, CAMERA_FPS, EJECTOR_DISTANCE_M, VALVE_DELAY_MS, CONTAMINANTS
from ui.common import (CLASS_COLORS, DECISION_COLORS, DECISION_INK, DECISIONS, FEED, REACTOR_FEED, YIELDS, OIL_BAND,
                       SORT_RATE_KG_H, load_events, load_predictions, decide_all, probs, reject_t, page_title, ROOT)

REACTOR_TEMP_C = 430     # case brief: about 430 °C
LIVE_JSON = ROOT / "static" / "live" / "belt.json"   # written by belt_sim.py while it runs


def belt_running():
    try:
        s = json.loads(LIVE_JSON.read_text())
        return bool(s.get("running")) and time.time() - s["updated"] < 3
    except (OSError, ValueError, KeyError):
        return False


def start_belt(speed, n_items):
    log = open(ROOT / "belt_sim_log.txt", "w")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    st.session_state.belt_proc = subprocess.Popen(
        [sys.executable, "belt_sim.py", "--no-window", "--speed", str(speed), "--items", str(n_items),
         "--reject-t", str(reject_t())], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)


def stop_belt():
    st.session_state.belt_proc.terminate()
    try:                                     # tell the 3D page straight away instead of waiting for the timeout
        s = json.loads(LIVE_JSON.read_text())
        LIVE_JSON.write_text(json.dumps({**s, "running": False}))
    except (OSError, ValueError):
        pass


def build_data():
    rt = reject_t()
    ev = load_events()
    live = {"n": 0}
    if ev is not None and len(ev):
        contam = ev[ev["true_class"].isin(CONTAMINANTS)]
        live = {"n": len(ev), "counts": {d: int((ev["decision"] == d).sum()) for d in DECISIONS},
                "leaked": int((contam["decision"] == "ACCEPT").sum()), "contam": len(contam),
                "lat_mean": float(ev["latency_ms"].mean()), "lat_p95": float(ev["latency_ms"].quantile(0.95))}

    # the animation replays real decisions: the last belt run, or else a sample of the test set
    pred = load_predictions()
    if live["n"]:
        src, rows = "belt", ev.tail(60)
        replay = [{"c": r["true_class"], "d": r["decision"], "p": probs(r)} for _, r in rows.iterrows()]
    elif pred is not None:
        src, rows = "test", pred.sample(min(60, len(pred)), random_state=1)
        dec = decide_all(rows, rt)
        replay = [{"c": r["true"], "d": dec[i], "p": probs(r)} for i, r in rows.iterrows()]
    else:
        src, replay = "none", []

    test = {"n": 0, "accuracy": 0, "pet_n": 0}
    if pred is not None:
        test = {"n": len(pred), "accuracy": float((pred["true"] == pred["pred"]).mean()),
                "pet_n": int((pred["true"] == "PET").sum())}

    t = belt_timing()
    return {
        "reject_t": rt, "replay": replay, "replay_source": src, "live": live, "test": test,
        "class_colors": {k: int(v[1:], 16) for k, v in CLASS_COLORS.items()},
        "decision_colors": DECISION_COLORS, "decision_ink": DECISION_INK,
        "timing": {"belt_m_s": BELT_SPEED_M_S, "fps": CAMERA_FPS, "ejector_m": EJECTOR_DISTANCE_M,
                   "valve_ms": VALVE_DELAY_MS, "mm_per_frame": t["mm_per_frame"],
                   "mm_during_inference": t["mm_during_inference"], "fire_ms": t["fire_after_capture_ms"],
                   "slack_ms": t["slack_ms"]},
        "case": {"feed": sum(FEED.values()), "composition": FEED, "sort_rate": SORT_RATE_KG_H,
                 "reactor_feed": REACTOR_FEED, "reactor_temp": REACTOR_TEMP_C, "yields": YIELDS, "oil_band": OIL_BAND},
    }


page_title("3D plant", "The whole micro-plant as a model. Drag to turn it, scroll to zoom, and click any part "
           "or its label to see what happens there. Items on the belt replay real decisions.")
proc = st.session_state.get("belt_proc")
ours = proc is not None and proc.poll() is None
running = ours or belt_running()
c1, c2, c3, c4, c5 = st.columns([1.1, 1.1, 1, 1.4, 1.6], vertical_alignment="bottom")
speed = c3.selectbox("Speed", [0.25, 0.5, 1.0], format_func=lambda v: "real time" if v == 1 else f"{v}× (slow motion)",
                     disabled=running)
n_items = c4.number_input("Items", 10, 300, 80, 10, disabled=running)
if c1.button("Start belt", icon=":material/play_arrow:", type="primary", disabled=running,
             help="Runs python belt_sim.py in the background. Click CAM in the 3D view to watch it."):
    start_belt(speed, n_items)
    st.rerun()
if c2.button("Stop belt", icon=":material/stop:", disabled=not ours,
             help="Only stops a belt started here. Close a terminal run with q or Esc in its window."):
    stop_belt()
    st.rerun()
c5.button("Reload numbers", icon=":material/refresh:", help="Re-reads events.csv for the part panels. The view resets.")
if running:
    st.caption("The belt is running. Click **CAM** to watch belt_sim.py live. The first item takes a few seconds "
               "while the model loads.")
st.caption("Equipment after the belt (condenser, tanks, bins) is drawn for illustration; its size and layout are "
           "not part of the essay's design.")
html = Path(__file__).with_name("plant3d.html").read_text(encoding="utf-8")
components.html(html.replace("__DATA__", json.dumps(build_data())), height=760)
