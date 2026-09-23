# General practice: diagnosing and calibrating any FDM print

Distilled from the CN3D knowledge base (docs.cn3d.eu, 2026: calibration guides, twelve diagnostic flows, knowledge-base articles). The source is written for Klipper/Marlin and OrcaSlicer users; everything here is kept only where it applies to a Bambu printer with closed firmware (automatic bed levelling, input shaping and flow dynamics), and setting names are translated to Bambu Studio keys — checked against Studio 2.8, not guessed. Advice that needs firmware access (e-steps, PID, skew, input-shaper, motor current) is left out.

This file is **general knowledge, not measured on our prints** — when it disagrees with `model-playbook.md`, `symptoms-and-fixes.md` or `filament-calibration.md`, those win; the disagreements are marked below.

## 1. Read the symptom before touching a setting

Most wrong fixes start from a misread symptom. First sort it:

| What you see | Most likely | Not this |
| --- | --- | --- |
| Fine hairs everywhere between features | nozzle too hot (each +5 °C noticeably more hairs), then wet filament | retraction — raise it last |
| Thick strings, oozing blobs | PETG behaviour, or temperature far too high | |
| A blob **only at the seam** | pressure dumped where the loop ends — on Bambu, the automatic flow dynamics failed or was skipped for that print; then `seam_gap` | over-extrusion |
| Blobs at **every** corner | pressure advance too low (same note) | |
| Ripples that fade out a few mm **after** a corner | ringing (vibration) | VFA |
| Even vertical lines over the **whole** wall | VFA — see the interval test below | ringing |
| Horizontal bands repeating at a fixed height step | Z-banding (lead screw) | floor line — that one sits at one height, at an internal floor (`symptoms-and-fixes.md` §1) |
| Rough and wavy everywhere | flow ratio too high | |
| Gaps that are constant through the print | exceeding max volumetric speed, partial clog | |
| Gaps that get **worse** the longer it prints, recover after cooling | heat creep | |
| Gaps at **random** heights, popping or hissing from the nozzle | wet filament | anything else — dry first |
| Part too big in X and Y only | flow ratio too high | |

**Interval test for periodic lines** — measure the spacing with calipers: ~2 mm = belt tooth pitch (GT2); ~7 mm = one turn of a 20-tooth pulley; irregular = a bearing. On a bed-slinger note the axis: lines along X-moves point to the X belt, along Y-moves to the Y belt. Horizontal bands every ~2 mm = one turn of a single-start lead screw, ~8 mm = a 4-start screw. None of these are fixed in the slicer; the slicer mitigation is a slower outer wall (below).

## 2. Stringing and retraction

- **What retraction does:** it does not suck plastic back, it releases the pressure stored in the melt zone. More retraction beyond that point only pulls softened filament into the cold zone — clogs and grinding.
- **Order before touching `retraction_length`:** dry the filament → confirm the temperature (take the low end of the calibrated range) → flow dynamics on → no wall crossings (`reduce_crossing_wall`) → only then retraction.
- **Direct drive:** start 0.5–1.0 mm, sensible range 0.2–2.0 mm. The source calls anything above 2 mm "hiding a different problem". **Ours is stricter:** on a Bambu direct-drive toolhead above ~1.5 mm already punched holes in the wall (`forecast.md`, check 16) — keep 1.5 as the ceiling.
- **Travel speed** as an anti-ooze lever: the source's 150–200 mm/s is already far exceeded by Bambu presets (`travel_speed` 700) — nothing to gain there.
- **Seam blob:** `seam_gap` exists in Studio (default 15 % of the nozzle diameter ≈ 0.06 mm); the source's 0.10–0.15 mm is ≈ 25–35 %. "Wipe on loops" does not exist in Bambu Studio 2.8; `wipe` (on) and `wipe_distance` (2 mm) are the nearest.

## 3. Drying

Wet filament imitates almost every other defect (stringing, gaps at random heights, rough walls, weak layers) and cannot be calibrated away — dry before calibrating or diagnosing. Source values: **PLA 45 °C / 4 h** (a vendor sheet gives 55 °C / 6 h), **PETG 65 °C / 6 h**, ABS 80 °C / 4 h, PA 80 °C / 12 h+. Signs of moisture: popping or hissing at the nozzle, steam, bubbly or foamy lines.

