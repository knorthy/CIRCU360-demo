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

## Results of the first training run (2026-10-28, RTX 3050)
- Dataset: PET 1,508 / HDPE 1,028 / OTHER 2,284 (`Images_of_Waste\rawimgs\...`; the `YOLO_imgs` copy is skipped). Split: 3,374 train / 723 val / 723 test.
- Early stop after 15 epochs (best at epoch 7), 5 min of training. Test accuracy 97.9% (argmax); recall HDPE 99.4%, PET 98.7%, OTHER 96.8%.
- **PET leak: 0 of 226 at every reject_t from 0.05 to 0.95.** By the rule of three, the 95% upper bound is ≈1.33%. At reject_t=0.30: PET recall 99.6% (the one remaining PET item went to UNCERTAIN, not the reactor), polyolefin false-reject 1.95%, uncertain 6.0%.
- One OTHER item (a can or glass bottle) was ACCEPTed: a non-plastic leak into the reactor feed.
- Latency on this GPU: mean 6.5 ms, p95 11.3 ms (model only), against the 35 ms spec.
- Caveat for the essay: the test images come from the same photo set as the training images (clean, single objects), so real coastal waste will score lower.
- Outputs: `runs\circu360\` (best.pt, best.onnx, confusion_matrix_test.png, test_predictions.csv, threshold_sweep.csv); logs: `train_log.txt`, `eval_log.txt`.

## Pipeline
- In one run, `circu360_train_local.py`:
  1. Builds a train/val/test (70/15/15, stratified, seed 42) dataset from `data\drinking-waste-raw` into `data\split`.
  2. Trains an Ultralytics **YOLO11n-cls** classifier at 224 px (batch 32, workers 2, `time=1.5` h cap, patience 8), with outputs in `runs\circu360\`.
  3. Evaluates on the test set: classification report, confusion matrix, per-item CSV, and a reject-threshold sweep (PET leak count and rate, PET recall, polyolefin false-reject rate, uncertain fraction). When a threshold shows 0 leaks, it prints the rule-of-three upper bound (≈3/n).
  4. Prints belt timing, both for the 35 ms spec and for the measured latency, and exports the model to ONNX.
- `--eval-only` skips steps 1–2 and re-runs steps 3–4 on the existing `best.pt`.
- If CUDA runs out of memory, lower batch to 16.
- Pass a **folder** to `model.predict()`, not a list of paths. A list is loaded into RAM all at once and crashed with MemoryError on 8 GB.
- During ONNX export, Ultralytics auto-installed `onnx 1.19.1` and `onnxruntime-gpu`. onnxruntime now offers the CUDA and TensorRT providers.

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
1. ~~Train~~ done. Retrain once the team's own PP/LDPE/PVC photos are added.
2. Choose `reject_t`: every value gives 0 leaks, and between 0.15 and 0.30 the results differ by only one item, so they can't be told apart with this test set. Keep the essay's 0.30 unless the team decides otherwise.
3. ~~Belt simulation~~ and 4. ~~Dashboard~~: **built and tested** (see "Demo" below). Original spec, kept for reference:
   **Belt simulation** (`belt_sim.py`, OpenCV):
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

## Demo
- Terminal 1: `streamlit run dashboard.py` (opens http://localhost:8501).
- Terminal 2: `python belt_sim.py`. Options: `--speed 0.25` (default, 4× slow motion; 1 = real time), `--items 80`, `--reject-t 0.30`, `--onnx`, `--no-window` (record only), `--seed 1`.
- `--speed` changes playback only, meaning the window and the `demo.mp4` fps. The simulated belt stays at 0.8 m/s, so the timings and `events.csv` are unchanged.
- `belt_sim.py`:
  - Positions are floats moving 13.3 px/frame, so the belt runs at exactly 0.8 m/s.
  - Simulated time is frame/60, so `demo.mp4` always plays at true belt speed, even if the live window is slower.
  - Items are classified at the camera line, and the ejector fires at capture + 485 ms (`belt_timing()`).
  - The decision colours are the same as on the dashboard.
- Tested: 80 items, decisions **identical (80/80)** to `test_predictions.csv`. End-to-end latency (pre-processing + model + post-processing) is 13.9 ms mean, 23.9 ms p95.
- **Feed the camera the original image.** Pre-shrinking it (256 px, INTER_AREA) shifted borderline probabilities by up to 0.2 and flipped 3 of 20 decisions. That's a robustness point for the essay: items near the thresholds are sensitive to image scale.
- `dashboard.py` is a multipage Streamlit app (redesigned with the Impeccable skill, 2026-10-28). It only sets up navigation and the sidebar `reject_t` slider (`st.session_state.reject_t`, shared by all pages). The pages are in `ui/`:
  - `overview.py` (live, refreshes every 2 s): a row of resin-code columns (1 PET, 2 HDPE, 3 PVC, 4 LDPE, 5 PP, OTHER) with live counts, decision mix and route, the PET/PVC leak count, the latest items, and links to each stage.
  - `feed.py`: the case feed (editable kg/day), composition, and where each class must go and why.
  - `sorting.py`: walk one test image through `decide()` (the rule that fired is boxed), "try your own probabilities" sliders, and the threshold sweep, metrics and confusion matrix.
  - `belt.py`: the camera→ejector timeline from `belt_timing()` (spec vs measured latency) and the latency histogram.
  - `reactor.py`: the Sankey (editable reactor feed), and yields with the oil ±9 pp band.
  - `energy.py`: energy-balance inputs. The gas heating value and reactor demand start empty, and nothing is computed until a sourced value is entered.
- `ui/plant3d.py` + `ui/plant3d.html` (3D plant page): a three.js model of the plant (three.js 0.160.0, served locally from `static/three/`). Click any part or its label to open a panel with that part's numbers. Items on the 3D belt replay the last run, or follow live decisions while `belt_sim.py` runs. **Start belt / Stop belt** run `belt_sim.py --no-window` in the background (log: `belt_sim_log.txt`). Clicking **CAM** shows the sim's frames live: `belt_sim.py` writes `static/live/belt.jpg` + `belt.json` every 4th frame (git-ignored; `--no-web` turns it off). Loading the model takes about 20 s before the first item appears.
- `ui/common.py` holds the colours, case numbers, loaders and HTML helpers. Every figure carries a basis tag: MEASURED / CASE BRIEF / SOURCED / ASSUMPTION.
- The theme is in `.streamlit/config.toml`: white with black ink, square corners, and the Archivo font served from `static/fonts` (OFL), so it works offline. The design context is in `PRODUCT.md` and `.impeccable/surfaces/dashboard-py.md`.
- `st.html` strips inline `<svg>`, so the resin badges are data-URI `<img>`s. Charts go through `chart()` in `ui/common.py` (white background, automargin).
- Colours: classes use fixed categorical colours (HDPE blue, PET orange, OTHER aqua). Decisions use status colours (`DECISION_COLORS`, kept in sync with `belt_sim.py`), and text uses the darker `DECISION_INK`, always with a text label.
- `demo.mp4` is written as mp4v, which browsers can't play, so the dashboard doesn't embed it.

## Style
- Keep code simple and readable for students, with short comments and no over-engineering.
- Use Windows-friendly paths built with `pathlib` and relative to the repo root. Don't hard-code absolute paths.
- Don't invent numbers. Anything assumed should be labelled as an assumption so it can be stated honestly in the essay.
