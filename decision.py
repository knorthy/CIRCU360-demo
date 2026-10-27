"""Shared decision rule (essay Table 3) and belt-timing numbers.

Imported by circu360_train_local.py, belt_sim.py and dashboard.py,
so the sorting logic lives in exactly one place.
"""

CLASSES = ["HDPE", "LDPE", "PP", "PET", "PVC", "OTHER"]
POLYOLEFINS = ["HDPE", "LDPE", "PP"]   # allowed into the pyrolysis reactor
CONTAMINANTS = ["PET", "PVC"]          # must never reach the reactor


def decide(P, reject_t=0.30, accept_t=0.90, other_t=0.90):
    if P.get("PET", 0) + P.get("PVC", 0) > reject_t:  return "REJECT"     # checked FIRST: PET/PVC can never be accepted
    if P.get("HDPE", 0) + P.get("LDPE", 0) + P.get("PP", 0) >= accept_t:  return "ACCEPT"
    if P.get("OTHER", 0) >= other_t:  return "REMOVE"   # non-plastic stream (added for this dataset)
    return "UNCERTAIN"                                  # manual inspection / float-sink test


# --- Belt timing (essay vision spec) ---
BELT_SPEED_M_S = 0.8
CAMERA_FPS = 60
INFERENCE_MS = 35            # spec value; compare with the latency measured on your hardware
EJECTOR_DISTANCE_M = 0.40    # ASSUMPTION: ejector placed 0.40 m downstream of the camera
VALVE_DELAY_MS = 15          # ASSUMPTION: air-valve response time, not sourced


def belt_timing(inference_ms=INFERENCE_MS):
    """Belt travel and ejector firing time. 0.8 m/s is the same as 0.8 mm/ms."""
    travel_ms = EJECTOR_DISTANCE_M / BELT_SPEED_M_S * 1000
    fire_ms = travel_ms - VALVE_DELAY_MS          # fire at capture_time + D/v - t_valve
    return {
        "mm_per_frame": BELT_SPEED_M_S * 1000 / CAMERA_FPS,
        "mm_during_inference": BELT_SPEED_M_S * inference_ms,
        "travel_time_ms": travel_ms,
        "fire_after_capture_ms": fire_ms,
        "slack_ms": fire_ms - inference_ms,       # time left after the decision is ready
    }
