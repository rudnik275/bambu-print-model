# Forecast: catalog of checks

The forecast is a mandatory part of handing a model off to print: before the Print button, the user reads what will come out badly on this model, where, why, and what fixes it. Every check below runs on every model; the result is either a hit with a severity or "clean". A skipped check = no forecast.

Severity is three words, and only these:

- **stop** — the print will certainly ruin the part or the printer. Do not offer Print; name the options and wait for a choice.
- **noticeable** — the defect will be visible on the finished part. Name the location (height, side), the cause, what weakens it right now and what removes it entirely. Printing is the user's decision.
- **minor** — only someone looking for it will see it. One line.

Sources: `result.json` and `slice_info.config` from the CLI slice, `scripts/gcode_features.py <plate.gcode>` (per-feature summary), `scripts/gcode_layers.py` (time and extrusion per layer), `scripts/gcode_airtravel.py` (nozzle travels through air inside the part — check 16), `scripts/bbs_current.py` on the project.

Counting per-feature extrusion from `G1` only is a mistake: with `enable_arc_fitting` smooth walls move into `G2/G3`, and `resolution` (the quality package changes 0.012 → 0.004) shifts the very share of the contour that becomes arcs. Walls are undercounted, the gap-fill share inflates — differently in each slice, so a comparison of variants reads backwards. On a whistle, check 6 without arcs reported "25 consecutive layers at 22–27 %"; with arcs — clean in both slices. `gcode_features.py` counts arcs; any custom analysis must do the same.

## Checks