## 4. Layer adhesion (layer separation, weak parts)

- Minimum nozzle temperature for a proper bond: **PLA ≥ 200 °C, PETG ≥ 235 °C.**
- **Layer height ≤ 75 % of the nozzle** (0.4 nozzle → at most 0.30 mm); strongest bond at 50–60 % (0.20–0.24 mm).
- Too fast for the melt: slow down 20–30 % or add +5 °C.
- For strength prefer gyroid/cubic infill over grid/lines — more even in all directions. Strength still comes mainly from walls (`model-playbook.md`).
- Cooling tuned last: too much fan weakens layers (see `symptoms-and-fixes.md` §5 for the fan-per-layer mechanism).

## 5. Warping and the first layer

- Clean the plate with warm water and dish soap, never touch it bare-handed; IPA only for a quick wipe between prints (`symptoms-and-fixes.md` §11).
- Bed temperature on textured PEI: PLA 60–65 °C; the source gives **PETG 75–85 °C**. **Ours:** a 148 cm² solid PETG first layer did not lift at 70 °C on texture (`model-playbook.md` §2.4) — raise the bed toward 80 °C only when a PETG part actually lifts.
- **PETG fan:** the source says at most 20–30 %, off for the first 3–5 layers. Bambu's PETG presets run 40–90 % (off for the first 3 layers) and our PETG prints did not warp or delaminate on them; treat 20–30 % as a lever for a PETG part that lifts at the corners or splits between layers, not as a default.
- Sharp 90° corners lift first: **mouse ears** (small discs at the corners) are often better than a full brim. In Studio: `brim_type = brim_ears` (ears placed automatically on sharp corners), or paint them where needed.
- Heat creep, partial clog — **cold pull:** heat to 200 °C, cool to 90 °C (PLA) / 120 °C (PETG), pull the filament out firmly; repeat until the tip comes out clean (3–5 times). Do not leave the hotend hot and idle for more than a few minutes, especially with PETG.

## 6. Bridges

- A bridge line stays round in the air instead of being pressed flat, so it needs its own flow, speed and cooling.
- Source recipe: bridge flow 1.4–1.6 (start 1.5), bridge speed ~10 mm/s for visible or difficult bridges, fan 100 % for PLA, **less for PETG** (it bonds worse when cold). **Not verified here, and it runs against the only data we have** — a transplanted MakerWorld profile with `bridge_flow 0.95` printed a 29 mm lip bridge cleanly (`model-playbook.md` §2.6). Bambu Studio keys: `bridge_flow` (default 1), `thick_bridges` (default 0), `bridge_speed` (default 50). Bridge cooling on Bambu is `overhang_fan_speed` (PETG preset 90 %); the presets carry no separate bridge fan value. Test before adopting.

## 7. Surface above supports

- Interface: 2–3 layers, dense (in Studio: `support_interface_spacing` 0–0.2), rectilinear or concentric, slow (source 20–40 mm/s; Studio default `support_interface_speed` 80).
- Top Z distance: one layer height (0.1–0.2 mm) for PLA; **PETG on PETG needs 0.25–0.3 mm** — matches our own finding that PETG welds at 0.2 (`model-playbook.md` §2.2).
- If the support still fuses: print it 5–10 °C cooler than the part (only with a second filament/extruder; with one filament use the Z gap).

## 8. Ringing and VFA — slicer-side mitigation

On a closed-firmware printer the root causes (belts, pulleys, input shaping) are not user-tunable; what the slicer can do:
- Ringing: lower `outer_wall_speed` by 10–15 % — ringing grows with corner speed.
- VFA: lower `outer_wall_speed` to 40–60 mm/s as an immediate mitigation — which is exactly what `0.16mm High Quality` (outer wall 60) does.

## 9. Maximum flow of hotends — sanity check

Typical hotend ceilings: E3D V6 ≈ 11 mm³/s, Dragon HF ≈ 18, Volcano ≈ 25, **Bambu stock hotend ≈ 32**. A calibrated `filament_max_volumetric_speed` well below 32 on a Bambu is the filament's limit, not the hotend's — normal. Real speed of a line = max volumetric speed ÷ (layer height × line width).
