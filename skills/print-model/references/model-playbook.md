# Model playbook: what kind of model → how to prepare it

Distilled from a series of documented prints on a Bambu Lab A1 mini (0.4 nozzle, 180 × 180 × 180 mm bed, **bed moves in Y**); the rules carry over to other Bambu printers with the bed size, height and rod clearance taken from their machine preset (`printable_area`, `printable_height`, `extruder_clearance_height_to_rod`). Every rule is backed by a measured slice or a printed part; the numbers are the evidence. Symptom → cause → key tables live in `symptoms-and-fixes.md`, resolution and mesh detail in `slicing-quality.md`, the 16 forecast checks with thresholds in `forecast.md`, filament values in `filament-calibration.md`. This file only says which of those apply to which geometry.

Vocabulary: **package** = the walls-and-resolution keys applied to every print (§3); **forecast** = the 16 checks run on the mesh and the sliced G-code, each rated *stop / noticeable / minor*; **lever** = one `--set` variant sliced against the baseline and adopted only if time grows ≤ 15 % **and no other check worsens** — one lever per variant; **floor line** = a horizontal band on the outer wall at the height of an internal solid layer; **stair-steps** = layer contours reading as map contour lines on a shallow slope.

## 1. Quick decision table

| Model trait | Process and walls | Orientation and supports | Brim, seam, sequence |
| --- | --- | --- | --- |
| Flat vertical walls where ripple / gloss spots would show (enclosures, shells) | `0.16mm High Quality` (outer wall pinned at 60 mm/s instead of 200), 3 walls | largest flat face down; trees from the part's own inner surface where lips need them (`support_on_build_plate_only 0`) | no brim on a flat contact ≥ 60 cm²; seam `back`; one plate per shell |
| Organic figure: lying ribs, backs, domes | `0.12mm Fine`, or `0.20` + height-range modifier (`bbs_project.py ranges`) `0.08` on the shallow-slope band; walls as authored | as authored; tree(auto), z gap 0.24–0.3, xy gap 0.8 | auto brim; seam `back` on faces; run the slope check (15, `scripts/mesh_slopes.py`) before slicing |
| Box with internal floors, shelves, windows | `0.20mm Standard`, 3 walls + precise wall, wall order `inner/outer` | open side up, no supports | auto brim; seam `aligned` in a corner; chamfer floor and window edges in CAD — settings only soften the band |
| Hollow bottom, or tall and narrow (footprint < ⅓ of base at h > 40 mm, or h/width > 3.5), or centre of mass outside the first-layer footprint | as needed | as authored | **`brim_type outer_only`, 5 mm, at once** — never "if it comes off" |
| Rounded edge tangent to the plate (a fillet rolling onto the bed) | as needed; line width 0.5 helps | turn it vertical if the part allows; otherwise a height-range modifier with a thin layer over the bottom 0.28 × R (at 0.20) | offer the CAD chamfer as the alternative and let the user pick — §2.11 |
| Functional cavity (whistle, flute, air or water channel) | author's layer; thinner only if the air-travel check (16, `scripts/gcode_airtravel.py`) does not worsen | as authored (openings to the bed) | `outer_only` brim; levers: retraction up, temperature to the low end of the calibrated range |
| Louvred grille | `0.12mm Fine` + `0.08` on the rounded top, 3 walls; slat width = whole extrusion lines | on the straight mating edge, slats vertical; trees only under the dome, support blocker (`scripts/bbs_blocker.py`) over the slat band alone | `outer_only` 4 mm, removed from the mating edge; seam `back` |
| Screen bezel / frame with a 45° bevel | `0.12mm Fine`, 3 walls, `elefant_foot_compensation 0.15` | flat face down on a textured plate; trees threshold 50° (skips the bevel, reaches the catches) | no brim; seam `back`; keep x ≥ 20 mm from the left bed edge (A1 mini) |
| Legs, small pins | `0.20mm Standard`, 3 walls; pins 100 % infill | as assembled, overhang side facing inward; no supports | no brim; seam `back` toward the lean; print spare pins |
| Snap-fit, cantilever | `0.20mm Standard`, 3 walls | cantilevers parallel to the bed, hooks pointing up; normal(auto) supports, interface spacing 0.2 under cantilevers | no brim; CAD clearance 0.2 → 0.3 if PLA parts will not enter |
| MakerWorld / foreign 3MF | your `… @BBL <printer>` base + the author's process tweaks | author's, including painted enforcers and seams (they live in the mesh) | re-decide the brim for a moving bed; `bbs_project.py retarget` printer and filament first (§2.9) |
| Multi-body assembly | per part | per part | one plate per part; `print_sequence by object` only if every part is lower than the machine's `extruder_clearance_height_to_rod` (25 mm on the A1 mini) |
| Prototype pass | `0.20mm Standard`, 2 walls, 10 % infill; keep supports, brim, seam, blocker | unchanged | −36 % time on a six-plate assembly; `0.24mm Draft` is not worth it (§2.10) |

