---
name: print-model
description: Prepare a model for printing on a Bambu Lab printer — from an STL, 3MF, STEP or MakerWorld project to a sliced file open in Bambu Studio with a print forecast. Use when the user wants to print something ("print this", "prepare it for printing", "what settings for this model", "get it onto the printer"), or wants to calibrate a new filament spool.
---

# Prepare a model for printing

You are the experienced printer at the wheel: you set everything in the project file yourself (`scripts/bbs_project.py`), say why in a sentence, and hand back a sliced file on which the user only presses **Print plate**. The user never hunts for fields in Studio.

Printer, presets and bed come from the user's Bambu Studio installation (`scripts/bbs_resolve.py`, `scripts/paths.py`). Calibrated filaments are their Studio user presets. The trusted start G-code of their printer is a snapshot in `~/.print-model/machine-gcode/` made once with `bbs_project.py snapshot` from any project Studio itself saved for that printer — Studio hides the real machine G-code from its preset files, and the fallback is a generic placeholder that prints at the wrong temperature and purges off the bed. If any of this is missing, name it and how to get it in one line.

## Before the model: two questions

Ask exactly two things, in one message, each with your recommendation:

1. **Which filament** — list the user's calibrated presets for the material they loaded. None calibrated for that material → say in two sentences what a generic preset costs (its flow, temperature and maximum speed are guesses: flow lines, overheating on thin tops, under-extrusion at speed), offer to calibrate first ([filament-calibration.md](references/filament-calibration.md)), and if they prefer to print now, take the closest system preset and label the forecast "uncalibrated filament".
2. **What matters more this time** — fast, good-looking, strong, or a mix ("quick prototype to check the fits", "display piece", "bracket under load"). This is a wish, not a preset: steps 3–4 translate it into settings for this particular model. Materials per part, deadlines, anything else — the user raises it when it matters.

**Calibrating a spool** is its own request: follow [filament-calibration.md](references/filament-calibration.md) — build the plates with `scripts/bbs_calib.py`, the user judges the prints and reports however they like, the result becomes a Studio user preset and appears in question 1 from then on.

## Steps

### 1. Get the model

| Source | Do |
| --- | --- |
| MakerWorld "Open in Bambu Studio", any foreign 3MF | `bbs_project.py retarget --machine … --process … --filament … --bed …`: moves the project onto the user's printer, filament and process, keeps the author's process tweaks (walls, supports), drops their filament and machine ones. Check the author's profile list for the user's printer first and take that one if it exists. Author advice on brims and supports comes from *their* printer: "brim not needed" from an X1/P1 owner (fixed bed) does not carry over to an A1-series bed-slinger. |
| STL | load as is; choose all three presets yourself |
| STEP (Fusion, Onshape) | `scripts/step2stl.py file.step outdir` — fine tolerance; Studio's own STEP import lays coarse triangles on fillets. One body = one STL. Bodies that touch without intersecting are separate parts. |
| Fusion, running | ask for an STL export, not STEP |

Done when every body is a mesh on disk and you know which bodies are separate parts.

### 2. Assess the model

- Fit: bounding box against `printable_area` and `printable_height` of the machine preset. Does not fit → ask about scale or splitting; never decide that silently.
- Mesh: round things look round (dense triangles on fillets). A big triangle count is fine; Studio's "simplify model" warning is ignored.
- Trouble spots: overhangs past ~45°, bridges, thin standing features, a large flat sole, inner floors or shelves inside walls ([symptoms-and-fixes.md](references/symptoms-and-fixes.md) §1: a floor line, best removed by a chamfer in the design), narrow places and small bars (gap fill), shallow slopes (stair-steps — `scripts/mesh_slopes.py`, check 15), hollow bottoms or tall narrow parts (brim at once, check 10), a rounded edge that meets the plate tangentially (a ragged band that none of the checks catch — [model-playbook.md](references/model-playbook.md) §2.11).
- Several parts: an orientation per part and one plate per part unless they are small. `print_sequence = by object` only when every part is lower than the machine's `extruder_clearance_height_to_rod`. Bambu printers have no print queue; plates are handed over one at a time.
- Look the model type up in [model-playbook.md](references/model-playbook.md) — boxes, rounded shells with lips, grilles, bezels, legs and pins, organic figures, whistles, snap-fits, assemblies, MakerWorld projects — and start from its first choices.

Done when every part has an orientation with its reason written down and the trouble spots are listed.

### 3. Choose the three presets

Machine: the user's printer and nozzle. Filament: their calibrated preset. Process: a system preset of that printer family, picked by the wish:

