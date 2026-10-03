# OrcaSlicer instead of Bambu Studio

Bambu Studio stays the default. Read this when the user slices in OrcaSlicer. Measured on Orca 2.4.2 against Studio 02.08.02.61, A1 mini, SUNLU PLA. Steps 1–5 of the skill apply unchanged, and so do the forecast scripts on Orca's G-code. One label differs: Orca calls the first solid layer over infill `Internal Bridge`, a separate feature from `Bridge`.

## Presets

`scripts/orca.py presets` turns every Studio user preset into an Orca user preset with the same values:
- **Parity keys.** Orca ships same-named system presets, but a few defaults differ: the 0.20 process uses crosshatch infill where Studio uses grid, and filaments use different `close_additional_fan_first_x_layers`. The script carries Studio's value wherever the two system parents disagree.
- **`version` key.** It writes one; Orca silently skips a user preset without it.
- **Out-of-range values.** It replaces values Orca refuses: `tree_support_wall_count = -1` is Studio's "auto", outside Orca's 0..2.
- **Restart.** Orca reads presets only at start.

Machine G-code is no problem in Orca. Its system machine presets carry the real Bambu start and end blocks (21 × `M1002` in the A1 mini start), so no snapshot is needed.

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
- **Full configs.** Orca's CLI takes the settings files as complete configs and does not follow `inherits`, so the script resolves the presets first.
- **Projects the GUI keeps.** A CLI-exported project carries `different_settings_to_system = ['', '', '']`, and Orca's GUI then resets every key to the system preset when it opens the project. The script fills the list (`orca.py fix-project` does it for any such file). After that, the project's only "unsaved change" against its preset is what was `--set`.
- **First launch on macOS.** A freshly installed Orca must be opened once from Finder or `open -a` before using the CLI. While the "downloaded from the internet" prompt is pending, the CLI hangs silently.

## Sending to the printer

Printers on Bambu's authorization firmware accept jobs from Orca only in **LAN Only Mode + Developer Mode** (printer screen: LAN Only Mode → Developer Mode). That disconnects the cloud: no Bambu Handy or remote start. Without it there are two routes:
- **Through Studio:** export the sliced `.gcode.3mf`, strip it with `bbs_project.py gcode3mf` and send it from Bambu Studio. Studio opens Orca's G-code as a sliced file. Its own time estimate for it is wrong (days instead of hours); the printer uses the file's `M73` lines.
- **Through Bambu Connect.**

Orca also needs three things to see the printer:
- **Bambu's network plug-in.** Orca offers to download it and needs its own version (02.03.00.62 for Orca 2.4.2), not Studio's newer one.
- **UDP port 2021 free.** Studio and Orca both bind it for printer discovery, so with Studio running Orca finds no printer.
- **Local network permission on macOS.** Orca must be allowed to find devices on the local network.

With Developer Mode on, the LAN access code is the only credential, so keep it out of chats and screenshots.
