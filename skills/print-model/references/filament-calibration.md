# Calibrating a new filament

Based on Factorian Designs, "Filament Calibration Masterclass", merged with the profile decisions and calibration experience behind this skill. Read this when a new filament is loaded; it is not needed for preparing a model to print.

Calibrate a **product line, not a colour**: the same plastic in another colour usually gives a close result, another brand always gives its own. Pigment changes flow within ~1 % — below the useful resolution. Once per line, then the values live in a Bambu Studio user filament preset. Matte is a different line from glossy PLA of the same brand (filler, different flow ceiling, usually a different flow ratio and temperature) and gets its own preset; PETG is a separate line too.

Before any test: the filament is dry, stored in a sealed box with silica gel. Wet filament produces "defects" that cannot be calibrated away.

## 1. Why calibrate at all

A system preset is a good guess for a brand and material class, not for the spool on the printer. What goes wrong when it is off:

- **Flow lines.** Too little flow leaves dark grooves between the extrusion lines on top surfaces; too much gives bulging lines with a glossy wave. Both read as "rough print" and are invisible in the slicer.
- **Overheating.** Too hot: overhang tips pull up and grow hairs, fine detail smears, stringing increases.
- **Under-extrusion at speed.** Bambu printers push walls fast (an A1 mini runs them at 200–300 mm/s). A nozzle that is too cold for that flow does not melt the plastic through — overhangs disintegrate into threads, and above the filament's real flow ceiling the wall turns matte and loose. A preset with a max volumetric speed that is too high lets the printer run into that ceiling; one that is too low quietly throttles every print (example: a matte PLA whose system preset said 21 mm³/s printed clean to 26 mm³/s — the preset was conservative; for a PLA+ from the same brand the preset's 12 mm³/s was exact, so this is only known by testing).
- **Stringing.** Hairs between features on travel moves — a retraction matter, and often mistaken for a temperature one.

Every downstream fix (slicing keys, wall order, speeds) treats a symptom if the filament underneath is wet or uncalibrated; see `slicing-quality.md`, "Symptom → where to look". Even when the system preset turns out almost exact, the test is not wasted: the value is then known, not assumed.

## 2. What "calibrated" means

The minimum set, in the order it is measured:

| Value | Key in the preset | How |
| --- | --- | --- |
| Temperature | `nozzle_temperature` (+ `nozzle_temperature_initial_layer`) | temperature tower |
| Flow ratio | `filament_flow_ratio` | two-pass flow test (coarse, then fine) |
| Max volumetric speed | `filament_max_volumetric_speed` | flow ramp on a single-wall cylinder |

Beyond that:

- **Retraction distance** — only on a stringing symptom. The machine preset's default is usually enough for a direct-drive extruder (example: a Bambu Lab A1 mini machine preset carries 0.8 mm / 30 mm/s and never needed a change).
- **Pressure advance** — not calibrated. Bambu printers measure flow dynamics themselves before each print; leave `enable_pressure_advance = 0` in the preset. This is a deliberate exception: the video's author calls the automatic flow calibration "unreliable" and cuts it out of the start G-code in favour of one manual K. If part corners start drifting from print to print, this is the first candidate to revisit. What matters if manual PA is ever attempted:
  - a value is correct for exactly one pair of "flow + acceleration"; the further from it, the worse;
  - so it is calibrated at the speed and acceleration of the **outer wall** — what is seen most;
  - if the max volumetric speed is low, the printer never reaches the nominal wall speed — take the real speed from the preview, not from the settings field;
  - adaptive PA (several values for different flows) gives artifacts on Bambu — Klipper only.

One filament is calibrated once; after that no in-print calibrations are needed — except PA, which stays automatic.

## 3. Order, plates, and how to read them

Order matters — early steps shift the results of later ones. The working order:

1. **Flow, coarse pass** — only for the first product line of a brand; for the next lines go straight to the fine pass from the system preset's value.
2. **Temperature tower.**
3. **Flow, fine pass** at the chosen temperature.
4. **Max volumetric speed** at the chosen temperature and flow.
5. Preset (section 4).

Retraction, if needed, is a separate test after the preset exists.

