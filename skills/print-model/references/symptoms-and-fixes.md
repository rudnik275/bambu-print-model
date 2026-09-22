# Clean prints: symptom → cause → what to change

Distilled from five Factorian Designs videos (2024–2026): "Fix ALL Shrink & Wall Lines", "The Fatal Error No One Talks About", "Crazy 3D Slicer Hacks", "5 Tricks For Incredibly Clean Prints", "Cut Your 3D Printing Time In Half". Setting names are Bambu Studio's; "(Bambu default: X)" in parentheses is the value in Bambu's stock `0.20mm Standard @BBL A1M` process, and where the value lives in the filament preset, "(typical Bambu PLA preset: X)".

The author's general principle: **make the print easy for the machine** — long continuous lines, even flow, no tiny extrusions, no unnecessary retractions, no wall crossings. Most "mysterious" defects come from there.

## 1. Floor line / "box line"

**Symptom.** A horizontal band on the outer wall exactly at the height of an internal floor, shelf, or lid. Boxes, vases, trays. Below and above it the wall is clean.

**Cause.** Not layer time but **mass**: a solid floor layer is a lot of material; as it cools it shrinks harder and pulls the walls bonded to it inward. Equalising layer times does not cure it — it makes it worse (the author checked at 150 s/layer). Hence three levers: decouple, control shrinkage, hide.

**Decouple the walls from the massive layer** (the strongest lever):
- In the design: a **chamfer on every floor edge** (the bigger the better), a thickened wall right above the floor, a micro-gap at the height of the top layer, a floor/shelf of smaller area, a sloped or rounded base instead of a flat one. The author gives all his boxes a sloped/rounded base — and the "line" vanishes even on stock profiles.
- In the slicer: `wall_sequence = inner-outer-inner` (Bambu default: `inner/outer`) — the outer wall prints without a neighbour, comes out more even and cools symmetrically; with 2 walls Studio switches to outer/inner and the seam becomes more visible. **Only for closed walls without openings**: on a box with a window it worsened the lintel over the window and did not touch the floor line — reverted to `inner/outer`.
- A related case — an **opening in a wall** (window, slot): on the layers where it starts and ends the contour breaks apart / rejoins → a bump around the whole perimeter, stronger in the corners. Settings do not fix it (tested in two settings variants); a chamfer or fillet on the opening's edges in the design does — the transition is spread over several layers. If you would rather not change the wall order — `precise_outer_wall = 1` (Bambu default: 0). `infill_wall_overlap` 15 % → 0 or negative (Bambu default: 15 %) — decouples, but noticeably weakens the part. `ensure_vertical_shell_thickness` off (Bambu default: enabled) — otherwise the slicer "stitches" the walls back on by itself. More walls can make it **worse** — they reconnect to the floor.

**Shrinkage:** fast cooling — for PLA the author runs 100 % fan everywhere (typical Bambu PLA preset: 60–80 %), open chamber, cool room. **The same speed on every line** (everything = outer wall speed): even flow → even shrinkage; for that, turn off the overhang slowdown (`enable_overhang_speed`, Bambu default: 1) and the slowdown for layer cooling (`slow_down_for_layer_cooling`, typical Bambu PLA preset: 1). Material: CF-PLA and others with lower shrinkage — a weaker line.

**Hide:** fuzzy skin; relief on the wall with sloped/curved sections at floor height; move the floor to the very bottom (solid layers at the bed give less of a line) + a chamfer and fillet on the top edge — the eye reads the distortion as part of the shape.

Settings alone do not remove the line completely; a chamfer in the design + settings — down to zero.

## 2. Tiny extrusions — "the fatal error"

**Symptom.** A locally dirty, weak patch while the rest is fine: a ragged first line of the next layer, the part breaking at the same layer every time, stringing near the seam. Especially on white PLA, PETG, TPU.

**Cause.** Gap fill made of dots and scraps at the end of a layer: retract–extrude–retract, one droplet at a time — the nozzle loses pressure and the next line comes out empty. Visible only in the preview (white gap-fill dots, pink retraction dots).