Layer height is the first choice, not the last: the forecast may send you back once — thin tops (check 7) → one step **thicker** or a cooling companion object; stair-steps (15) → **thinner** on that band only. Line width is not a quality lever: 0.42 at a 0.4 nozzle; narrower gives gaps and weak walls, 0.5 on walls is fine and faster.

## 2. Model types

### 2.1 Boxes and enclosures with floors, shelves and windows

- **What the geometry does.** Every internal floor or shelf is a solid layer: extrusion per layer jumps ×2–3, `infill_wall_overlap` 15 % pushes two thin walls outward → a horizontal band on the outer wall at that height (check 5). A neighbour finishing on the same plate drops layer time (32 → 14 s) → another band (plate composition). A window in a wall: the contour goes from a closed rectangle to a C-shape (−17 % extrusion on that layer) and an `aligned` seam jumps → a bump at the back wall and corner (check 14); the lintel above the window is printed as an ordinary outer wall in the air (22 outer-wall segments instead of 12 — the slicer does not call it a bridge) → sag (check 13).
- **Settings that worked** (box 67.6 × 51.6 × 44, `0.20mm Standard`, 38.5 min, 220 layers): `wall_loops 3` + `precise_outer_wall 1` + package — walls visibly cleaner, the plate-composition band gone. Floor lines are only softened: the extrusion jump on a whistle's chamber ceilings went ×3.5 → ×2.9–3.2 with three walls; zero only with a chamfer or fillet on the floor edges in CAD. A fillet R 20 on an enclosure back stretched the back → wall transition so far that **no floor line appeared** (no ×2 jump found).
- **Wall order.** `inner-outer-inner` cures a floor line the box did not have and made the lintel sag worse (outer wall first, with no neighbour). `inner wall/outer wall`: sag smaller than both the previous attempt and the stock print. Rule: models with openings in walls keep `inner/outer`.
- **What settings cannot fix.** Window-edge bumps were identical with both wall orders, along the whole perimeter, stronger at corners: a one-layer geometry step. Say so and point at the CAD edge. A rough lip predicted from gap fill (10 % of E, 1 859 of 2 956 segments < 1 mm) did not appear — the check-6 threshold is now > 20 % E on ≥ 5 consecutive layers with > 50 % tiny segments.
- **Benchy hull band** at deck height (8–10 mm): an *internal* bridge of 39.5 mm counts as a floor-line trigger. Three walls removed it (+6 % time, +9 % plastic), but the smooth lower hull looked better with two walls in hand — so the third wall is a lever for boxes, tablets, shelves, not a default for smooth hulls (ADR-0004).

### 2.2 Rounded shells with inner lips and tongues (six-plate enclosure)

- **Geometry.** Shells 125 × 170 × 120 and 59 × 165 × 120, wall 4.0 mm, rear fillets R 12–20, 9 mm lips turned inward at the front with a groove for the bezel, three tongues at the rear edge, a roof with 12 slots and a round knob.
- **Orientation rule: back down.** Compare overhang area > 45° and ceiling area in the six axis-aligned positions, then look at cross-sections. Back down leaves one overhang band — the rounded rear edges at 0–6 mm; the lips (90°, at z 98) are held by trees growing from the shell's own inner back (`support_on_build_plate_only 0`); roof slots become vertical slits, the knob a horizontal bump. Open side down: tongues hang 0.5 mm above the bed and the whole back becomes a ceiling over a cavity. On a side: trees land on the most visible rounded edges.
- **Package** (PETG 255 °C / bed 70, MVS 8, min layer time 12 s): `0.16mm High Quality`, `wall_loops 3`, `seam_position back` (seam lands on the roof's inner face and the floor's outer face — both hidden), `brim no_brim` (flat back contact 67–176 cm²), `tree(auto)` threshold 30° (45° gave interface on the same layers, +1.4 % time), `support_top_z_distance 0.25` — PETG welds to supports at 0.2. 8:25 / 147.8 g / 750 layers per cheek, 11:27 / 188.1 g for the middle box; 12–14 % of plastic (21–23 g) goes into trees.
- **Forecast to expect.** Tree marks on the rear fillets (only a smaller fillet in CAD or no supports — then the 9 mm lips sag); tongues printed on 1–2 support layers → rough underside, deburr if the fit is tight; two 125 × 4 mm walls standing 116 mm tall whose roof splits into twelve 4.5 × 3 mm pillars from z 48 to 95 → possible wobble on a Y-moving bed; a knob on the roof gets trees from the bed on its lower half.