Every plate is built by `scripts/bbs_calib.py` from a **base project**: a Studio project saved with the target printer, the closest system filament preset, the process preset and the bed type selected (its `Metadata/project_settings.config` supplies all settings; the objects in it are replaced). Later plates need a base that already carries the values chosen so far — the fine flow plate at the chosen temperature, the MVS plate at the chosen temperature and flow (set them in Studio and save the project, or with `scripts/bbs_project.py variant --set key=value`). The script replicates Studio's own calibration wizard (`CalibUtils.cpp`), so the plates are the wizard's, printed as ordinary files: slice the project, send the sliced file to the printer.

The user prints the plate, looks at it and reports in whatever form suits them — a photo, a number, "block 3 looks best", "it goes loose at about 20 mm". The agent turns that report into a value using the mappings below; the user never has to compute anything.

### 3a. Flow ratio — coarse and fine

```
scripts/bbs_calib.py flow1 <base_project.3mf> <out.3mf>            coarse: 9 blocks, -20 … +20 %
scripts/bbs_calib.py flow2 <base_project.3mf> <out.3mf> <coarse>   fine: 10 blocks, -9 … 0 % on top of <coarse> (e.g. 0.95)
```

Flow ratio is how much plastic goes into a line of the required width. Too much — the line is thick and the surface wavy; too little — gaps between the tracks.

Each block is printed with its own `print_flow_ratio` (wizard settings per object: 3 walls, 5 top layers, 1 bottom layer, 35 % infill, monotonic top, no ironing). The number moulded on a block is a **percentage modifier, not a flow ratio**: the ratio of block *k* is `base × (1 + k/100)`, where `base` is the preset's `filament_flow_ratio` for the coarse pass and `<coarse>` for the fine pass. The script prints the plate layout (order back → front, left → right) when it builds the plate — keep that output to map the user's "third block in the second row" to a modifier.

What to look for: the block with a smooth top **without gaps between the lines**; a faintly visible ring from the seam is normal. Too little flow shows as dark grooves between lines, too much as bulging lines with a glossy wave. A value between two neighbouring blocks is allowed. If the best block sits at the edge of the range, shift the base by 0.05 and run the pass again.

Choose the fine pass base so that its −9 … 0 % range brackets the expected value from both sides (example: with a system value of 0.98, a fine pass on a base of 1.02 covers 0.93 → 1.02 in one plate; blocks −5 and −4, 0.969 and 0.979, were even and indistinguishable, −9/−8 had grooves, −2 … 0 bulged → 0.975). The fine pass is worth doing: in another example the coarse pass gave 0 and the fine pass refined it to −2 → 0.98.

**Do not measure wall thickness with calipers.** That measurement catches layer waviness and extrusion scatter, not flow, and is sensitive to the measuring itself. Only the block test.

### 3b. Temperature tower

```
scripts/bbs_calib.py temp <base.3mf> <out.3mf> <tower.stl> <t_hi> <t_lo>
```

`<tower.stl>` is Studio's own wizard tower from its calibration resources: 35 blocks of 10 mm, labelled 350 °C at the bed → 180 °C at the top. The script cuts out the `t_hi … t_lo` blocks (`scripts/mesh_cut.py`; temperatures must be multiples of 5 within 180 … 350) and puts the **hottest block at the bottom**, −5 °C every 10 mm. The temperature steps are written into the project as custom G-code per layer, so Studio's own slice keeps them; the plate itself sets `nozzle_temperature` and `nozzle_temperature_initial_layer` to `t_hi`, so the base needs no particular temperature. Labels are moulded on the back face of each block.

Pick the range from the spool label. Labels often give two bands; the one for the higher print speeds is the relevant one on a Bambu, the lower band is for slow printers (example: a label with "205–215 °C at 50–100 mm/s" and "215–245 °C at 100–230 mm/s" → tower 235 → 200).

What to look for, per block: wall cleanliness and gloss, the stepped overhang ledge, the bridge, stringing between the columns, legibility of the label. The bottom of the range gives cleaner fine detail and less stringing, the top gives better overhangs and stronger layer bonding. The tower prints at the preset's speeds, so the cold blocks under-extrude — that is part of the signal, since real parts will print at those speeds.

