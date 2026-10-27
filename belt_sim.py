"""CIRCU360 - conveyor belt simulation (OpenCV).

Test images ride a virtual belt at 0.8 m/s (1 px = 1 mm, 60 fps). Each item is
classified when it crosses the camera line, decide() picks ACCEPT / REJECT /
REMOVE / UNCERTAIN, and a virtual air ejector 400 mm downstream knocks REJECT
items off the belt. Every item is logged to events.csv (read live by
dashboard.py) and the run is recorded to demo.mp4 as a fallback for the demo.

Run:            python belt_sim.py
Options:        --speed 0.25  --items 80  --reject-t 0.30  --onnx  --no-window  --seed 1
                --speed is playback only (0.25 = 4x slow motion, 1 = real time); the simulated
                belt is always 0.8 m/s, so timings and events.csv do not change.
Keys:           q or Esc to stop early
"""
import argparse
import csv
import random
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from decision import (decide, belt_timing, BELT_SPEED_M_S, CAMERA_FPS,
                      EJECTOR_DISTANCE_M, VALVE_DELAY_MS)

ROOT = Path(__file__).resolve().parent
TEST_DIR = ROOT / "data" / "split" / "test"
WEIGHTS = ROOT / "runs" / "circu360" / "weights"
EVENTS_CSV = ROOT / "events.csv"
VIDEO = ROOT / "demo.mp4"

# Canvas layout, 1 px = 1 mm
W, H = 1400, 440
BELT_TOP, BELT_BOTTOM = 130, 330
ITEM = 120                                        # item picture size, px
CAMERA_X = 330                                    # trigger line
EJECTOR_X = CAMERA_X + int(EJECTOR_DISTANCE_M * 1000)   # 400 px downstream
PX_PER_FRAME = BELT_SPEED_M_S * 1000 / CAMERA_FPS        # 13.3 px per frame

# Decision colours (BGR), same as the dashboard: status green/red/amber + neutral grey
COLORS = {"ACCEPT": (12, 163, 12), "REJECT": (59, 59, 208),
          "REMOVE": (150, 150, 150), "UNCERTAIN": (25, 178, 250)}


class Item:
    def __init__(self, path):
        self.path = path
        self.true = path.parent.name
        # keep the original image: pre-shrinking it changed borderline probabilities by up to 0.2
        self.full = img = cv2.imread(str(path))            # what the camera "sees"
        self.pic = cv2.resize(img, (ITEM, ITEM))           # what we draw
        self.x = -ITEM                                     # left edge, starts off-screen
        self.y = (BELT_TOP + BELT_BOTTOM) // 2 - ITEM // 2
        self.decision = None
        self.fire_t = None        # simulated time the ejector valve is triggered
        self.ejected = False


def paste(canvas, img, x, y):
    """Draw img on canvas at (x, y), clipped to the canvas edges."""
    x, y = int(x), int(y)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x0 < x1 and y0 < y1:
        canvas[y0:y1, x0:x1] = img[y0 - y:y1 - y, x0 - x:x1 - x]


def classify(model, img):
    t0 = time.perf_counter()
    r = model.predict(img, imgsz=224, verbose=False)[0]
    latency_ms = (time.perf_counter() - t0) * 1000           # pre + model + post on this laptop
    probs = r.probs.data.cpu().numpy()
    return {r.names[i]: float(p) for i, p in enumerate(probs)}, latency_ms


