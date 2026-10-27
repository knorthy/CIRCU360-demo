"""CIRCU360 - train and evaluate the RGB sorting classifier in one run.

  1. Build train/val/test (70/15/15) folders from the raw Kaggle dataset
  2. Train YOLO11n-cls at 224 px
  3. Evaluate on the test set: report, confusion matrix, reject-threshold sweep
  4. Print belt timing and export the model to ONNX

Run:            python circu360_train_local.py
Re-evaluate:    python circu360_train_local.py --eval-only   (skips steps 1-2)
"""
import csv
import shutil
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay
from sklearn.model_selection import train_test_split

from decision import decide, belt_timing, CONTAMINANTS, POLYOLEFINS

# All paths are inside the repo; data\ and runs\ are git-ignored
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "drinking-waste-raw"   # unzip the Kaggle dataset here
DATA = ROOT / "data" / "split"               # train/val/test, rebuilt by this script
RUNS = ROOT / "runs"
RUN_NAME = "circu360"

# Folder-name keyword -> class. First match wins, so keep "hdpe" before "pet".
# Add your own photo folders here, e.g. ("ldpe", "LDPE"), ("pvc", "PVC"), ("polypropylene", "PP").
FOLDER_MAP = [
    ("hdpe", "HDPE"),
    ("pet", "PET"),
    ("alu", "OTHER"),
    ("can", "OTHER"),
    ("glass", "OTHER"),
]
SKIP_WORDS = ["yolo", "label"]   # duplicate YOLO-format copies of the same images
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SEED = 42


# ---------- 1. Dataset ----------
def class_for(path):
    """Class of an image from its folder names (nearest folder first), or None."""
    parts = [p.lower() for p in path.relative_to(RAW).parts[:-1]]
    if any(w in p for p in parts for w in SKIP_WORDS):
        return None
    for name in reversed(parts):
        for keyword, cls in FOLDER_MAP:
            if keyword in name:
                return cls
    return None


def build_dataset():
    if not RAW.exists():
        sys.exit(f"Raw dataset not found: {RAW}\n"
                 "Download https://www.kaggle.com/datasets/arkadiyhacks/drinking-waste-classification "
                 "and unzip it there.")

    files, labels, seen, unmatched = [], [], set(), set()
    for p in sorted(RAW.rglob("*")):
        if p.suffix.lower() not in IMG_EXT:
            continue
        cls = class_for(p)
        if cls is None:
            unmatched.add(str(p.parent.relative_to(RAW)))
            continue
        if p.name.lower() in seen:      # same image in two folders
            continue
        seen.add(p.name.lower())
        files.append(p)
        labels.append(cls)

    print("\nImages per class:")
    for cls in sorted(set(labels)):
        print(f"  {cls:6s} {labels.count(cls)}")
    if unmatched:
        print("Folders skipped (no FOLDER_MAP match or duplicate copy):", sorted(unmatched))
    if not files:
        sys.exit("No images found. Check the folder names above and fix FOLDER_MAP.")

    # 70 / 15 / 15, stratified so every split has the same class mix
    train_f, rest_f, train_y, rest_y = train_test_split(
        files, labels, test_size=0.30, stratify=labels, random_state=SEED)
    val_f, test_f, val_y, test_y = train_test_split(
        rest_f, rest_y, test_size=0.50, stratify=rest_y, random_state=SEED)

    if DATA.exists():
        shutil.rmtree(DATA)
    for split, fs, ys in [("train", train_f, train_y), ("val", val_f, val_y), ("test", test_f, test_y)]:
        for f, y in zip(fs, ys):
            dst = DATA / split / y / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
        print(f"  {split:5s} {len(fs)} images")


# ---------- 2. Training ----------
def train():
    import torch
    from ultralytics import YOLO

    if torch.cuda.is_available():
        device = 0
        print("\nTraining on GPU:", torch.cuda.get_device_name(0))
    else:
        device = "cpu"
        print("\nWARNING: no CUDA GPU found, training on CPU (slow). See CLAUDE.md setup commands.")

    model = YOLO("yolo11n-cls.pt")
    # time=1.5 caps training at 1.5 hours; it overrides epochs. Lower batch to 16 on CUDA out-of-memory.
    model.train(data=str(DATA), imgsz=224, epochs=100, batch=32, workers=2, time=1.5, patience=8,
                device=device, project=str(RUNS), name=RUN_NAME, exist_ok=True, seed=SEED)
    return Path(model.trainer.save_dir) / "weights" / "best.pt"


# ---------- 3. Evaluation ----------
def frac(items, value):
    return items.count(value) / len(items) if items else float("nan")


