# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Primary:** judges of the International Student Essay Challenge (Case Study 2, Circular Economy & Urban Waste). They watch a **live demo presented by Group 2** on the team laptop, and the presenters drive the UI while they explain. Judges may ask to click or try something themselves.
- **Secondary:** the 6-person student team, who use the same UI to explore the reject threshold and to pull numbers and figures for the essay.

## Product Purpose
CIRCU360 is a prototype of a smart, safety-first circular plastic recovery micro-plant for mixed coastal plastic waste in Indonesia and the Philippines (2,000 kg/day). The UI has to make the **whole process** understandable and interactive in one demo: mixed feed → AI sorting (classifier probabilities → `decide()` → ACCEPT / REJECT / REMOVE / UNCERTAIN) → belt timing and ejector → polyolefin reactor feed → pyrolysis yields (liquid / gas / char) → energy balance.
Success means a judge leaves understanding that contaminants (PET/PVC) are kept out of the reactor by design, and that the numbers shown are measured or sourced, never invented.

## Positioning
Safety comes first in the sorting logic: PET/PVC is checked before anything else and can never be accepted. The headline metric is the **PET/PVC leak rate into the reactor**, which is shown ahead of accuracy. The reject threshold is presented as a process-safety parameter, because PVC releases about 58 wt% HCl.

## Operating Context
- The demo runs locally: `streamlit run dashboard.py` in one terminal and `python belt_sim.py` (OpenCV window, writes `events.csv`, records `demo.mp4` as a fallback) in a second.
- The laptop is a Windows 11 machine with an RTX 3050 4 GB and 8 GB RAM. The internet connection is unreliable, so the demo must not depend on it.
- Presentation format: there should be **one plant overview** where every stage updates live from the belt simulation, and each stage links to a **detailed interactive panel** (sliders, item drill-down) for explaining it step by step.

## Capabilities and Constraints
- **Stack:** Streamlit + Plotly, Python only, because it is easy for the student team to edit. This is the user's choice, made over a custom HTML/JS front end.
- `decide()` and the belt-timing constants live in `decision.py`. They are imported and never copied or changed.
- Data sources: `events.csv` (live belt), `runs/circu360/test_predictions.csv`, `threshold_sweep.csv`, `confusion_matrix_test.png`.
- Class names: HDPE, LDPE, PP, PET, PVC, OTHER. The current model knows only HDPE, PET and OTHER.
- Unsourced values (pyrolysis gas heating value, reactor heat demand, ejector valve delay of 15 ms, ejector distance of 0.40 m) are **labelled assumptions or editable inputs**, never hard-coded claims.
- Keep the code simple and readable for students, with no over-engineering.

## Evidence on Hand
- First training run (2026-10-28): 97.9% test accuracy. 0 of 226 PET leaked at every reject_t (rule-of-three upper bound ≈1.33%). Latency 6.5 ms mean / 11.3 ms p95 model-only, and 13.9 / 23.9 ms end-to-end, against the 35 ms spec.
- Case mass flow: 2,000 → 1,700 kg/day reactor feed → liquid 77.8%, gas 16.8%, char 5.4%. There is a ±9 wt% band on oil (Belden et al. 2023). HDPE oil heating value is 43.4–46.5 MJ/kg (Shah et al. 2023).
- Known limitations that must stay visible: the test images come from the same photo set as training, the dataset has no LDPE/PP/PVC, RGB cannot separate clear PET from PVC (NIR is the proposed upgrade), and one non-plastic item was accepted.
- There are no real plant photos, customers or field data. None should be fabricated.

## Product Principles
1. Safety before throughput: contaminant leaks are the first number shown.
2. Honest numbers: every figure is measured, sourced, or visibly marked as an assumption.
3. One story, end to end: every stage is reachable from the overview and explains how it connects to the next one.
4. Built for presenting: readable from across a room, and every interaction gives a clear result that a presenter can narrate.
5. Student-maintainable: plain Streamlit that any team member can change overnight.

## Accessibility & Inclusion
Decision states always carry a text label as well as a colour. The UI is projected or screen-shared to judges, so text and contrast must hold up at a distance.