### 2.3 Louvred grilles

- **Geometry.** 48 × 155 × 30, 26 slanted slats 1.7 mm thick, a hollow dome Ø 23 protruding 11 mm.
- **Orientation: on the straight edge that mates with the frame** — slats become vertical plates, the dome a hemisphere on its side. Face down or back down there is nothing to stand on (dome and slats protrude).
- **Slats sized to whole lines:** 1.71 mm → two 0.43 mm lines per side, computed from the cross-section, so no gap fill inside the slat. Acute slat corners still give 9 % gap fill of E (11–12 % per layer, up to 68 % short segments at the dome base) → rough slat edges possible; Arachne is a lever on request only.
- **Supports: trees under the dome only, via a support blocker** (`scripts/bbs_blocker.py`: a blocker volume as part of the object, z 24–50 **over the slat band only**). Keep the blocker off anything that protrudes on the far side: a first version spanning the full depth also took the trees out from under two snap clips, and a 2.4 × 9.1 mm clip started in mid-air — caught by `scripts/gcode_unsupported.py`, not by any feature label. Check every blocker with it. Without it trees grew between the slats up to the top rail because the slicer treats the rail above slat edges as an overhang, not a bridge (`bridge_no_support 1` changed nothing): 6.1 % → 0.7 % support plastic, −14 min. No supports at all: 3:48 but the lower quarter of the dome sags ("floating regions" warning). Rail spans over slats are 3.4 mm — fine unsupported.
- **Brim** `outer_only` 4 mm — footprint 155 × 9 mm, h/w 5.5; strip it from the mating edge. `seam back`. `0.12mm Fine` + `0.08` on z 42–48 (rounded top edge, up to 109 mm²/mm — check 15): 4:05, 49.6 g, 543 layers. A height range with supports on switches the slicer to independent support layers (0.11 + 0.01 pairs): +150–240 layer changes, +3–5 % time, harmless.

### 2.4 Screen bezels and frames

- **Geometry.** 173 × 155 × 26, flat front, 45° bevel around a 123 × 91 window, eight snap hooks and four corner catches at the rear.
- **Flat face down** on the textured plate: the face takes the plate texture; the bevel prints as a 45° overhang — set the support threshold to **50°** so trees go only under the catches (interface only at z 21.8–21.9); the rear is not flat, so it cannot go down. `0.12mm Fine` because the bevel is the most visible surface (0.20 shows its steps), 3 walls, `elefant_foot_compensation 0.15` for the visible face edge, no brim: a 148 cm² solid PETG first layer did not warp at 70 °C on texture. 3:31, 69.2 g, 216 layers (2:34 at 0.20).
- The extrusion jump ×8.6 at z 8.5 (top of the frame) is not a floor line — no walls continue above it. Twelve hook islands from z 9.2 get trees outside the perimeter, invisible in the groove.
- A 160 mm part along X leaves x 22.3–177.7: the A1 mini's left 20 mm is off limits (check 2, the extruder collides there on purge).

### 2.5 Legs and small pins

- **Legs** (heel Ø 18, height 25, leaning 36° outward on the diagonal): heel down = as assembled, so the overhang side faces inward and downward, under the enclosure; rotate each leg so the lean points to +Y and `seam_position back` puts the seam on the same hidden side. `0.20mm Standard`, 3 walls, no brim, no supports. Four legs per layer keep every layer above the 12 s PETG minimum.
- **Pins** 2.6 × 3.6 × 14.7: lying flat, `sparse_infill_density 100 %`, six printed for four needed. Gap fill 0.3 % in the pin cores — minor. Whole plate 0:48, 16.7 g, 125 layers.
- Print this cheapest plate **first**: it verifies the filament preset and adhesion before the 8–11 h shells.

