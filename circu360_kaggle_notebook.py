# CIRCU360 - Kaggle backup, in case local training fails.
# Runs the same pipeline as circu360_train_local.py, one step per cell, so nothing is duplicated.
#
# Setup on Kaggle:
#   1. New notebook -> Settings -> Accelerator: GPU T4, Internet: on
#   2. Add data -> "Drinking Waste Classification" (arkadiyhacks)
#   3. Upload decision.py and circu360_train_local.py as your own dataset named "circu360-code" and add it
#   4. Paste each "# %%" block below into its own cell and run them in order
#   5. At the end, download /kaggle/working/circu360_outputs.zip (a few MB) and unzip it into the repo,
#      so you get runs\circu360\... and data\split\test\... (sample images for belt_sim.py)
#
# Kaggle needs a phone-verified account to turn on GPU and Internet.

# %% Cell 1 - install
!pip install -q ultralytics onnx

# %% Cell 2 - load the pipeline and point it at Kaggle paths
import shutil, sys
from pathlib import Path

# Find our two code files and the dataset wherever Kaggle mounted them
INPUT = Path("/kaggle/input")
code = list(INPUT.rglob("decision.py")) + list(INPUT.rglob("circu360_train_local.py"))
raw = [d for d in INPUT.rglob("*") if d.is_dir() and "drinking-waste" in d.name.lower()]
print("Code files:", code)
print("Dataset folder:", raw[:1])
assert len(code) == 2, "Add your circu360-code dataset (decision.py + circu360_train_local.py) as Input"
assert raw, "Add the Drinking Waste Classification dataset as Input"

for f in code:
    shutil.copy(f, "/kaggle/working")
sys.path.insert(0, "/kaggle/working")

import circu360_train_local as T
T.RAW = raw[0]
T.DATA = Path("/kaggle/working/data")
T.RUNS = Path("/kaggle/working/runs")

# %% Cell 3 - build train/val/test folders (check the per-class counts it prints)
T.build_dataset()

# %% Cell 4 - train
best = T.train()

# %% Cell 5 - evaluate and run the threshold sweep
rows, out_dir, mean_ms = T.evaluate(best)
T.sweep(rows, out_dir)

# %% Cell 6 - belt timing and ONNX export
T.print_belt_timing(mean_ms)
T.export_onnx(best)

# %% Cell 7 - zip results + 30 test images per class, laid out like the repo
out = Path("/kaggle/working/outputs")
shutil.copytree(T.RUNS / T.RUN_NAME, out / "runs" / T.RUN_NAME, dirs_exist_ok=True)
for cls_dir in (T.DATA / "test").iterdir():
    dst = out / "data" / "split" / "test" / cls_dir.name
    dst.mkdir(parents=True, exist_ok=True)
    for img in sorted(cls_dir.iterdir())[:30]:
        shutil.copy(img, dst)
shutil.make_archive("/kaggle/working/circu360_outputs", "zip", out)
print("Download circu360_outputs.zip from the Output panel on the right")
