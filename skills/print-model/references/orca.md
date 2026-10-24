# OrcaSlicer instead of Bambu Studio

Bambu Studio stays the default. Read this when the user slices in OrcaSlicer. Measured on Orca 2.4.2 against Studio 02.08.02.61, A1 mini, SUNLU PLA; what Orca 2.5 changed is in its own section below. Steps 1–5 of the skill apply unchanged, and so do the forecast scripts on Orca's G-code. One label differs: Orca calls the first solid layer over infill `Internal Bridge`, a separate feature from `Bridge`.

## Presets

`scripts/orca.py presets` turns every Studio user preset into an Orca user preset with the same values:
- **Parity keys.** Orca ships same-named system presets, but a few defaults differ: the 0.20 process uses crosshatch infill where Studio uses grid, and filaments use different `close_additional_fan_first_x_layers`. The script carries Studio's value wherever the two system parents disagree.
- **`version` key.** It writes one; Orca silently skips a user preset without it.
- **Out-of-range values.** It replaces values Orca refuses: `tree_support_wall_count = -1` is Studio's "auto", outside Orca's 0..2.
- **Restart.** Orca reads presets only at start.
- **Renamed key.** The quality package's `no_slow_down_for_cooling_on_outwalls` is `dont_slow_down_outer_wall` in Orca; the script translates it in `presets` and in `--set`. Slicing from Orca's GUI, put it in the filament preset: on a 50 mm bin the 17 wall layers between the floor and the top shell fell under the 6 s layer time and the outer wall dropped 200 → 145 mm/s there, a visible band with a step at each edge; with the key on, the inner wall and gap fill take the stretch (300 → 107 mm/s), layer time and total time unchanged.

Machine G-code is no problem in Orca. Its system machine presets carry the real Bambu start and end blocks (21 × `M1002` in the A1 mini start in 2.4.2, 25 in 2.5), so no snapshot is needed. `slice` prints the start block's count: 0 there means a placeholder start.

## The same number means a different bridge

| | Studio | Orca, thin bridge (default) | Orca, `thick_bridges = 1` |
| --- | --- | --- | --- |
| thread at `bridge_flow 1.6` | round, d = 0.4·√1.6 = 0.506 | flat 0.4 × 0.2 strip × 1.6 | round, d = 0.4·√1.6 |
| cross-section, spacing (measured) | 0.203 mm², 0.558 mm | 0.114 mm², 0.357 mm | 0.201 mm², 0.556 mm |

- **Thick bridges.** A `bridge_flow` calibrated in Studio keeps its meaning in Orca only with `thick_bridges = 1`. A thin Orca bridge at the same value lays half the plastic.
- **Internal bridges.** Orca's internal bridge reuses the bridge thread and **multiplies** it by `internal_bridge_flow`, so it is not an independent flow. Overhang walls take the same thread × `overhang_flow_ratio` (which acts only with `set_other_flow_ratios = 1`). Setting both to `1 / bridge_flow` returns them to the plain d0.4 thread: measured 0.126 mm² for the internal bridge and 0.124 mm² for overhang walls, against Studio's 0.130 for overhang walls.
- **Internal bridge speed.** `internal_bridge_speed` defaults to 150 % of `bridge_speed`. Under slow visible bridges (10 mm/s) that is 15 mm/s; give it 50 mm/s, the speed Studio's system presets use for every bridge.

The presets command writes all of this.

**Why internal bridges need their own settings.** Studio 2.8 has one `bridge_speed`/`bridge_flow` for both kinds, and the slow, thick setting that makes open spans flat fails over sparse infill:

| | Open-span calibration plate | Internal bridge over 10 % gyroid |
| --- | --- | --- |
| line length, median | 32 mm | 6 mm |
| anchor | 1.1 mm on solid | 0.6 mm on a 0.45 mm gyroid wall |
| line ends over nothing | 0 % | 11–14 % |
| turnarounds in the air | 0 % | 12 % |

The result over gyroid: heavy strands sagging into the cells and a comb of loops along the wall where unanchored ends curl. Moving internal bridges to 50 mm/s on a 6-hour part cut them from 40 min to 7 min.

## What Orca does that Studio 2.8 does not