### 2.6 Organic figures (skeleton duck, branch phone stand, Moai tissue box, skull whistle)

- **Stair-steps, not speed.** Ribs, backs and domes lying near-horizontal show layer contours side by side, like map contour lines. Step width = layer height / tan(slope): at 10° a 0.12 layer gives 0.7 mm, 0.20 gives 1.1 mm, 0.08 gives 0.45 mm. Speed, temperature, resolution and detours do not change it; only the layer height on those heights, or the orientation. Diagnostic question for any "wave along the rib": do the lines run **along** the layers (steps) or **across** them (VFA)? A speed ripple is a wave along the wall within one layer. A speed tower on Ø 6 × 25 pillars at 0.12 showed no wave at 40–200 mm/s → do not slow the outer wall on organics at 0.12 (such pillars fall at 200 mm/s without a 5 mm skirt).
- **Slope check (15) before slicing:** area of faces whose step width falls in 0.3–2 mm per 1 mm height band; narrower is ordinary layer texture, wider is a terrace the eye reads as design (a Benchy cabin roof at 4.5° → 2.5 mm step, invisible). Threshold ≥ 20 mm² per mm — absolute area, not a fraction: a lying rib's crown is a quarter of its surface and all of it is visible. Duck at 0.12: 12.8 % shallow, 25–170 mm²/mm on the ribs. Branch stand at 0.16: 7.5 %, bands 0–20, 50–60, 90–100 mm, steps up to 0.9 mm — accepted because bark texture masks them (0.12 = steps a quarter smaller for +30 % time); they printed exactly as predicted.
- **Height-range modifier** (`bbs_project.py ranges <in> <out> <object order> <z_lo> <z_hi> layer_height=0.08`) for a band: Moai crown at 82–106 mm lies at 6–11°, 1–2 mm steps at 0.20 (up to 3 400 mm²/mm) → `0.08` on that band only: steps 0.4–0.8 mm, plain texture under fuzzy skin; **6:31 instead of 7:56 at solid 0.12** (5:31 at plain 0.20). The object index in the range file follows the order in `3D/3dmodel.model`, not the model_settings id — a wrong index put the range on the wrong plate (919 layers). A per-layer height profile is ignored by CLI slicing; use the range modifier. When bands are spread over the whole height (skull: z 9–18, 33–44, 47–51, 55–67, 9.5 % of area at 0.16) the modifier is useless — whole-object 0.12 (5.5 %) or 0.08 (2.4 %).
- **Layer vs preset** (duck, 4 walls + supports): `0.20 Standard` 2:58 / 347 layers / 45 g; `0.16 Optimal` 3:35 / 434; `0.16 High Quality` 4:22; `0.12 Fine` 4:00 / 578 / 42 g. High Quality differs from Optimal/Fine only by outer wall 60 vs 200 mm/s — for flat vertical planes; on organics it is invisible, so `0.12 Fine` beats `0.16 High Quality` at the same time. Matte filament hides both stair-steps and gloss spots on carved relief; glossy shows both.
- **Thin tops (check 7).** Layers faster than the 6 s PLA minimum, ≥ 5 in a row: gloss and melting on spikes and tips narrower than ~6 mm; wider elements are minor (Benchy chimney Ø 8, 44 short layers → a few dots on the rim; a 14 × 7 mm mouthpiece, 91 layers at 5.3–5.8 s with fan at 79–80 % → minor). Share of layers under 6 s on the duck: 0.12 → 36 %, 0.16 → 29 %, 0.20 → 23 % → one step thicker, or a second object beside as a cooling companion. Branch tips 106–130 mm: 151 consecutive short layers → glossy tip ends.
- **Supports.** A spongy web inside the ribcage mid-print is the support interface roof (lines through air at 0.5 mm pitch) holding the skull floor and the beak — read `; FEATURE:` in the G-code, not the photo. Gaps for removal: `support_top_z_distance` ≥ 0.2 (the `0.12 Fine` base 0.12 is one layer and welds; 0.24–0.3), `support_object_xy_distance` 0.6–0.8 when trunks hug the part — first removal took ~30 min. Trees cost ≈ 36 min of 3 h on the duck, 6 % / 42 min on the stand. Keep an author's `support_top_z_distance` of one layer when the support is structural (skull mouthpiece: 6 interface layers, "removes easily" over thousands of prints).
- **Moai (two plates, 171.6 × 159.5 × 147.8 and 151 × 173 × 106).** Kept the author's process: fuzzy skin `external` 0.4 / 0.22 (stone texture, hides layers), Arachne, 3 walls, widths 0.4 / 0.5, 8 % supportcubic + `infill_combination`, top 0.6 mm monotonic, `bridge_flow 0.95`; dropped his filament tweaks; added the package and `seam_position back` (the `aligned` seam ran down the face). Body at 0.20: 7:15, 213 g. Both parts printed flawless on matte: a 145 × 151 mm ceiling bridge at 143 mm (one 200 s layer) sagged invisibly inside, a 29 mm lip bridge and 1.1 % unsupported overhangs (nose, brows) merged into the fuzzy skin. A 1.9 M-face mesh needs no Simplify for slicing (CLI: 2 min).

