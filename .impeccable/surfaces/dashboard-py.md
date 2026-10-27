---
version: 1
slug: "dashboard-py"
primary_target: "dashboard.py"
related_targets: ["ui"]
---

# Surface: CIRCU360 dashboard (Streamlit multipage)

Mode: Operate. A live demo to essay judges, driven by a presenter on the team laptop and projected or screen-shared. It has a plant overview (live control room) plus one detailed interactive page per process stage: 01 Feed, 02 AI sorting, 03 Belt & ejector, 04 Reactor & yields, 05 Energy balance.
Constraints: Streamlit + Plotly only. decide() and belt_timing() are imported from decision.py. Unsourced values are tagged ASSUMPTION or entered by the user. It must run offline, so fonts are served locally.
Memorable moment: the resin-code row on the overview, where each plastic is shown under the number moulded on its bottle and its route is printed in a box beneath it. Then the presenter clicks an item and walks it through decide().

## Direction contract
THESIS: The plant is organised by the resin codes judges already see on every bottle (1 PET, 2 HDPE, 3 PVC, 4 LDPE, 5 PP, plus non-plastic). Every class's route is printed beside it. This refuses the default of a generic KPI-card dashboard with donut charts.
OWN-WORLD: The ground is white packaging print with black ink (#141414) as the main rule and type colour, and 1–3px black rules instead of shadows or rounded cards. Each class keeps its fixed colour on an outlined ASTM-style resin triangle. Decisions are boxed, uppercase, 2px-bordered destination tags in the status colours. There is one face (Archivo, local), with tabular numerals. Square corners throughout.
STORY: A judge sees which plastics enter, where each one goes, and that PET/PVC never reaches the reactor (leak count 0, rule-of-three bound). They then see how one item is decided and how timing, yields and energy follow from it. They believe every figure, because each one is tagged as measured, case brief, sourced or assumption.
FIRST VIEWPORT: A sidebar with the stage nav, live status and the reject_t control. Main area: a title row with LIVE status, then a row of six resin columns (triangle, class, live count, decision mix bar, boxed destination). Below that, the monumental PET/PVC leak count on the left and the latest-items table with boxed decisions on the right, and a stage strip linking to each stage page.
FORM: Resin Code Labels, the top of my grounded list on re-roll 1 (chosen as IMPECCABLE’S PICK). seed:54a2c2b49a4c153d
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