- **Scarf seam works.** With `seam_slope_type = external` and `seam_slope_conditional = 1` (Orca's defaults: 155°, 20 mm, 10 steps), an R15 cylinder got sloped outer-wall moves on 49 of 50 layers. A part with a sharp corner in every section kept a plain seam in the corner. In Studio the same keys reached only the G-code header.
- **More keys.** `wipe_on_loops` (an inward wipe at the end of a closed loop) and `filament_shrinkage_compensation_z` exist.
- **More calibrations.** Orca's calibration menu has tests Studio's lacks (VFA, cornering, input shaping, tolerance), and its temperature tower takes any range.

## Slicing

`scripts/orca.py slice <out dir> <model> --machine M --process P --filament F [--set key=value ...]`.
- **Full configs (2.4).** Orca 2.4's CLI takes the settings files as complete configs and does not follow `inherits`, so the script resolves the presets first. Orca 2.5 resolves them itself — below.
- **Projects the GUI keeps.** A CLI-exported project carries `different_settings_to_system = ['', '', '']`, and Orca's GUI then resets every key to the system preset when it opens the project. The script fills the list (`orca.py fix-project` does it for any such file). After that, the project's only "unsaved change" against its preset is what was `--set`.
- **Modifiers from the CLI.** A modifier part (a mesh listed as `subtype="modifier_part"` in `model_settings.config`, its keys as `<metadata>`) is honoured by the CLI and kept by the GUI. A height-range modifier (`layer_config_ranges.xml`) crashes Orca 2.4.2's CLI with signal 11 and nothing in the log. The modifier is what a small feature needs once the outer wall is exempt from the cooling slowdown: a 17 × 8 mm tab on that bin went from 5.8 to 2.7 s per layer; a modifier over it with `outer_wall_speed = 20` gave the layers back, the speed change sits on the body's top edge where it cannot show.
- **First launch on macOS.** A freshly installed Orca must be opened once from Finder or `open -a` before using the CLI. While the "downloaded from the internet" prompt is pending, the CLI hangs silently.
- **Forecast inputs.** The CLI writes `result.json` on Linux only; `slice` writes one from the G-code (object boxes between the object labels, arcs included) so that `gcode_forecast.py` runs as after a Studio slice. Slicer warnings are in the project's `slice_info.config`, which the forecast reads anyway — on a PLA preset with a 60 °C smooth-plate bed Orca warns `bed_temperature_too_high_than_filament` (over the 54 °C vitrification of SUNLU PLA Matte), a warning meant for enclosed printers.

## Orca 2.5

Orca 2.5.0-alpha changed how the CLI gets its presets. `orca.py` notices it by itself — a `<vendor>.opc` file in Orca's `system/` folder — and switches; `ORCA_NATIVE=0` forces the 2.4 path.
- **No JSON profiles.** The app ships each vendor as one binary cache, `BBL.opc`, holding every preset in source form: its own keys, its parent and the presets it includes. There is no `BBL.json` to resolve against any more.
- **`include`.** A Bambu machine preset no longer holds its G-code: `Bambu Lab A1 mini 0.4 nozzle` includes five `… template machine_start_gcode` / `machine_end_gcode` / `layer_change_gcode` / `time_lapse_gcode` / `change_filament_gcode` presets, and 1393 process and filament presets include templates too. Following `inherits` alone ends in `fdm_machine_common`, whose start is a placeholder: `M109 S205`, a purge line at x 10, no `M1002` before the first layer — and still hundreds of `M1002` in the whole file from the layer-change and end blocks, so only the start block's count exposes it.
- **Presets are resolved by the CLI, by identity.** For a `--load-settings` file with a parent, the CLI looks for the preset its bundle loaded *from that file* and takes that preset's resolved config instead of the file's contents; any other file is refused ("Preset was not found in the loaded bundle"). So `slice` builds a scratch data dir — Orca's `system/` caches plus copies of the chosen user presets, a system preset as a one-line user stand-in that inherits it — and hands the CLI those files. The exported project names the stand-in's system preset again, with an empty `inherits_group` entry, as the GUI saves it.
- **`--set` goes on the command line.** Every config key is a CLI option, `--key-with-dashes=value` (`--enable-support=1`, booleans included); the CLI applies it last and records it in `different_settings_to_system` itself, in the column of the preset kind that owns the key. Underscores are refused ("Invalid option").
- **User presets: the newest copy.** Orca keeps `user/default/` and one folder per signed-in account; a stale `default/` copy of a filament preset still had 210 °C where the account's, edited a week later, had 225. `slice` takes the newest file.
- **`presets`.** The Orca parent comes from the CLI (`--export-settings` with a stand-in, 0.2 s per parent), the `version` key from the stamp at the head of `BBL.opc`. Parity compares values, not spellings: the resolved config writes `1` and `100%` where Studio's JSON has `1.0` and `100`. On 2.5.0-alpha the only real disagreements left on `0.20mm Standard @BBL A1M` are `support_ironing_pattern` and `tree_support_wall_count`; the 0.20 process uses grid infill like Studio's.
- **Same G-code.** A Gridfinity bin with a support blocker and a 0.08 mm height range sliced through the native path and through the flattened configs: 4 h 26 min 17 s and 228 layers both times. The height-range modifier that crashed 2.4.2's CLI slices in 2.5.

## Sending to the printer

Printers on Bambu's authorization firmware accept jobs from Orca only in **LAN Only Mode + Developer Mode** (printer screen: LAN Only Mode → Developer Mode). That disconnects the cloud: no Bambu Handy or remote start. Without it there are two routes:
- **Through Studio:** export the sliced `.gcode.3mf`, strip it with `bbs_project.py gcode3mf` and send it from Bambu Studio. Studio opens Orca's G-code as a sliced file. Its own time estimate for it is wrong (days instead of hours); the printer uses the file's `M73` lines.
- **Through Bambu Connect.**

Orca also needs three things to see the printer:
- **Bambu's network plug-in.** Orca offers to download it and needs its own version (02.03.00.62 for Orca 2.4.2), not Studio's newer one.
- **UDP port 2021 free.** Studio and Orca both bind it for printer discovery, so with Studio running Orca finds no printer.
- **Local network permission on macOS.** Orca must be allowed to find devices on the local network.

With Developer Mode on, the LAN access code is the only credential, so keep it out of chats and screenshots.