### 2.7 Whistles and flutes

- **Orientation as authored**: vertical, resonators open to the bed, mouthpiece on top (24.6 × 15.0 × 57.3). Flipping puts the mouthpiece slope into supports.
- **Adhesion is the first stop-factor.** Footprint by first-layer extrusion (E × 2.405 / 0.2 = mm²), not by bounding box: 120 mm² of a 369 mm² base, 57 mm tall, 15 mm along the moving Y axis — forecast said *minor*, the part **tore off at layer 460 of 477 (96 %)**. The author's "brim not needed" came from a fixed-bed P2S. Rule: footprint < ⅓ of the base at h > 40 mm, or h/width > 3.5, or centre of mass outside the first-layer footprint → `brim_type outer_only`, `brim_width 5` immediately (159 → 545 mm², ×3.4). The brim does not stick to the resonator mouths on the bottom. Skull whistle (48.3 × 74.7 × 71.1): footprint 369 mm² and 2.7:1 pass both thresholds, but the centre of mass sits at y 88.8 with the base ending at y 83.0 and the mouthpiece tube reaching 44 mm beyond it — held by the base plus the author's single *structural* tree_slim support (painted enforcer, a 146 mm² pad narrowing to one 1.7 mm line at z 4–20). Brim 369 → 817 mm² (×2.2) for 25 s and 0.11 g; it wraps the body only, not the support pad.
- **Cavity threads (check 16) decide the sound.** `reduce_crossing_wall` detours around walls but jumps windows and recesses straight through the air, and every travel at 220 °C with the factory 0.8 mm retraction is a thread candidate landing in the air path. Six-tone whistle at 0.12 / 3 walls: 830 air travels, 3.4 m, 3.8 per layer across the windows, 8 837 retracts → threads inside, weak whistle. At 0.08 / 2 walls: 1 444, 5.6 m, 4.6 per layer, 10 273 retracts — same mechanism, ×1.7. Threshold: ≥ 2 travels per layer in the functional band → noticeable, for a whistle as good as stop. Levers, in order: calibrate retraction (`filament-calibration.md`), then `retraction_length` 0.8 → 1.2 (above ~1.5 → holes in the wall), `nozzle_temperature` to the low end of the calibrated range (210 for a PLA calibrated at 220; **not** for a matte calibrated at 225 — 200–215 tears its arches), then needle-clean the windows. Settings cannot remove the travels; the package cut them 4 933 → 3 635 (−26 %) and 31.3 → 18.6 m (−41 %) on the skull.
- **Layer choice bows to check 16.** Skull: 0.12 costs +13 % time (passes the 15 % rule) but travels rise 3 635 → 4 560 / 18.6 → 25.0 m (+25 %) — kept the author's 0.16 (2:24, 554 layers, 30.6 g), 0.12 offered as a looks-over-sound alternative. The author's 0.08 profile on the six-tone whistle (2:15, 715 layers vs 1:32 at 0.12 High Quality) was taken because he ties chamber tightness to the thin layer — a functional part gets the author's construction plus non-geometric keys only.
- **Outer-wall speed.** `0.20 Standard`: outer wall median 112 mm/s, range 20–159, 48 cooling-slowed layers in 5 bands → gloss spots and uneven shrink on glossy PLA; `High Quality` holds 60 mm/s on all 477 layers (52 min → 1:45 at 0.12). On matte with carved relief the unevenness (60 % at 150–200, 33 % below 100, 9 % below 30) does not read → skip High Quality and its +1 h.
- **Floor lines** on chamber ceilings (z 4.1 / 16.8 / 47.6 / 56.5, extrusion ×3.4 / ×5.1 / ×3.0 / ×2.8): softened by three walls, removed only by CAD chamfers. **Internal bridges** 21.8–22.7 mm stay under the 25 mm threshold; sag inside is tenths of a chamber volume. Measure a bridge as the longest single extrusion in `; FEATURE: Bridge`, not the region's bounding box (a 9.3 × 37.0 region bridges across 9.3 → real span 21.8).
- **Arachne exception.** On a dense carved mesh classic walls gave 16 590 gap-fill segments over 340 of 554 layers and +20 min against the author's Arachne with 2 018 on 98 layers → keep the author's Arachne; the check-6 percentage was silent in both (0.1 % vs 0.8 % E), so decide by segment count. On a Benchy the opposite held (classic 5.6 % gap fill; Arachne made letters, roof slats and the chimney rim worse).

