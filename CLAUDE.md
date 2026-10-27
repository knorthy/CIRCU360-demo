# CIRCU360 prototype — context for Claude

## What this is
A software prototype for a student essay, **"CIRCU360: A Smart, Safety-First Circular Plastic Recovery Micro-Plant"**, written for the International Student Essay Challenge, Case Study 2 (Circular Economy & Urban Waste). The authors are Group 2 from Cavite State University and Universitas Wahid Hasyim, and it is due November 2026. The essay draft is `../Case Study 2 Essay Draft — Structure.md`. Its research reports are in `../reports/`, and the dataset research for this prototype is `../reports/CIRCU360 prototype datasets.md`. These essay files are not on every team laptop.

The plant sorts mixed coastal plastic waste in Indonesia and the Philippines at 2,000 kg/day. It sends only polyolefins (HDPE, LDPE, PP) to a containerized screw pyrolysis reactor at about 430 °C. PET goes to mechanical recyclers, and PVC goes to specialist disposal because it releases HCl. The prototype has to **demonstrate the AI sorting stage, the belt timing, and a monitoring dashboard**. It does not need to be production-grade. The goal is a working demo plus numbers and figures for the essay, built overnight by a team of 6.

## Machine
- Windows 11 laptop with an Intel i5-11400H, 8 GB RAM, and an **NVIDIA RTX 3050 Laptop GPU (4 GB)**.
- Python 3.13.
- The repo is at `C:\Users\ricoe\SOFTENG\CIRCU360-demo`, which is not under OneDrive.
- The internet connection drops often. Large downloads need resume or retry: use pip `--retries 10 --resume-retries 10`, or `curl -C -` in a loop.

## Repository layout
Everything lives inside this repo. Large files are git-ignored (see `.gitignore`).
```
CIRCU360-demo\
  decision.py                  decide() + belt-timing constants, shared by every script
  circu360_train_local.py      main pipeline: dataset -> train -> evaluate -> sweep -> ONNX
  circu360_kaggle_notebook.py  Kaggle backup; imports circu360_train_local.py, one step per cell
  requirements.txt
  data\                        (git-ignored)
    drinking-waste-raw\        unzip the Kaggle dataset here
    split\                     train/val/test, rebuilt by the script on every full run
  runs\circu360\               (git-ignored) weights\best.pt, best.onnx, confusion_matrix_test.png,
                               test_predictions.csv, threshold_sweep.csv
```
Paths in the scripts are relative to the repo (`ROOT = Path(__file__).resolve().parent`), so the code works on every teammate's laptop.

## Setup
```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
```
- Install the CUDA torch build **first**, otherwise pip installs the CPU-only build.
- Check it with: `python -c "import torch; print(torch.cuda.is_available())"`.
- On this laptop, torch 2.9.1+cu126 / torchvision 0.24.1+cu126 **are installed and see the RTX 3050**. They were installed from wheels downloaded with resumable curl to `C:\circu360\wheels`, because pip downloads kept failing. That folder only holds installers and can be deleted.
- Because the connection is bad, training on Kaggle (`circu360_kaggle_notebook.py`) is the main alternative: the dataset stays on Kaggle and only a small `circu360_outputs.zip` comes back.

## Current state
- `circu360_train_local.py` has been smoke-tested on fake images (dataset build, decide(), sweep). It has **not been trained yet**. In one run it:
  1. Builds a train/val/test (70/15/15, stratified, seed 42) dataset from `data\drinking-waste-raw` into `data\split`.
  2. Trains an Ultralytics **YOLO11n-cls** classifier at 224 px (batch 32, workers 2, `time=1.5` h cap, patience 8), with outputs in `runs\circu360\`.
  3. Evaluates on the test set: classification report, confusion matrix, per-item CSV, and a reject-threshold sweep (PET leak count and rate, PET recall, polyolefin false-reject rate, uncertain fraction). When a threshold shows 0 leaks, it prints the rule-of-three upper bound (≈3/n).
  4. Prints belt timing, both for the 35 ms spec and for the measured latency, and exports the model to ONNX.
- `--eval-only` skips steps 1–2 and re-runs steps 3–4 on the existing `best.pt`.
- If CUDA runs out of memory, lower batch to 16.

## Dataset
- **Drinking Waste Classification** (Kaggle, arkadiyhacks): https://www.kaggle.com/datasets/arkadiyhacks/drinking-waste-classification
- About 4,800 images in 4 categories: aluminium cans, glass bottles, PET bottles, and HDPE milk bottles. Licence CC0.
- The script maps folders by name keyword (`FOLDER_MAP`, first match wins): hdpe→HDPE, pet→PET, alu/can/glass→OTHER.
  - The real folder names have **not been checked yet**. The script prints per-class counts and the folders it skipped. If a class shows 0 images, fix `FOLDER_MAP`.
  - Folders whose names contain "yolo" or "label" are skipped as duplicate copies, and images are de-duplicated by filename.
- **Limitation:** the dataset has only PET and HDPE as plastics, with no LDPE, PP or PVC. The plan is for the team to photograph about 100–200 images each of PP, LDPE film/sachets and PVC (pipe offcuts, blister packs). Each class goes in its own folder under `data\drinking-waste-raw`, and `FOLDER_MAP` gets a new entry. The rest of the code already handles those class names.
- RGB alone cannot reliably tell clear PET from clear PVC, or HDPE from PP. The essay says so and proposes NIR as the upgrade. Open spectral datasets for an optional NIR demo: FTIR-Plastics https://zenodo.org/records/11176740 and the VIS–NIR–SWIR library https://zenodo.org/records/20180898.

## Decision rule (from essay Table 3) — keep this logic exact
It lives in `decision.py`. Every script imports it from there and never copies it.
```python
def decide(P, reject_t=0.30, accept_t=0.90, other_t=0.90):
    if P.get("PET", 0) + P.get("PVC", 0) > reject_t:  return "REJECT"     # checked FIRST: PET/PVC can never be accepted
    if P.get("HDPE", 0) + P.get("LDPE", 0) + P.get("PP", 0) >= accept_t:  return "ACCEPT"
    if P.get("OTHER", 0) >= other_t:  return "REMOVE"   # non-plastic stream (added for this dataset)
    return "UNCERTAIN"                                  # manual inspection / float-sink test