def evaluate(best):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ultralytics import YOLO

    model = YOLO(str(best))
    names = model.names          # {0: "HDPE", 1: "OTHER", 2: "PET", ...}
    out_dir = best.parent.parent

    rows = []
    for cls_dir in sorted((DATA / "test").iterdir()):
        imgs = [str(p) for p in sorted(cls_dir.iterdir())]
        for r in model.predict(imgs, imgsz=224, stream=True, verbose=False):
            probs = r.probs.data.cpu().numpy()       # full probability vector for decide()
            rows.append({
                "file": Path(r.path).name,
                "true": cls_dir.name,
                "pred": names[int(probs.argmax())],
                "P": {names[i]: float(p) for i, p in enumerate(probs)},
                "ms": r.speed["inference"],
            })

    y_true = [r["true"] for r in rows]
    y_pred = [r["pred"] for r in rows]
    labels = sorted(set(y_true) | set(y_pred))
    print("\nClassification report (test set, argmax):")
    print(classification_report(y_true, y_pred, labels=labels, digits=3, zero_division=0))

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    ConfusionMatrixDisplay(cm, display_labels=labels).plot(cmap="Blues")
    plt.title("CIRCU360 test set confusion matrix")
    plt.savefig(out_dir / "confusion_matrix_test.png", dpi=150, bbox_inches="tight")
    plt.close()

    # per-item results, useful for the essay and the dashboard
    with open(out_dir / "test_predictions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "true", "pred"] + [f"P_{n}" for n in names.values()] + ["decision", "latency_ms"])
        for r in rows:
            w.writerow([r["file"], r["true"], r["pred"]] + [round(r["P"][n], 4) for n in names.values()]
                       + [decide(r["P"]), round(r["ms"], 2)])

    lat = np.array([r["ms"] for r in rows])
    print(f"Inference latency: mean {lat.mean():.1f} ms, p95 {np.percentile(lat, 95):.1f} ms "
          f"(model only, batch 1, this machine)")
    print("Saved:", out_dir / "confusion_matrix_test.png", "and", out_dir / "test_predictions.csv")
    return rows, out_dir, float(lat.mean())


def sweep(rows, out_dir):
    """Reject-threshold sweep. Leak = a PET/PVC item ACCEPTed into the reactor."""
    contam = [r for r in rows if r["true"] in CONTAMINANTS]
    poly = [r for r in rows if r["true"] in POLYOLEFINS]

    results = []
    for t in np.arange(0.05, 0.951, 0.05):
        d_contam = [decide(r["P"], reject_t=t) for r in contam]
        d_poly = [decide(r["P"], reject_t=t) for r in poly]
        d_all = [decide(r["P"], reject_t=t) for r in rows]
        results.append({
            "reject_t": round(float(t), 2),
            "pet_leaked": d_contam.count("ACCEPT"),
            "pet_leak_rate": frac(d_contam, "ACCEPT"),
            "pet_recall": frac(d_contam, "REJECT"),
            "polyolefin_false_reject": frac(d_poly, "REJECT"),
            "uncertain_frac": frac(d_all, "UNCERTAIN"),
        })

    print(f"\nReject-threshold sweep ({len(contam)} PET/PVC and {len(poly)} polyolefin test items):")
    print(" reject_t  leaked  leak_rate  PET_recall  PO_false_reject  uncertain")
    for s in results:
        print(f"   {s['reject_t']:.2f}    {s['pet_leaked']:4d}    {s['pet_leak_rate']:.4f}     "
              f"{s['pet_recall']:.4f}        {s['polyolefin_false_reject']:.4f}        {s['uncertain_frac']:.4f}")
    if contam and any(s["pet_leaked"] == 0 for s in results):
        # "rule of three": with 0 leaks in n items, the 95% upper bound on the leak rate is about 3/n
        print(f"Note: 0 leaks in {len(contam)} items still means the true leak rate could be up to "
              f"~{min(1, 3 / len(contam)):.2%} (95% upper bound).")

    with open(out_dir / "threshold_sweep.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)
    print("Saved:", out_dir / "threshold_sweep.csv")


# ---------- 4. Belt timing and export ----------
def print_belt_timing(measured_ms):
    print("\nBelt timing (0.8 m/s, 60 fps; ejector distance and valve delay are ASSUMPTIONS):")
    for label, ms in [("spec 35 ms", None), (f"measured {measured_ms:.1f} ms", measured_ms)]:
        b = belt_timing() if ms is None else belt_timing(ms)
        print(f"  [{label}] {b['mm_per_frame']:.1f} mm/frame, {b['mm_during_inference']:.1f} mm during inference, "
              f"travel {b['travel_time_ms']:.0f} ms, fire ejector {b['fire_after_capture_ms']:.0f} ms after capture, "
              f"slack {b['slack_ms']:.0f} ms")


def export_onnx(best):
    from ultralytics import YOLO
    try:
        path = YOLO(str(best)).export(format="onnx", imgsz=224)
        print("\nONNX model:", path)
    except Exception as e:   # export is optional; best.pt still works
        print("\nONNX export failed (pip install onnx, then re-run with --eval-only):", e)


def main():
    if "--eval-only" in sys.argv:
        best = RUNS / RUN_NAME / "weights" / "best.pt"
        if not best.exists():
            sys.exit(f"No trained model at {best}. Run without --eval-only first.")
    else:
        build_dataset()
        best = train()
    rows, out_dir, mean_ms = evaluate(best)
    sweep(rows, out_dir)
    print_belt_timing(mean_ms)
    export_onnx(best)


if __name__ == "__main__":   # required on Windows because the data loader starts worker processes
    main()