### 2.8 Snap-fits, pins and threads

- **Test piece:** bar 20 × 13 × 50 with two T-slots (8 mm channel, 11 mm crossbar, slot height 8.4, one open at the end) and a latch 12 × 17 × 12 with two 2.5 × 8 × 7.5 cantilevers and Ø 2.5 hooks, CAD clearance 0.2 per side.
- **Orientation.** Bar rotated 180° about X: solid face down, the end-open slot opens upward, no bridges at the bottom. Latch as designed with cantilevers 2 mm above the bed on supports. Hooks pointing sideways would put the layers across the cantilever → it snaps at the first click. `print_sequence` by layer: a 50 mm bar exceeds the 25 mm rod clearance for by-object printing.
- **Settings.** `0.20mm Standard`, 3 walls, `enable_support 1`, `support_type normal(auto)`, `support_on_build_plate_only 1`, `support_interface_spacing 0.2` — a dense interface because the cantilever underside slides on the slot floor; 33 min, 8.4 g, 254 layers, supports 1.2 %, no shallow slopes.
- **Fit.** PLA slots come out 0.1–0.2 mm narrower than nominal → tighter than designed; if the latch will not enter, 0.3 in CAD. Solid layers under slot floors (extrusion ×2.8) may leave a thin band; 8–11 mm bridges over slots sag slightly, so the slot top sits a hair under 8.4. Mating tongues printed over supports get a rough underside — deburr.
- **Threads** (CAD rules, seam behaviour confirmed on a printed M36 × 4): modeled thread, pitch ≥ 2 mm at 0.4 nozzle / 0.2 layer (3–4 better), axis vertical for both parts (ISO 60° prints unsupported), clearance by a 0.15–0.30 ladder on the thread faces — never by scaling (breaks the pitch); tightness from a shoulder, not zero clearance; 1 × 45° entry chamfer. An `aligned` seam jumps between layers on a thread and drops beads on the flanks (bumps at 1.2, 7.9, 10.7… mm) → hide the seam; scarf seam keys produce no G-code change in Studio 02.08 (body identical byte for byte), so do not offer it.

### 2.9 MakerWorld projects

- **Three preset levels**, top down: Printer (bed, start G-code, retraction) → Filament (temperature, flow, MVS, fan, bed) → Process (layer, walls, infill, supports, speeds); the `@BBL <printer>` suffix is the compatibility binding. An author's 3MF carries all three; opening it switches the slicer to *his* printer, and your presets turn grey as Unsupported — the root cause is the printer, not the filament.
- **What is whose.** Printer → yours. Filament → yours, calibrated (the author's is another plastic on another machine). Process → your `… @BBL <printer>` base **plus the author's process tweaks**, read from `different_settings_to_system` (the `*` before the preset name), never rebuilt by guesswork. Drop the author's filament and machine tweaks (a Moai author's `slow_down_layer_time 10`, min speed 10). Painted support enforcers and seams live in the mesh and survive retargeting — `tree(manual)` without paint yields nothing (skull: 172 enforcer + 4 789 seam triangles are the whole support strategy). Keep the author's wall count; add a third only when check 5 fires.
- **Check the model page for a profile for your printer first.** A profile made natively for the A1 mini needed only filament and plate changed and sliced within 4 % of the author's estimate (2:13 vs 2:19).
- **Retarget traps.** Author's AMS leaves four values in every per-filament list (`filament_colour`, `filament_map`, `pressure_advance`, fan keys, 4 × 4 flush matrix) → four filament slots on a single-filament plate; cut every list to its first value. An object placed in a larger printer's coordinates (centre 167, 161) sits outside a 180 mm bed → move it to (100, 90). The author's scale (e.g. 1.355) lives in the object transform, not the mesh. Real Bambu start G-code is not in the system JSON: a stub start (`M109 S205`, purge line off the bed, no wipe) printed a duck at 205 °C instead of 220 and tore a box's first layer; verify `M1002` appears hundreds of times and no un-indented `M109 S205` remains. Set `enable_prime_tower 0` for one filament.
- **Fixed-bed advice does not transfer.** "Brim not needed" and support thresholds from P1/P2/X1/H2 owners assume a static bed; on a Y-moving bed re-run check 10. A Standard preset for a P1S will also run the outer wall at up to 159 mm/s where your filament's MVS allows — a glossy PLA capped at 12–13 mm³/s never reaches the preset's 200 mm/s anyway, so fast presets neither speed up nor hurt.