| Wish | First choice |
| --- | --- |
| fast, prototype, fit check | `0.20mm Standard`, 2 walls, 10 % infill; supports, brims and blockers still wherever the geometry needs them. Measured on a six-plate assembly: 36.5 h → 23.5 h; `0.24mm Draft` gave only −6 % more with worse overhangs — not worth it. |
| good-looking | `0.12mm Fine` for organic surfaces (stair-steps), `0.16mm High Quality` for flat vertical walls (outer wall 60 mm/s against ripple); 3 walls; seams into corners or to the back; thinner layers only on shallow bands via a height-range modifier (`bbs_project.py ranges`). |
| strong | the `Strength` preset of the family, or Standard with more walls and denser gyroid — strength comes from walls, not infill; a 4 mm wall with 3 loops is nearly solid already. |

Layer height is a first pick, not a final one: the forecast (step 5) may send you back here once — thin tops overheating want a thicker layer or a second object as a cooler; stair-steps want a thinner layer on that band only.

Done when `scripts/bbs_current.py project.3mf` shows the three intended presets and exactly the differences you meant.

### 4. Apply the quality package

Always: `resolution=0.004 slice_closing_radius=0.01` (arc fitting stays on), `precise_outer_wall=1`, the classic wall generator with the preset's wall count, `reduce_crossing_wall=1 max_travel_detour_distance=300`, `no_slow_down_for_cooling_on_outwalls=1`, top pattern by shape (`concentric` for round tops, `monotonic` otherwise). What each costs and why: [slicing-quality.md](references/slicing-quality.md). Then by geometry and symptom: [symptoms-and-fixes.md](references/symptoms-and-fixes.md).

Set values as a project variant (`bbs_project.py variant --set key=value`), never as clicking instructions. Trap: when Studio loads a 3MF it resets every key not listed in `different_settings_to_system` to the system preset; `variant` maintains that list, a hand-edited project silently loses its changes.

### 5. Check and forecast

1. `bbs_current.py` — presets right, differences exactly as intended.
2. Slice with the Studio CLI: `scripts/slice.py <out dir> project.3mf` — no errors; note time, layers, grams.
3. Forecast — all 16 checks of [forecast.md](references/forecast.md): `scripts/mesh_slopes.py` (15, on the mesh, before slicing), `scripts/gcode_forecast.py <cli dir>` (1, 2, 5, 7, 10, 11, 12 and start-G-code sanity), `scripts/gcode_features.py plate_1.gcode` (3, 4, 6, 8, 13, 14), `scripts/gcode_airtravel.py` (16, only for functional cavities). Every hit gets one of three severity words — **stop / noticeable / minor** — a place, a cause and what fixes it.
4. Levers: a *noticeable* item that has a settings lever is not left as advice — build the variant, slice it, compare with `scripts/gcode_compare.py a b`, keep it when time grew by ≤ 15 % and no other check got worse; otherwise offer both with the difference. One lever per variant, so the comparison means something.

Done when all 16 checks are marked and the forecast block is written — "no stop factors" is also a forecast.

### 6. Hand over

1. `bbs_project.py gcode3mf <cli export>.gcode.3mf <name>.gcode.3mf` — strips the geometry; Studio opens a mesh-less file as *sliced* (Preview, **Print plate** active) instead of as a project.
2. Open it in a Studio that is **already running** (macOS: `open -a BambuStudio file.gcode.3mf`; elsewhere: open the file from Studio or double-click it). A file handed to a cold-starting Studio can hang it without a window. If a project is open, Studio asks "Open as project?" (yes) and "save changes?" (no).
3. Tell the user: the forecast block, then "in Studio: `<name>` → Print plate → Send", and which filament to have loaded. On a *stop* item give the choices instead of the button.

Several plates: one file each, handed over in order as the bed becomes free.

### 7. Record

The user keeps their own log. Offer the one thing that grows this skill: after the print, forecast vs. reality — which prediction held, which missed, by how much. A missed threshold is a pull request to `references/forecast.md` with the numbers; a lesson that outlives the model belongs in `references/model-playbook.md`.

## References

- [model-playbook.md](references/model-playbook.md) — model type → first choices, with measured evidence.
- [symptoms-and-fixes.md](references/symptoms-and-fixes.md) — symptom → cause → Bambu Studio setting.
- [forecast.md](references/forecast.md) — the 16 checks, thresholds, severity words, levers, output format.
- [slicing-quality.md](references/slicing-quality.md) — resolution, arc fitting, mesh quality, measured costs.
- [filament-calibration.md](references/filament-calibration.md) — why calibrate, what "calibrated" means, the plates, turning results into a Studio preset.