| # | What | How to see it | Threshold | Severity | What to say |
| --- | --- | --- | --- | --- | --- |
| 1 | Does not fit | `result.json` → `bbox_objects` against the machine preset's `printable_area` and printable height; `slice_info` → `outside` | any excess | stop | scale or split — ask |
| 2 | Left 20 mm of the bed | bbox `x < 20` | — | noticeable | move it right (an A1 mini trait — single-rail machine, the bed moves in Y — the toolhead clips that zone during the purge; a single part goes right of center) |
| 3 | Bridge without support | `gcode_features` → Bridge `max span` — **the length of the longest single extrusion through air**, not the region extent (the extent is printed in parentheses). An earlier version of the tool reported the extent: on a whistle, a 9.3 × 37.0 mm bridge region became "37 mm" against the 25 threshold, while the slicer lays the bridge across the short side and the real span is 21.8 mm | > 25 mm — noticeable; > 40 mm — stop | by threshold | sag on the underside; support under the bridge or reorientation |
| 4 | Overhang without support | `enable_support = 0` and Overhang wall E > 1 % of total, or consecutive layers with Overhang wall | — | noticeable; at E > 5 % — stop | ragged underside of overhangs; enable supports from the build plate / from the model |
| 5 | Floor line | `gcode_layers` → heights where per-layer extrusion jumps ≥ 2× relative to its neighbors while walls continue above | each such height | noticeable | a band on the wall at that height; settings (wall order, precise wall) weaken it, a chamfer along the shelf edges removes it — `symptoms-and-fixes.md` §1 |
| 6 | Tiny extrusions | `gcode_features` → Gap infill: share of E and `tiny/seg`; worst layers | Gap infill > 20 % E on ≥ 5 consecutive layers and tiny > 50 % on them (a box: 10 % E, tiny 63 % — nothing visible on the rim) | noticeable | roughness / weak layer at those heights; Arachne, wall width 0.5, `filter_out_gap_fill` — §2 |
| 13 | Wall over an opening | `gcode_features` → "Outer wall over openings" summary: a layer where the Outer wall segment count jumps ≥ 1.5× and returns on the next; the slicer does not treat this as a bridge | any such layer | noticeable | the lintel is printed through air at full speed → sag; with a `wall_sequence` that puts the outer wall first (`outer/inner`, `inner-outer-inner`) it is worse — return to `inner/outer` or slow the layer down; in the design — a chamfer/arch above the opening |
| 14 | Contour jump | `gcode_features` → "Outer wall events": a layer where the contour splits or merges (start and end of an opening, shelves) | any | noticeable | **a bump around the perimeter at that height, stronger in the corners** — a geometry transition within one layer; settings do not fix it (a box: v2 and v3 identical), only a chamfer/fillet along the opening edges in the design does — say this plainly |
| 7 | Tops overheating | `gcode_layers` → consecutive layers with time < `slow_down_layer_time` (a filament setting: 6 s in Bambu PLA presets, 12 s in PETG) | ≥ 5 consecutive layers | noticeable for spikes and tops narrower than ~6 mm; minor for wider features (Benchy: Ø8 chimney, 44 layers < 6 s — only dots on the rim) | gloss/slumping on turrets and spikes; print by object, a second "cooler" object, lower temperature for the top — §5 |
| 8 | Support marks on the visible side | Support interface: heights and xy against the model's visible surfaces | interface under a visible surface | noticeable | a rough patch at that spot; change orientation or accept |
| 9 | Seam on a cylinder | `seam_position = aligned` and an object without corners (round contour) | — | noticeable | a vertical seam line the full height; hide the seam in a corner (`seam_position`). Scarf seam (`seam_slope_type`) in Studio 02.08.02.61 **does not work**: the keys land in the header, the G-code body does not change — verified on a ring and a Benchy, CLI and GUI, classic and Arachne, `external`/`all`, with and without the conditional; do not offer it until confirmed on a newer version |
| 10 | First layer | a large flat footprint → corner warping; a tall narrow part → wobble; **a hollow bottom** (whistle, flute, figurine on a small base) — compute the first-layer footprint from first-layer extrusion (E × 2.405 / 0.2 = mm²), not from the bbox. **The third sign, which the first two miss — mass carried beyond the footprint:** compute the center of mass in X and Y as the extrusion-weighted center of all layers (exclude support and `Custom`) and compare it with the first-layer bbox | footprint < ⅓ of the base at height > 40 mm, or h/width > 3.5 without a brim, **or the center of mass outside the first-layer bbox** (a whistle: footprint 369 mm² — seems fine, 2.7:1 — also fine, but the CoM in Y sits at 88.8 mm with the base ending at 83.0, because the mouthpiece extends 44 mm backward; the part is held by the base and the author's single support pressing against the underside of the tube) | noticeable (PLA warping — minor) | brim `outer_only` 5 mm **right away**, not "if it comes loose": a whistle — 120 mm² of 369, 3.8:1, narrow axis along Y (the A1 mini bed travels in Y), the forecast said "minor" → detached at 96 %. An author's "brim not needed" from a P2S/X1 (stationary bed) does not transfer to a bed-slinger |
| 11 | Slicer warnings | `slice_info.config` → `<warning …>`; `result.json` → `error_string` ≠ Success | any, except timelapse | noticeable / stop by the text | quote it |
| 12 | Support share | `result.json` → support g / model g | > 40 % | minor | a lot of plastic and time wasted — reconsider orientation |
| 15 | Stair-stepping on shallow slopes | `scripts/mesh_slopes.py <project.3mf> --layer <layer>` — on the mesh, before slicing: area of faces whose step width (layer / tan(slope)) falls within 0.3–2 mm, per height band; narrower — ordinary layer texture, wider — a terrace the eye reads as design (Benchy: cabin roof 4.5°, 2.5 mm step — no visible steps) | ≥ 20 mm² per 1 mm of height | noticeable | layer contours will lie like contour lines on a map across the whole band — ribs, backs, domes of lying organic shapes; speed, temperature, resolution do not affect it; fixed by a thinner layer at those heights — a height-range modifier, `bbs_project.py ranges` (lever below) — or a different orientation |
| 16 | Strings in cavities | `scripts/gcode_airtravel.py <plate.gcode> --bands …` — nozzle travels through air **inside** the part (windows, channels, chambers): `reduce_crossing_wall` only avoids walls; the slicer jumps straight across a recess or a window. Compute only for parts where an internal cavity is functional (whistle, flute, air or water channel, guide) | ≥ 2 travels per layer in the band of a functional cavity | noticeable; for a whistle — effectively stop for the sound | strings will lie across the jet/channel; levers — temperature down to the low end of the calibrated range and retraction up (retraction calibration first, `filament-calibration.md`), then cleaning with a needle through the windows. A whistle printed at 0.12 with six windows: 830 travels / 3.4 m, ~4 per layer across the windows at 220 °C and 0.8 retraction → strings inside, weak whistle |

Check 5 is the one that fires most often on boxes, vases, trays; 13 and 14 — on any openings in walls (windows, slots). Before calling a height a "floor line", check 13/14: on a box, both "shelves" turned out to be window edges.

Check 15 is the only one that works on the mesh, not the G-code, so it runs at step 2, before slicing. Bands along a rib, a back, a dome — this check first, and only then speed hypotheses: on a duck, "ripple along the ribs" was stair-stepping; a speed tower could not have answered it.

Setting interactions the forecast accounts for: a `wall_sequence` with the outer wall first worsens 3, 4 and 13; `seam_position = aligned` amplifies 9 and 14.

## Levers: hit → project variant

A **noticeable** item whose lever is a setting, not design or orientation, does not stay advice: the agent immediately builds a variant (`scripts/bbs_project.py variant --set …`), slices it and compares (`scripts/gcode_compare.py a b`). The variant becomes the working one if time grew by no more than 15 % and no other check got worse; otherwise the "Forecast:" block gives both with the time difference, and the user chooses. What was changed and why is always in the block.

| Check | Lever (`--set`) | Cost |
| --- | --- | --- |
| 3 bridge > 25 mm, 4 overhang | `enable_support=1 support_type=tree(auto) support_on_build_plate_only=1` + gaps `support_top_z_distance=0.2 support_object_xy_distance=0.8` | time, marks (check 8) |
| 5 floor line | `wall_loops=3` (precise wall is already in the package): Benchy v3 — the ridge on the deck went away, a box — cleaner walls; **but** a smooth hull below the deck looks worse with three walls (Benchy v1 vs v3 — v1 was preferred), so set it on boxes, trays, parts with shelves, and on housings with a smooth wall offer the choice; if the ridge remains even with three — only a chamfer along the shelf edges in the design | +5–10 % time, the look of a smooth hull |
| 6 tiny extrusions | **not Arachne by default**: Benchy v2 removed gap fill (5.6 % → 0), but the letters, roof slats and chimney rim became lumpy, lintels sagged more, more stringing — wide variable-width lines on a flow calibrated for 0.42. The lever is wall width 0.5 / `filter_out_gap_fill` (`symptoms-and-fixes.md` §2); Arachne — only on explicit request and as a single variable | — |
| 10 wobble, weak base | `brim_type=outer_only brim_width=5` | an edge after brim removal |
| 16 strings in cavities | `nozzle_temperature` and `nozzle_temperature_initial_layer` at the low end of the filament's calibrated range (example: SUNLU PLA → `nozzle_temperature=210 nozzle_temperature_initial_layer=210`) and `retraction_length=1.2` (machine setting; the factory 0.8 is an uncalibrated default) — `variant` puts the keys in their own filament and machine tabs; verify in the G-code: `M104/M109 S210`, `G1 E-1.2` | slightly weaker layer adhesion; retraction above ~1.5 gives holes in the wall |
| 13 wall over an opening | `wall_sequence=inner wall/outer wall` (if it was set otherwise) | — |
| 15 stair-stepping | `scripts/bbs_project.py ranges <in> <out> <obj> <z_lo> <z_hi> layer_height=0.08` — a thin layer only in the band from `mesh_slopes`, the object by its order in `3D/3dmodel.model` (a Moai: 82–106 mm, +1 h vs 0.20, −1.5 h vs a solid 0.12). With supports enabled, a range switches Studio to independent support layers over the full height (0.11 + 0.01 pairs in `Z_HEIGHT`): +150–240 layer changes, +3–5 % time, no harm to the model (a grille) | time in the band ×2.5 |
| 8 trees grow where they cannot be reached (between slats, into louvers, into a cavity) | `scripts/bbs_blocker.py <in> <out> <obj> x0 y0 z0 x1 y1 z1` — a support blocker as part of the object, bed coordinates: overhangs inside the box stay unsupported, trees to targets outside it grow as before. `bridge_no_support=1` and `max_bridge_length` do not help here — Studio treats a crossbar over slat edges as an overhang, not a bridge (a grille: 6.1 % → 0.7 % support, −14 min) | the overhangs left behind print through air — only spans up to ~5 mm and hidden undersides |
| 7, 9, 12, 14 | orientation, a second object, layer height (step 3), design — not `--set`; name them in the block | — |

One lever at a time: two variables in one variant make it impossible to tell what worked.

## Format in the message

```
Forecast:
- [noticeable] bands at 6.2 and 34.2 mm — internal shelves; wall order weakens it, a chamfer in the design removes it
- [noticeable] rim 42–44 mm — 63 % of gap segments shorter than 1 mm → rough top; Arachne fixes it
- [minor] aligned seam in a corner — nearly invisible
No stop factors.
```

"No defects expected" is also a forecast, and it is also verified by the print. After the print, the forecast is compared with the outcome in the print's notes (a "Forecast vs. reality" section) — that is how the catalog is calibrated: a threshold that missed gets corrected here.