### 2.10 Prototype vs final pass

- Six-plate enclosure, quality version (`0.12 Fine` / `0.16 High Quality`, 3 walls, 0.08 range on the grille): **36.5 h, 618 g**. Prototype: every plate re-sliced at `0.20mm Standard` (outer wall 200 instead of 60), `wall_loops 2`, `sparse_infill_density 10 %`; supports, gaps, blocker, brim, seam and slat widths unchanged, the 0.08 range dropped → **23.5 h, 503 g**. Per plate: grille 4:05 → 2:35, bezel 3:31 → 2:34, cheek 8:25 → 5:08, middle box 11:27 → 7:18.
- `0.24mm Draft` on the biggest box: 6:51 vs 7:18 (−6 %) — rejected: lip overhangs and fits are worse for half an hour.
- Prototype forecast adds: 0.20 steps visible on the bevel and rounded grille edge; two-line walls over 10 % infill lower the stiffness of thin roof pillars. Support marks are the same. Keep the quality settings-diff as the base for the final material.
- **Plate order:** cheapest plate first (verifies filament preset and adhesion), then the plate with the thinnest features, then ascending time. The printer has no queue: one plate at a time, next one when the bed is clear.

### 2.11 A rounded edge tangent to the build plate

- **Geometry.** Where a fillet rolls onto the plate it is a 90° overhang exactly, not "almost", and it flattens with
  height. A line holds if it lands on at least half the line below, so the band that cannot carry itself is
  **`band = R × (1 − k/√(1+k²))`, `k = line width / (2 × layer height)`**:

  | Layer | Share of R | R 12 mm | R 25 mm |
  | --- | --- | --- | --- |
  | 0.28 | 40 % | 4.8 mm | 10.0 mm |
  | 0.20 | 28 % | 3.3 mm | 6.9 mm |
  | 0.16 | 20 % | 2.5 mm | 5.1 mm |
  | 0.12 | 13 % | 1.6 mm | 3.3 mm |
  | 0.08 | 7 % | 0.8 mm | 1.6 mm |

  Halving the layer more than halves the band — the only lever here with non-linear return. Width 0.5 instead of 0.42
  takes 28 % down to 22 % at a 0.20 layer.
- **What it looks like.** A horizontal band of ragged, torn lines, worst where the contour flares fastest and fading to
  nothing on the flat part of the same wall; above and below it the surface is clean. On a PETG shell (0.20, R 12–20)
  the band ended at 3.2–3.4 mm as predicted, and for the first 16 layers the contour was also **fragmented into separate
  islands** (outer-wall bbox width jumping 45 → 0.8 → 43 mm), so the wall kept starting and stopping inside the band.
- **No check catches it.** `gcode_unsupported.py` reads the band as supported (check 4 blind spot: material rests on the
  line below, just on 20 % of it) and no feature label changes. Find it on the mesh at step 2, from the fillet radius.
- **Levers, in order.**
  1. **Orientation first.** A fillet standing vertical or facing up is free; only the one rolling onto the plate is a
     problem. Compare overhang and ceiling area over the six axis-aligned positions — do not assume the part can turn
     (on this shell it could not: on its side the hollow opened downward, and the roof slots became horizontal).
  2. **A thin layer over the band only** — `bbs_project.py ranges <in> <out> <obj> 0 <band> layer_height=0.08`, the same
     tool as check 15. Time is paid only inside the band.
  3. **Line width 0.5.**
  4. **Leave `enable_overhang_speed` and the overhang fan on.** They are what holds those lines; turning them off for an
     even sheen (§5) breaks this band first.
  5. **Supports: measure before adding.** Studio's `tree(auto)` already covered the band here, and
     `support_remove_small_overhang = 0` changed nothing (interface stayed at 0.2–1.8 mm in both slices, ±13 mm of
     extrusion). A support under a visible rounded edge buys a rough imprint instead (check 8).