**Selection rule: take the upper bound of the acceptable range.** Higher temperature — stronger part and a higher reachable max volumetric speed, that is, faster printing. Not the middle "to be safe". (Example: 200–215 ragged arches and ledges, 220–235 clean, 230 and 235 ledge tips pulled up and hairy → acceptable 220–225 → **225 °C**. Another example, a PLA+: 220 °C.)

Thin hairs on almost every block are not temperature but travels and retraction — a retraction test is separate, if they bother on real parts.

### 3c. Max volumetric speed

```
scripts/bbs_calib.py speed <base.3mf> <out.3mf> <f_lo> <f_hi> [lw lh]        build the plate
<slice out.3mf to out.gcode.3mf>
scripts/bbs_calib.py speed-ramp <out.gcode.3mf> <f_lo> <f_hi> [lw lh]         write the flow ramp into the G-code
```

This is the main limiter of real print speed: the printer itself slows every move that would exceed this flow. The plate is a single-wall spiral-vase cylinder, ⌀40 × 60 mm, with `spiral_mode`, one wall, no top, 0 % infill, layer-time slowdown and overhang slowdown off, and `filament_max_volumetric_speed` raised to 50 so nothing caps the test. `speed` builds the project; after slicing, `speed-ramp` rewrites the feedrate of every extrusion move so that the volumetric flow rises linearly from `f_lo` at z = 2 × layer height (0.4 mm on 0.20 layers) to `f_hi` at the top. **Print that sliced file as-is — do not re-slice it in Studio**, the ramp lives in the G-code.

The optional `lw lh` (line width × layer height, default 0.42 × 0.2) is for high flows: a thicker line keeps the feedrate down (0.6 × 0.28: 40 mm³/s = 238 mm/s), because a 40 mm circle cannot hold much above 300 mm/s.

What to look for: the height of the **first defect** — the wall starts tearing, turns matte and loose, or the surface gloss changes (that change is material degradation, a defect too). Flow at that height:

`flow(h) = f_lo + (f_hi − f_lo) × (h − 0.4) / 59.6` (0.20 layers; `speed-ramp` prints the exact formula for the file)

Example: on a 4 → 30 mm³/s ramp, 10 mm ≈ 8.2, 20 mm ≈ 12.6, 30 mm ≈ 16.9, 40 mm ≈ 21.3, 50 mm ≈ 25.6 mm³/s.

**Selection rule: subtract 10–20 % from the flow at the first defect.** Not "minus one". (Example: a PLA+ went steadily loose from 21 mm = 13 mm³/s at 220 °C → preset 12 — that is −8 %, borderline; at the next recalibration the value should go closer to 11.)

If the cylinder is clean to the very top, the ceiling was not found. Two ways out:

- a second cylinder with a higher ramp — but a file with `f_hi` above 26 mm³/s will not go through Studio (section 5): copy it to the printer's SD card (card reader, FTP, or Bambu Handy) and start it from the printer's screen;
- if the speed gain is not worth that, put −8 … 10 % of the proven-clean point into the preset (example: matte PLA clean to 26 at 225 °C → **24**; a 20 → 40 plate on a 0.6 × 0.28 line was built and skipped, since the gain would have been 5–8 % of print time).

### 3d. Retraction distance — on a stringing symptom only

How far the filament is pulled back between lines — responsible for stringing and clean line starts and ends. `scripts/bbs_calib.py` does not build this plate; use Studio's own test from its Calibration menu (a tower of rings where the retraction distance grows with height).

What to look for: the **first** ring without hairs and blobs, checking at the same time that the seam at that height is clean. Keep the value low: too much retraction gives small holes in the outer wall that look exactly like printing with wet filament. Zero is not allowed.

## 4. From the result to a Studio preset

The result is a **user filament preset** in Bambu Studio: a JSON that `inherits` the closest system preset and carries only the calibrated keys. Only filament keys go in — `nozzle_temperature` (+ `nozzle_temperature_initial_layer`), `filament_flow_ratio`, `filament_max_volumetric_speed`, and if needed fan and bed temperature. Process settings (seam, walls) belong in process presets, not here.

```
scripts/bbs_preset.py filament "<name>" "<inherits>" key=value [key=value ...] [--out dir]
```

Example: a SUNLU PLA+ spool calibrated to 220 °C, flow 0.98, MVS 12 mm³/s on an A1 mini:

```
scripts/bbs_preset.py filament "SUNLU PLA @BBL A1M" "SUNLU PLA+ @BBL A1M" nozzle_temperature=220 filament_flow_ratio=0.98 filament_max_volumetric_speed=12
```

The script writes Studio's own on-disk format: `from: User`, `inherits`, `name`, `filament_settings_id`, `filament_extruder_variant`, and every value as a one-element list (Studio's convention for filament keys); `nozzle_temperature_initial_layer` is copied from `nozzle_temperature` when not given. Studio itself keeps only the keys that differ from the parent (example: with a parent that already had 220 °C and MVS 12, the stored preset ended up holding just `filament_flow_ratio 0.98`).

Naming:

- keep the printer suffix the system presets for your printer carry (`@BBL A1M` on an A1 mini) — Studio filters compatibility by it;
- the name must not coincide with a system preset (example: `SUNLU PLA Matte @BBL A1M` already exists as a system preset, so the user preset for that line was named `SUNLU Matte @BBL A1M`).

Getting it into Studio — either way:

- **Import Configs**: in Studio, File → Import → Import Configs, pick the JSON; the preset then syncs to the Bambu cloud.
- **Drop the file in place with Studio closed**: write `<name>.json` and a `<name>.info` next to it (`sync_info = create`, `user_id`, `base_id = <setting_id of the system preset it inherits>`) into the user filament folder; on the next start Studio creates the preset in the cloud itself and fills in `setting_id`. The folder per platform:
  - macOS `~/Library/Application Support/BambuStudio/user/<id>/filament/`
  - Windows `%APPDATA%\BambuStudio\user\<id>\filament\`
  - Linux `~/.config/BambuStudio/user/<id>/filament/`

Studio reads that folder at start: after writing files there, restart Studio (or use Import Configs instead).

**The preset lives in the Bambu cloud; that folder is a local mirror.** This is the part that surprises: deleting or
renaming a `.json` by hand does nothing lasting, because on the next start Studio syncs the cloud copy back, with its
old name and its old contents. The `.info` beside each preset is the channel for saying otherwise, and it is only read
with **Studio closed**:

| `sync_info` | Effect on next start |
| --- | --- |
| `create` (and an empty `setting_id`) | Studio registers a new preset in the cloud and fills the `setting_id` in |
| `delete` (keeping the existing `setting_id`) | Studio asks the cloud to drop that preset; it stops coming back |
| empty | already in sync, leave it alone |

So **renaming is create + delete, not a file rename**: write the new pair with `sync_info = create` and an empty
`setting_id`, mark the old `.info` `sync_info = delete` with its `setting_id` intact, then start Studio. Renaming the
files alone produced both presets side by side, the old one empty, pulled straight back from the cloud.

**An almost-empty preset file means two opposite things, and telling them apart matters.** Studio stores only what
differs from the parent. A preset inheriting a brand profile that already carries temperature and flow ceiling stores
just the one key that differs, and that is correct. A preset inheriting a `Generic …` profile must carry **every**
calibrated value explicitly, so the same near-empty file there means *not calibrated*. Read the parent before judging.
A calibrated PETG spool once printed for a full day while Studio's own preset was a bare clone of `Generic PETG`: the
prints were correct because the project carries the values in `different_settings_to_system`, but anything asking
Studio which filaments are calibrated answered "none".

Verify by reading the file back **after a restart**, not right after writing it.

Record the values somewhere durable (this skill keeps a table of calibrated filaments with the spool, the values and the date of calibration) and recalibrate when the spool's manufacturer or product line changes.

## 5. Trap: Studio refuses sliced files above ~26–28 mm³/s

Bambu Studio silently does not load a `.gcode.3mf` whose volumetric flow exceeds roughly 26–28 mm³/s: the Preview is empty and the Print plate button is greyed, with no error. The threshold is by **flow, not by feedrate**: a 4 → 30 ramp (357 mm/s) and a 20 → 40 ramp on a 0.6 × 0.28 line (238 mm/s) both opened as an empty plate, a 4 → 26 ramp opened fine.

Workaround: keep `f_hi ≤ 26` on any MVS plate that goes through Studio. To test above that, copy the sliced file to the printer's SD card (card reader, FTP, or Bambu Handy) and start it from the printer's screen — such files print from SD without issue.
