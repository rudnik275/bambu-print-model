#!/usr/bin/env python3
"""What prints where: per-layer extrusion by feature type from a sliced Bambu G-code, for the print forecast.

  gcode_features.py <plate.gcode>                      summary: bridges (span), overhang walls, gap fill,
                                                        support interface, tiny extrusions — with layers/heights
  gcode_features.py <plate.gcode> <from> <to> [regex]  per-layer rows for layers from..to (feature filter)

Bridge span: the real span is the longest single extrusion through air, NOT the bounding box of the bridge
region — a 9 x 37 mm patch is bridged across its short side, and reading the box as the span turns a 22 mm
bridge into a fake "37 mm". The summary prints both (max span, and the region box in brackets).
Arcs (G2/G3) are counted as extrusions: enable_arc_fitting turns smooth walls into arcs and `resolution`
changes how much of a contour becomes arcs — skipping them undercounts walls and inflates the gap-fill share
by a different amount in each slice, so a comparison across a resolution change would read backwards."""
import re, sys
from collections import defaultdict

def parse(path):
    """-> {(layer, feature): [xmin, ymin, xmax, ymax, E, segments, tiny_segments, longest_segment]}, heights {layer: z}"""
    L = 0; feat = None; x = y = 0.0; acc = {}; z = {}; zpend = 0.0
    for line in open(path, errors="replace"):
        if line.startswith("; Z_HEIGHT:"):                      # comes just before the layer-number line
            try: zpend = float(line.split(":")[1])
            except ValueError: pass
            continue
        if line.startswith("; layer num/total_layer_count:"):
            L = int(line.split(":")[1].split("/")[0]); z[L] = zpend; continue
        if line.startswith("; FEATURE: "):
            feat = line[11:].strip(); continue
        if feat is None or line[:3] not in ("G1 ", "G0 ", "G2 ", "G3 "): continue
        mx = re.search(r"X([-\d.]+)", line); my = re.search(r"Y([-\d.]+)", line); me = re.search(r"E([-\d.]+)", line)
        nx = float(mx.group(1)) if mx else x; ny = float(my.group(1)) if my else y
        if me and float(me.group(1)) > 0 and (mx or my):
            a = acc.setdefault((L, feat), [1e9, 1e9, -1e9, -1e9, 0.0, 0, 0, 0.0])
            a[0] = min(a[0], nx); a[1] = min(a[1], ny); a[2] = max(a[2], nx); a[3] = max(a[3], ny)
            a[4] += float(me.group(1)); a[5] += 1
            d = ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
            if d < 1.0: a[6] += 1                                          # segment shorter than 1 mm
            if d > a[7]: a[7] = d                                          # longest single extrusion
        x, y = nx, ny
    return acc, z

def rows(acc, z, lo, hi, pat=None):
    for (l, f), a in sorted(acc.items()):
        if lo <= l <= hi and (pat is None or re.search(pat, f, re.I)):
            print(f"L{l:<4} z{z.get(l, 0):6.2f} {f:<22} x {a[0]:6.1f}..{a[2]:6.1f}  y {a[1]:6.1f}..{a[3]:6.1f}  E {a[4]:7.2f}  seg {a[5]:5d} tiny {a[6]:4d}")

def summary(acc, z):
    by = defaultdict(list)
    for (l, f), a in acc.items(): by[f].append((l, a))
    total_e = sum(a[4] for a in acc.values()) or 1.0
    print(f"layers: {max(l for l, _ in acc)}   total E {total_e:.0f} mm\n")
    for f in ["Bridge", "Overhang wall", "Gap infill", "Support interface", "Support", "Top surface"]:
        items = sorted(by.get(f, []))
        if not items: print(f"{f:<18} —"); continue
        e = sum(a[4] for _, a in items); ls = [l for l, _ in items]
        line = f"{f:<18} E {e:7.1f} ({100 * e / total_e:4.1f} %)  layers {len(ls)}  z {z.get(ls[0], 0):.1f}..{z.get(ls[-1], 0):.1f}"
        if f == "Bridge":
            # longest single extrusion through air = the span; the region's bounding box is only context (module docstring)
            l, a = max(items, key=lambda t: t[1][7])
            box = max(a[2] - a[0], a[3] - a[1])
            line += f"  max span {a[7]:.1f} mm @ L{l} z{z.get(l, 0):.1f} (region box {box:.1f} mm)"
        if f == "Gap infill":
            tiny = sum(a[6] for _, a in items); seg = sum(a[5] for _, a in items)
            worst = sorted(items, key=lambda t: -t[1][6])[:3]
            line += f"  tiny {tiny}/{seg} seg; worst L" + ", L".join(f"{l}(z{z.get(l, 0):.1f}:{a[6]})" for l, a in worst)
        print(line)
    # contour events on the outer wall: a one-layer jump in segment count = wall printed across an opening
    # (the slicer does not call it a bridge); a lasting jump with an E drop = contour splits (opening starts)
    ow = {l: a for l, a in by.get("Outer wall", [])}
    events = []
    for l in sorted(ow):
        p, n = ow.get(l - 1), ow.get(l + 1)
        if not p: continue
        if ow[l][5] >= 1.5 * p[5] and n and n[5] < 0.8 * ow[l][5]:
            events.append(f"L{l} z{z.get(l, 0):.1f}: wall across an opening ({ow[l][5]} seg vs {p[5]})")
        elif ow[l][5] >= 1.4 * p[5] and ow[l][4] < 0.9 * p[4]:
            events.append(f"L{l} z{z.get(l, 0):.1f}: contour splits ({p[5]}->{ow[l][5]} seg, E {p[4]:.1f}->{ow[l][4]:.1f})")
    print("\nOuter wall events    " + ("; ".join(events) if events else "—"))

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    acc, z = parse(sys.argv[1])
    if len(sys.argv) >= 4: rows(acc, z, int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
    else: summary(acc, z)