**Fix:**
- `wall_generator = arachne` (Bambu default: classic) — variable width fills the gap with a single line. Slices longer, occasionally misbehaves.
- Wall width **0.5** + Arachne `min_feature_size` / minimum wall length ≈ 2 mm → the micro-squiggles disappear. Play with `min_bead_width`, `wall_transition_filter_deviation`.
- In classic: the model is designed for a whole number of lines (3 × 0.4 = 1.2 mm). **Scaled the part — recompute the line width**, otherwise thin gap fill appears; 0.48 instead of 0.42 often solves it.
- `filter_out_gap_fill` (Bambu default: 0) — sometimes helps, sometimes does nothing.
- Ironing: the ironing flow is tiny → the nozzle runs empty; raise `ironing_speed` and `ironing_flow` a little (Bambu default: 30 / 10 %) to double the flow; a tail of ironing dots breaks the next layer.
- Top / bottom / internal solid infill patterns — **concentric** for long continuous lines (mandatory for TPU; Bambu default: monotonicline / monotonic / zig-zag).
- Extra retractions (pink dots) go away with a small shift of the first-layer and wall widths — the path becomes continuous.
- Workaround: "smooth timelapse" — after every layer the printer purges the nozzle on the tower, so the next layer starts with a full nozzle.

## 3. Wall crossing → stringing and dirty inner walls

**`reduce_crossing_wall = 1`, `max_travel_detour_distance` 200–300 mm** (Bambu default: 0 / 0). The nozzle stops dragging a blob through the outer wall. The author enables it **on every print**; stringing on his tray disappeared completely. Plus the line-width rule: **±0.5 × nozzle diameter — 0.2…0.6 mm for a 0.4 nozzle**; in other slicers, reducing the width forces the path to go around.

## 4. Wall order

- `outer/inner` — cleaner outer wall and more accurate dimensions (the outer wall is not squashed by the inner one), but worse overhangs (no neighbour to stick to). For precise parts without steep overhangs.
- `inner-outer-inner` — the compromise for the floor line (see §1).
- `inner/outer` (Bambu default) — the default, best on overhangs.

## 5. Gloss patches: glossy and matte on one part

**Cause.** On small layers (the top of a vase, narrow sections) the slicer slows down for cooling → slower flow → hotter plastic → gloss; fast sections come out matte. Plus the overhang slowdown at the bottom.

**Fix.** `slow_down_for_layer_cooling = 0` (typical Bambu PLA preset: 1 — 6 s / min 20 mm/s); raise the overhang speed slightly and lower the outer wall speed — an even surface. Careful: too fast at the top → overheating and scrap. **`no_slow_down_for_cooling_on_outwalls = 1`** (Bambu default: 0) — the layer-time stretch is taken out of the
internal features instead of the outer wall. This key **does exist in Bambu Studio** (an earlier version of this file
said it was Orca-only); measured on a 600-layer PETG shell with the slowdown forced on, outer wall 153 → 181 mm/s and
its layer-to-layer spread 31 → 20 mm/s, while inner wall and sparse infill absorbed the stretch (165 → 152, 166 → 153);
total time 6:53 → 6:51. It is in the always-package.

**The fan is the other half of this, and it is per layer, not per feature.** Bambu interpolates fan speed between
`fan_min_speed` at `fan_cooling_layer_time` and `fan_max_speed` at `slow_down_layer_time`; a geometry change that
alters layer time therefore changes the sheen of the outer wall, and no setting gives the outer wall its own cooling
(only overhangs and bridges have their own `overhang_fan_speed`). Measured on a PETG shell whose layer time jumped
14.9 s → 58–83 s where the front lips begin: fan 79 % → 40 %, a visible gloss band exactly between those heights, and
**35 distinct fan values over the print, 20 of them on the outer wall alone** — the band the eye catches is only the
sharpest step of a continuous drift. Setting `fan_min_speed = fan_max_speed` makes it a constant (5 values left, all
from the start G-code and the overhang override) at no cost in time or plastic (6:34 vs 6:33, 199.3 g both). Pick the
value the bulk of the part already prints at. What is sacrificed on PETG: the thick slow layers now get roughly double
the cooling they had, so layer adhesion in that band is weaker and a large flat part is slightly more prone to lifting
— judge it against how much of the part is in that band and whether it carries load.

