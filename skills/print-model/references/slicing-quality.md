# Clean walls: what spoils them and what fixes them

Based on Factorian Designs, "Almost Nobody Uses This Slicer Setting", verified by slicing on a Bambu Lab A1 mini. The numbers in the tables below are those measurements, not figures from the video.

## The key pair

The nozzle path is built from the triangle mesh, not from the original CAD geometry. How closely it follows that mesh is decided by two keys — and they only work together.

- **`resolution`** — the contour approximation tolerance. Larger → longer, coarser segments. Bambu default **0.012**, working value **0.004**.
- **`slice_closing_radius`** — closes gaps smaller than 2× the value while slicing. Needed for broken meshes, but it lowers final accuracy and **masks** a lower `resolution`: change one and see no effect, because the other smooths everything anyway. Bambu default **0.049**, working value **0.01**.

The symptom this pair removes: walls that do not line up between layers here and there, short rough stretches, extra lines on inner surfaces — with a sound mesh, dry calibrated filament and correct PA. From the outside the part may look fine: it shows most on inner walls and under harsh top light.

**Lower bound — 0.003.** Below that the printer cannot keep up with the stream of tiny commands: it skips extrusions (voids in the wall, visible on a break) or stalls and leaves "pimples". The risk grows with print speed; on a filament with a low max volumetric speed it is below average (example: a PLA+ calibrated to MVS 12 mm³/s already caps the real wall speed).

## The cost (measured on a Bambu Lab A1 mini)

| Model | 0.012 / 0.049 | 0.004 / 0.01 | Difference |
| --- | --- | --- | --- |
| Box (flat, fillets) | 644 KB, 13 843 G1, 37:30 | 664 KB, 14 565 G1, 37:28 | none |
| Duck (organic, 0.20) | 27 MB, 589 k G1, 2:58:24 | 35 MB, 741 k G1, 2:59:01 | +37 s, +30 % file size |

Accuracy is practically free — so it is set always, not "when it matters".

## Arc fitting: leave it on

The common advice "turn arc fitting off on Bambu and Klipper, it gets in the way of the internal planner" is **not adopted**. Measured on the duck (0.004/0.01):

| | File | G1 | Arcs | Time |
| --- | --- | --- | --- | --- |
| `enable_arc_fitting = 1` | 35 MB | 741 k | 339 k | 2:59:01 |
| `enable_arc_fitting = 0` | 49 MB | **1.77 M** | — | **3:09:56** |

Turning it off gives 2.4× more commands and +11 minutes, that is, it pushes straight into the overload regime that causes skipped extrusions in the first place. The claim is about quality and cannot be checked by slicing — if a concrete suspicion ever appears, compare by printing two identical parts, not by file size.

## Mesh

- From CAD export **STL directly** rather than feeding the slicer STEP: the built-in converter lays large flat triangles on organic and curved surfaces — on the print these become facets where there should be smoothness. On simple geometry the difference is almost nil, on filleted geometry it is large.
- Visual check (wireframe): round looks round, small triangles on fillets; flat areas need only a couple. Looks faceted — needs more triangles.
- The advice "keep the face count low" is outdated: a modern machine handles a dense mesh. Growing it endlessly is pointless too — once the curves are smooth, more adds nothing.
- Gap closing masks holes, it does not fix them. A broken mesh (holes, non-manifold) is fixed in CAD or a mesh editor, not by raising `slice_closing_radius`.

## Symptom → where to look

| What you see | First suspect |
| --- | --- |
| Walls not lining up, short rough stretches, extra lines on inner surfaces | `resolution` / `slice_closing_radius` — **both, always** |
| Faceted fillets, a "polygon" instead of a circle | mesh: STEP import or a coarse STL export |
| Voids, missing pieces of wall, "pimples" on a fast print | `resolution` pushed too low (< 0.003) or arc fitting turned off |
| Stair-stepping on organic shapes | layer height, not line width: 0.12 instead of 0.20 |
| Ripple on flat vertical walls | outer wall speed — the `High Quality` process preset (60 mm/s) |
| A band on the wall at the height of an inner floor or shelf | the "floor line" — `symptoms-and-fixes.md` §1 |
| A locally dirty or weak patch, stringing at the seam | tiny gap-fill extrusions — `symptoms-and-fixes.md` §2 |
| The whole part is rough, layers uneven with correct settings | filament: wet or uncalibrated → `filament-calibration.md` |

Order of diagnosis: first make sure the filament is dry and calibrated and the mesh is sound, and only then turn slicing keys — otherwise you treat the consequence.