def draw_scene(canvas, frame_no, counts, last_latency, sim_t, blast, speed):
    canvas[:] = (245, 245, 245)
    # belt with moving stripes so the motion is visible
    cv2.rectangle(canvas, (0, BELT_TOP), (W, BELT_BOTTOM), (60, 60, 60), -1)
    offset = int(frame_no * PX_PER_FRAME) % 80
    for x in range(-80 + offset, W, 80):
        cv2.line(canvas, (x, BELT_TOP), (x, BELT_BOTTOM), (80, 80, 80), 2)
    # reject chute below the ejector
    cv2.rectangle(canvas, (EJECTOR_X - 70, BELT_BOTTOM + 5), (EJECTOR_X + 70, H), (220, 220, 240), -1)
    cv2.putText(canvas, "PET/PVC chute", (EJECTOR_X - 62, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (59, 59, 208), 1)
    # camera and ejector lines
    cv2.line(canvas, (CAMERA_X, BELT_TOP - 30), (CAMERA_X, BELT_BOTTOM), (208, 120, 42), 2)
    cv2.putText(canvas, "CAMERA", (CAMERA_X - 34, BELT_TOP - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (208, 120, 42), 1)
    ej_color = (59, 59, 208) if blast else (120, 120, 120)
    cv2.line(canvas, (EJECTOR_X, BELT_TOP - 30), (EJECTOR_X, BELT_BOTTOM), ej_color, 4 if blast else 2)
    cv2.putText(canvas, "AIR EJECTOR (+400 mm)", (EJECTOR_X - 90, BELT_TOP - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.5, ej_color, 1)
    cv2.putText(canvas, "to pyrolysis reactor ->", (W - 230, BELT_TOP - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (12, 130, 12), 1)
    # HUD
    hud = (f"t = {sim_t:6.2f} s   belt 0.8 m/s   {PX_PER_FRAME:.1f} mm/frame   "
           f"last inference {last_latency:5.1f} ms")
    cv2.putText(canvas, hud, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1)
    if speed != 1:
        cv2.putText(canvas, f"SLOW MOTION x{speed:g}", (W - 210, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (208, 120, 42), 2)
    x = 12
    for name, color in COLORS.items():
        text = f"{name} {counts[name]}"
        cv2.rectangle(canvas, (x, 40), (x + 14, 54), color, -1)
        cv2.putText(canvas, text, (x + 20, 53), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 1)
        x += 30 + 11 * len(text)
    cv2.putText(canvas, f"ASSUMPTIONS: ejector distance {EJECTOR_DISTANCE_M} m, valve delay {VALVE_DELAY_MS} ms",
                (12, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 90, 90), 1)


def draw_item(canvas, it):
    paste(canvas, it.pic, it.x, it.y)
    if it.decision:
        color = COLORS[it.decision]
        cv2.rectangle(canvas, (int(it.x), it.y), (int(it.x) + ITEM, it.y + ITEM), color, 3)
        cv2.rectangle(canvas, (int(it.x), it.y - 20), (int(it.x) + ITEM, it.y), color, -1)
        cv2.putText(canvas, it.decision, (int(it.x) + 4, it.y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=0.25, help="playback speed: 0.25 = 4x slow motion, 1 = real time")
    ap.add_argument("--items", type=int, default=80, help="number of items to send down the belt")
    ap.add_argument("--reject-t", type=float, default=0.30)
    ap.add_argument("--onnx", action="store_true", help="use best.onnx instead of best.pt")
    ap.add_argument("--no-window", action="store_true", help="only record demo.mp4, no live window")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    random.seed(args.seed)
    files = sorted(p for p in TEST_DIR.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not files:
        raise SystemExit(f"No test images in {TEST_DIR}. Run circu360_train_local.py first.")
    queue = [Item(p) for p in random.sample(files, min(args.items, len(files)))]

    model = YOLO(str(WEIGHTS / ("best.onnx" if args.onnx else "best.pt")), task="classify")
    classify(model, queue[0].full)                       # warm-up, so the first latency is realistic
    fire_after_s = belt_timing()["fire_after_capture_ms"] / 1000

    canvas = np.zeros((H, W, 3), np.uint8)
    # the video plays at the same speed as the window (60 fps x speed)
    video = cv2.VideoWriter(str(VIDEO), cv2.VideoWriter_fourcc(*"mp4v"), CAMERA_FPS * args.speed, (W, H))
    frame_wall_s = 1 / (CAMERA_FPS * args.speed)          # how long each frame stays on screen
    counts = {k: 0 for k in COLORS}
    on_belt, frame_no, next_gap, last_latency, blast_until = [], 0, 0.0, 0.0, -1.0

    with open(EVENTS_CSV, "w", newline="") as f:
        log = csv.writer(f)
        log.writerow(["wall_time", "sim_time_s", "item", "file", "true_class", "P_HDPE", "P_LDPE", "P_PP",
                      "P_PET", "P_PVC", "P_OTHER", "decision", "latency_ms", "eject_fire_s"])
        item_no = 0
        while queue or on_belt:
            frame_start = time.perf_counter()
            sim_t = frame_no / CAMERA_FPS                # simulated time, always at true belt speed

            # put a new item on the belt after a random gap
            next_gap -= PX_PER_FRAME
            if queue and next_gap <= 0:
                on_belt.append(queue.pop())
                next_gap = ITEM + random.randint(40, 200)

            for it in on_belt:
                if it.ejected:
                    it.y += 18                           # blown off the belt into the chute
                else:
                    it.x += PX_PER_FRAME

                # camera trigger: classify once, when the item centre crosses the line
                if it.decision is None and it.x + ITEM / 2 >= CAMERA_X:
                    P, last_latency = classify(model, it.full)
                    it.decision = decide(P, reject_t=args.reject_t)
                    counts[it.decision] += 1
                    if it.decision == "REJECT":
                        it.fire_t = sim_t + fire_after_s          # capture + D/v - t_valve
                    item_no += 1
                    log.writerow([datetime.now().isoformat(timespec="milliseconds"), f"{sim_t:.3f}", item_no,
                                  it.path.name, it.true] +
                                 [f"{P.get(c, 0):.4f}" for c in ["HDPE", "LDPE", "PP", "PET", "PVC", "OTHER"]] +
                                 [it.decision, f"{last_latency:.2f}", f"{it.fire_t:.3f}" if it.fire_t else ""])
                    f.flush()                                     # so the dashboard sees it immediately

                # ejector: valve triggered at fire_t, air reaches the item after the valve delay
                if it.fire_t is not None and not it.ejected and sim_t >= it.fire_t + VALVE_DELAY_MS / 1000:
                    it.ejected = True
                    blast_until = sim_t + 0.1

            on_belt = [it for it in on_belt if it.x < W and it.y < H]

            draw_scene(canvas, frame_no, counts, last_latency, sim_t, sim_t < blast_until, args.speed)
            for it in on_belt:
                draw_item(canvas, it)
            video.write(canvas)
            if not args.no_window:
                cv2.imshow("CIRCU360 belt simulation", canvas)
                # wait out the rest of this frame's screen time, so the playback speed is steady
                wait_ms = int((frame_wall_s - (time.perf_counter() - frame_start)) * 1000)
                if cv2.waitKey(max(wait_ms, 1)) & 0xFF in (ord("q"), 27):
                    break
            frame_no += 1

    video.release()
    cv2.destroyAllWindows()
    print("Decisions:", counts)
    print("Saved:", EVENTS_CSV, "and", VIDEO)


if __name__ == "__main__":
    main()