## 6. Patterns and sequence

- Top: usually **monotonic** is smoother; for round parts — **concentric**, sometimes gives a beautiful pattern. Ten seconds to choose — a big difference.
- Several objects: **`print_sequence = by object`** (Bambu default: by layer) — zero travels between parts; place them close; watch the head clearance. One object at a time — the best quality.

## 7. Modifiers — material only where it is needed

A cylinder / sphere / height range as a modifier with its own settings. The last one in the list takes priority. A bridging bug is cured by shifting/scaling the modifier.
- **Bottom**: a 2 mm modifier → 3 bottom layers; globally 1 layer and 0 % infill → a "shell".
- **Pillar** under a floating internal floor (egg cup, tray with a double floor): a cylinder with 30 % infill. Better than lightning infill — that one wobbles and ~1 in 30 collapses.
- **Top**: a thin modifier → 3 top layers, 40 % infill with a pattern that suits a top (support cubic), top line width ~0.35, lower top-surface speed.
- `ensure_vertical_shell_thickness` off and `detect_narrow_internal_solid_infill` off (Bambu default: both on) — otherwise the slicer adds infill wherever it is thin.
- The author's result: −30 % time and −31 % plastic with no loss of strength. Infill gives almost no strength — walls do.

## 8. Line width — a tool, not a constant

- Range 0.2–0.6 for a 0.4 nozzle. **0.5–0.6 on walls with no quality loss** for models without fine detail — and one wall fewer at the same thickness → noticeably faster. Width 0.5 also suppresses tiny extrusions (§2).
- **Top surface — slightly narrower** (~0.35–0.4): cleaner. Tweak until the dot extrusions in the preview turn into little triangles.
- First layer: a small width shift changes the traversal order (outside-in) — a more reliable start.
- A narrower line "for quality" — no: wall quality comes from the layer height (0.12 instead of 0.20), not the line.

## 9. First layer

- `elefant_foot_compensation` +0.1 (Bambu default: 0) — removes the sharp edge that reads as a defect.
- A little more squish (Z-offset in the start G-code) — more reliable; less — easier self-release (§11).
- First-layer speed 30 (Bambu default: 50) — "reliability over speed".
- No brim needed for large flat footprints without sharp corners (Bambu default: `auto_brim`).
- Do not start the print with the outer wall: a 0–0.2 mm modifier with a higher wall count hides start defects.

## 10. Time

- `z_hop` off (Bambu default: 0.4 Auto Lift) — per the author: gives no quality, adds stringing and time, wears the Z axis. Debatable for Bambu (on by default); verify by printing.
- Shell + modifiers (§7), width 0.5 and −1 wall (§8), no brim — the author's **−50 % time, −30 % cost**.
- Vase mode — temptingly fast, but looks cheap; not for a thing you want to show off.
- Save the result as a 3MF project.

## 11. Bed: adhesion and release

From a video about automating the A1 mini — the only thing in it about quality.

- A part on the stock PEI **releases itself as it cools**: the plastic contracts ~6× more than the sheet, and the bond breaks at a bed temperature of ≈ 22 °C. Do not pry it off hot — wait, it comes off without marks and without risk to the sheet.
- Adhesion is adjustable: squish (Z-offset in the start G-code, `G29.1`), bed/nozzle temperature on the first layer, first-layer line width. More — holds tighter; less — releases easier; do not overdo it in either direction.
- Wash the bed **with a sponge and dish soap, not IPA**, then clean water (Bambu advises the same). Adhesion only drops from greasy fingers — just do not touch the sheet with your hands.
- A1 mini: place a single part **right of centre** — less torque on the single rail in a collision; **do not use the left 20 mm of the bed**. The single rail is why long even lines and few sharp travels matter especially on the A1 mini.

## What is "always" and what is by case

Always (in `../SKILL.md`): the `resolution`/`slice_closing_radius` pair, `reduce_crossing_wall`, a top pattern matched to the shape, `print_sequence = by object` with several parts.

By symptom/geometry: everything else — per the sections above. A model with an internal floor/shelf → straight to §1. Many small bridges, narrow spots, thin walls → §2 (Arachne). Want it faster without losing quality → §7 and §10.