```
- "Polyolefin ≥ 90%" means the **sum** of P(HDPE)+P(LDPE)+P(PP).
- A **classifier** is used rather than a detector because the rule needs the full probability vector (`result.probs.data`).
- The headline metric is the **PET/PVC leak rate** (contaminant accepted into the reactor), reported ahead of accuracy. The reject threshold is treated as a process-safety parameter, because PVC releases about 58 wt% of its mass as HCl.

## Case numbers (from the brief / essay)
- Feed: 2,000 kg/day = HDPE 35% (700) + LDPE 30% (600) + PP 20% (400) + PET 10% (200) + dirt/non-plastic 5% (100).
- Reactor feed is 1,700 kg/day, running continuously at about 71 kg/h. Sorting runs at 150 kg/h, about 13.3 h/day in two shifts.
- Yields: liquid 77.8% (1,322.6 kg/day), gas 16.8% (285.6 kg/day), char 5.4% (91.8 kg/day).
  - The 5.4% char is high for clean polyolefins (literature 0.4–2%). Treat it as including wax, additives and dirt.
- Vision spec: 12,500-image, 6-class RGB model; belt 0.8 m/s; 60 fps camera; 35 ms inference.
  - That gives 13.3 mm of belt travel per frame and 28 mm during inference.
  - The ejector is assumed 0.40 m downstream, so travel time is 500 ms.
  - Fire the ejector at capture_time + D/v − t_valve, with t_valve assumed to be 15 ms. This value is **not sourced**; label it as an assumption.
  - These constants live in `decision.py` (`belt_timing()`). The firing time is 485 ms after capture, and the slack after a 35 ms inference is 450 ms.
- Energy: pyrolysis gas heating value and reactor demand are **not verified**. Make them **editable inputs** in the dashboard, not hard-coded claims. HDPE oil is 43.4–46.5 MJ/kg (Shah et al. 2023).

## Still to build (next steps)
1. Install CUDA torch, download the dataset into `data\drinking-waste-raw`, and run `python circu360_train_local.py`. Fix `FOLDER_MAP` or the batch size if needed.
2. Use `runs\circu360\threshold_sweep.csv` to choose `reject_t`.
3. **Belt simulation** (`belt_sim.py`, OpenCV):
   - A canvas scrolls 13 px/frame (1 px = 1 mm) at 60 fps, with test images from `data\split\test` placed on it.
   - Each item is classified with `runs\circu360\weights\best.pt` or `best.onnx` (onnxruntime) as it crosses a trigger line.
   - A virtual ejector fires 400 px downstream on REJECT.
   - It shows ACCEPT/REJECT/REMOVE/UNCERTAIN colours and logs each item to `events.csv` (timestamp, true class, probabilities, decision, latency).
   - It records `demo.mp4` as a fallback in case the live demo fails.
4. **Dashboard** (`dashboard.py`, Streamlit + Plotly):
   - Live decision counters and per-class pie from `events.csv`.
   - Latency histogram.
   - Sankey diagram of the 2,000 → 1,700 → liquid/gas/char flow, with a ±9 wt% band on oil (Belden et al. 2023 model error).
   - Editable energy-balance inputs.
   - Run it locally. The free host is Streamlit Community Cloud; Hugging Face Gradio/Docker Spaces now need a paid plan.

## Style
- Keep code simple and readable for students, with short comments and no over-engineering.
- Use Windows-friendly paths built with `pathlib` and relative to the repo root. Don't hard-code absolute paths.
- Don't invent numbers. Anything assumed should be labelled as an assumption so it can be stated honestly in the essay.