- **Removing it entirely is a CAD change:** replace the bottom of the fillet with a 45° chamfer tangent to the fillet at
  the top of the band (≈ 7 mm for R 25). The rounded look survives; the band, the supports under it and the sliver of a
  first-layer footprint all go at once.
- **Offer both routes explicitly** — the CAD chamfer, or the thin-layer band — and let the user choose. Never pick one
  silently: which one is right depends on whether they can still edit the model.

## 3. The walls-and-resolution package (every preparation, ADR-0003 / ADR-0004)

| Key | Value | Why (measured) |
| --- | --- | --- |
| `resolution` | 0.004 (Bambu 0.012) | nozzle path follows the mesh instead of coarse segments; duck 589 183 → 740 694 G1, 27 → 35 MB, 2:58:24 → 2:59:01 (+37 s on 3 h); box 13 843 → 14 565 G1, 37:30 → 37:28. Not below 0.003: planner overload → skipped extrusions, zits |
| `slice_closing_radius` | 0.01 (Bambu 0.049) | closes mesh gaps < 2× value at the price of accuracy and **masks** the resolution change; raise only for a known-broken mesh |
| `enable_arc_fitting` | 1 (keep) | without arcs the duck slice is 1.77 M G1, 49 MB, 3:09:56 vs 740 k G1 + 339 k arcs, 2:59:01 — 2.4× the commands and +11 min, i.e. exactly the overload the "disable arcs" advice warns of |
| `precise_outer_wall` | 1 | outer wall printed at true width, not squeezed by the inner one; part of the band cure on the box and the Benchy deck |
| `wall_generator` | classic | Arachne on a Benchy: gap fill 5.6 % → 0 but bumpy letters, rough roof slats, more sag and stringing — variable-width lines on flow calibrated for 0.42; Arachne only on request or when gap-fill segment count says so (§2.7) |
| `wall_loops` | preset (2); 3 as lever | third wall: +5–10 % time, +7–10 % plastic, floor-line band gone; smooth hull below looks worse — box/shelf yes, smooth shell by choice |
| `no_slow_down_for_cooling_on_outwalls` | 1 (Bambu 0) | the layer-time stretch comes out of the inner wall and infill instead of the visible one; measured with the slowdown forced on, outer wall 153 → 181 mm/s and its layer-to-layer spread 31 → 20 mm/s, total time 6:53 → 6:51. The key **is** in Bambu Studio, contrary to what `symptoms-and-fixes.md` used to say |
| `reduce_crossing_wall` + `max_travel_detour_distance` | 1 / 300 | nozzle does not drag a blob through the outer wall; skull travels −26 %, air length −41 % |
| `top_surface_pattern` | by shape | concentric on round tops, monotonic elsewhere |

Cost of the whole package on a 2 h print: 2:13 → 2:19 (+4 %), +0.03 g. Mesh beats settings: export STL from CAD, not STEP (the slicer's converter lays large flat triangles on curves); a STEP meshed at 0.01 mm tolerance equals the CAD export. Plate rules on the A1 mini: x ≥ 20 mm from the left edge; `by object` only when every part is under the rod clearance (`extruder_clearance_height_to_rod`, 25 mm on the A1 mini); everything else by layer or one plate per part.

## 4. Growing the playbook

After every print, write **forecast vs fact** next to the settings diff and move thresholds only on a miss: check 7 became *minor* for tops wider than ~6 mm after a chimney printed clean; check 15's window became 0.3–2 mm after a hull flagged at "< 25°" showed no steps; check 10 became "brim at once" after a whistle tore off at 96 %; check 6's threshold rose after a lip predicted rough came out clean; a Moai whose every *noticeable* item vanished under fuzzy skin on matte left the thresholds alone. "No defects expected" is a forecast too and gets checked the same way. One variable per experiment, one lever per variant; when a lever fails twice on the same geometry (window-edge bumps with both wall orders), the answer is CAD, and the playbook should say so rather than offer a third setting.
