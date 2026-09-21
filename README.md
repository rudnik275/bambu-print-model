# bambu-print-model

A Claude Code plugin that prepares a model for printing on a Bambu Lab printer — the way an experienced printer would, not the way the default profile does.

Give Claude a model (STL, 3MF, STEP, a MakerWorld project) and say what you want. It asks two things — which of your filaments, and what matters more this time (fast, good-looking, strong) — then decides orientation, presets, walls, supports, brims, seams, whether to split the model over several plates, runs a 16-check print forecast (bridges, overhangs, floor lines, stair-steps, first-layer stability, thermal issues on thin tops…), and hands you a sliced `.gcode.3mf` that opens in Bambu Studio in Preview with **Print plate** ready. You press the button.

The value is in the accumulated experience: which settings suit which kind of model, how to split an assembly, where a print will fail and what fixes it. It grows with every print.

## Install

```
/plugin marketplace add rudnik275/bambu-print-model
/plugin install bambu-print-model@bambu-print-model
```

Updates: `/plugin marketplace update`, then reinstall or update the plugin.

Requirements: [Bambu Studio](https://bambulab.com/en/download/studio) (its command-line slicer is used for checking and export), [Claude Code](https://claude.com/claude-code), Python 3 and [uv](https://docs.astral.sh/uv/) (a few scripts pull their own dependencies through it). macOS paths are the defaults; on Windows or Linux set `BAMBU_STUDIO_CLI` and `BAMBU_STUDIO_DATA` (see `skills/print-model/scripts/paths.py`). If something is missing, Claude will tell you what.

## First print

1. Load your filament and say: *"print this: `~/Downloads/model.stl`"* (or a MakerWorld 3MF, a STEP from Fusion, a folder of STLs).
2. Claude asks which filament preset to use and what matters more (fast / quality / strength). Answer in a sentence.
3. If none of your filaments is calibrated yet, Claude says so, explains what a generic preset costs you, and offers to calibrate first (`references/filament-calibration.md`) — you may still print on the generic preset.
4. Claude builds the project, slices it with the Studio CLI, reports the forecast (what will be bad, where, why, and what would fix it), and opens the sliced file in Bambu Studio. Press **Print plate**.

Several plates (an assembly, several materials) are handed over one at a time: Bambu printers have no print queue.

## What is inside

- `skills/print-model/SKILL.md` — the procedure: get the model, assess it, choose presets, apply the quality package, check and forecast, hand over, record.
- `references/model-playbook.md` — what kind of model → how to prepare it (boxes, rounded shells with lips, grilles, bezels, legs and pins, organic figures, whistles, snap-fits, MakerWorld projects, prototype passes).
- `references/symptoms-and-fixes.md` — symptom → cause → Bambu Studio setting.
- `references/forecast.md` — the 16 checks, thresholds, severity words and levers.
- `references/slicing-quality.md` — resolution, arc fitting, mesh quality, measured costs.
- `references/filament-calibration.md` — why and how to calibrate a spool, and how the result becomes a Studio preset.
- `scripts/` — the tools: check a sliced plate for material printed over air (`gcode_unsupported.py`), build and modify Studio projects without the GUI (`bbs_project.py`: retarget a MakerWorld project to your printer, variants, height-range modifiers, sliced-only export; `bbs_blocker.py`: support blockers; `step2stl.py`; `bbs_calib.py`: calibration plates), read a project (`bbs_current.py`, `bbs_resolve.py`), and analyse a sliced plate (`gcode_forecast.py`, `gcode_features.py`, `gcode_layers.py`, `gcode_compare.py`, `gcode_airtravel.py`, `mesh_slopes.py`).

Your own data — calibrated filament presets, the start-G-code snapshot of your printer, your print log — lives with you (`~/.print-model/` and Bambu Studio's user presets), not in the plugin.

## Contributing experience

Every print ends with "forecast vs. reality". When a threshold, a lever or a playbook rule turns out wrong on your printer, open an issue or a pull request with the numbers. Rules without measurements are not accepted.

MIT.
