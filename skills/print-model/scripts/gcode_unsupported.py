#!/usr/bin/env -S uv run --quiet --with numpy python3
# /// script
# dependencies = ["numpy"]
# ///
"""What is printed over air, and how far it reaches before it finds something to stand on — forecast checks 3
and 4 measured against the layers below instead of against a feature label.

Two numbers the slicer's own labels do not give:

* **True span.** A `Bridge` extrusion that runs 100 mm across thirty ribs is not a 100 mm bridge: it is anchored
  every few millimetres. `gcode_features.py` reports the longest single extrusion, which is an upper bound only.
  Here every extrusion is sampled, each sample is tested against the material below, and the spans reported are
  runs of consecutive unsupported samples — the distance the plastic actually has to cross.
* **Feature starting in mid-air.** A part that appears with nothing beneath it (a clip, a tab, a boss on a wall)
  is a cantilever, not an overhang: it is anchored along one short edge and hangs from there. The slicer plans
  support for it, so nothing is wrong until a support blocker, a raised support threshold or
  `support_on_build_plate_only` takes that support away — and then no feature label changes. Run this over the
  z range of any blocker you add.

Material a few layers down counts as support: an interface sits `support_top_z_distance` under the part, which
the slicer rounds up to whole layers, so the nearest material below a properly supported overhang is two or
three layers away — the depth is read from the G-code header (`--lookback` overrides). Support features
themselves are not tested: tree branches are printed over air by design.

Reads a sliced Bambu G-code. Reports per layer: share of sampled material over air, its xy extent, the longest
unsupported run along x and along y, a class, and the features involved. Classes: `over infill` — the layer
below is sparse infill there (the first solid layer over infill; harmless, spans equal the infill cell);
`bridging` — short runs both ways, rib-to-rib gaps; `cantilever` — several millimetres along one axis with a
fraction along the other, anchored on one edge only: the one that needs support or a design change.

Usage: gcode_unsupported.py <plate.gcode> [--layers A:B] [--min-share 2] [--cell 0.5] [--lookback N] [--all]
       gcode_unsupported.py <plate.gcode> --layer 208          one layer with its neighbours
"""
import os, re, sys

CELL = 0.5          # occupancy grid, mm
SAMPLE = 0.3        # extrusion sampling step, mm
NEIGHBOURS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def lookback(path, default=2):
    """How many layers below still count as support: the slicer leaves `support_top_z_distance` between the
    interface and the part, rounded up to whole layers, so the nearest material under a supported overhang sits
    two or three layers down. Reading it from the header keeps the check honest on any profile."""
    import math
    head = {}
    for line in open(path, errors="replace"):
        if line.startswith("; ") and " = " in line:
            k, v = line[2:].split(" = ", 1); head[k.strip()] = v.strip()
        elif line.startswith("; EXECUTABLE_BLOCK_START"): break
    try:
        gap = float(head["support_top_z_distance"]); lh = float(head["layer_height"])
        return max(default, math.ceil(gap / lh) + 1)
    except (KeyError, ValueError, ZeroDivisionError):
        return default


def layers(path):
    """-> [(layer number, z, [(x, y, feature), ...])]"""
    import numpy as np
    out = []; cur = None; feat = None; x = y = 0.0; z = 0.0
    for line in open(path, errors="replace"):
        if line.startswith("; Z_HEIGHT:"):
            try: z = float(line.split(":")[1])
            except ValueError: pass
            continue
        if line.startswith("; layer num/total_layer_count:"):
            cur = (int(line.split(":")[1].split("/")[0]), z, []); out.append(cur); continue
        if line.startswith("; FEATURE: "): feat = line[11:].strip(); continue
        if cur is None or line[:3] not in ("G1 ", "G2 ", "G3 ", "G0 "): continue
        mx = re.search(r"X([-\d.]+)", line); my = re.search(r"Y([-\d.]+)", line); me = re.search(r"E([-\d.]+)", line)
        nx = float(mx.group(1)) if mx else x; ny = float(my.group(1)) if my else y
        if me and float(me.group(1)) > 0 and (mx or my):
            n = max(2, int(((nx - x) ** 2 + (ny - y) ** 2) ** 0.5 / SAMPLE) + 1)
            for t in np.linspace(0, 1, n):
                cur[2].append((x + t * (nx - x), y + t * (ny - y), feat))
        x, y = nx, ny
    return [(n, zz, pts) for n, zz, pts in out if pts]


def runs(values, gap=1.2):
    import numpy as np
    v = np.sort(np.asarray(values))
    return [r.max() - r.min() for r in np.split(v, np.where(np.diff(v) > gap)[0] + 1)]


def analyse(pts, below_layers, cell=CELL):
    """-> None when nothing is over air, else dict(share, box, run_x, run_y, cls, feats)"""
    import numpy as np
    below = {}
    for bl in below_layers:                       # nearest layer last, so its feature label wins
        for px, py, f in bl: below[(int(px // cell), int(py // cell))] = f
    model = [(px, py, f) for px, py, f in pts if not (f or "").startswith("Support")]
    if not model: return None
    free = [(px, py, f) for px, py, f in model
            if not any((int(px // cell) + dx, int(py // cell) + dy) in below for dx, dy in NEIGHBOURS)]
    if not free: return None
    F = np.array([[p[0], p[1]] for p in free]); x0, y0 = F.min(0); x1, y1 = F.max(0)
    rows, cols = {}, {}
    for px, py, _ in free:
        rows.setdefault(int(py // cell), []).append(px); cols.setdefault(int(px // cell), []).append(py)
    rx = max(r for v in rows.values() for r in runs(v)); ry = max(r for v in cols.values() for r in runs(v))
    feats = {}
    for _, _, f in free: feats[f] = feats.get(f, 0) + 1
    under = [f for (cx, cy), f in below.items() if x0 - 2 <= cx * cell <= x1 + 2 and y0 - 2 <= cy * cell <= y1 + 2]
    infill = sum(1 for f in under if f == "Sparse infill") / len(under) if under else 0.0
    long_, short = max(rx, ry), min(rx, ry)
    if infill > 0.5: cls = "over infill"
    elif long_ >= 3.0 and long_ >= 3 * max(0.1, short): cls = "cantilever"
    else: cls = "bridging"
    return dict(share=100.0 * len(free) / len(model), box=(x0, y0, x1, y1), run_x=rx, run_y=ry, cls=cls, feats=feats)


def report(path, lo=None, hi=None, min_share=2.0, cell=CELL, show_all=False, back=None):
    L = layers(path); back = back or lookback(path)
    print(f"{os.path.basename(os.path.dirname(os.path.abspath(path)))}: {len(L)} layers, sampling {SAMPLE} mm, grid {cell} mm, support gap {back} layers")
    flagged = 0
    for i in range(1, len(L)):
        n, z, pts = L[i]
        if lo is not None and not (lo <= n <= hi): continue
        r = analyse(pts, [L[j][2] for j in range(max(0, i - back), i)], cell)
        if r is None:
            if show_all: print(f"L{n:<4} z{z:6.2f}  nothing over air")
            continue
        if r["share"] < min_share and not show_all: continue
        flagged += 1
        x0, y0, x1, y1 = r["box"]; top = ", ".join(f"{k} {v}" for k, v in sorted(r["feats"].items(), key=lambda t: -t[1])[:3])
        print(f"L{n:<4} z{z:6.2f}  over air {r['share']:4.1f} %  x {x0:6.1f}..{x1:6.1f}  y {y0:6.1f}..{y1:6.1f}"
              f"  run x {r['run_x']:5.1f} mm  run y {r['run_y']:5.1f} mm  {r['cls']:11s} {top}")
    if not flagged and not show_all: print(f"nothing over {min_share} % of a layer is printed over air")


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__.strip(), file=sys.stderr); sys.exit(1)
    path = a[0]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    lo = hi = None
    if "--layer" in a:
        n = int(a[a.index("--layer") + 1]); lo, hi = n - 1, n + 1
    elif "--layers" in a:
        s = a[a.index("--layers") + 1]; lo, hi = (int(v) for v in s.split(":"))
    report(path, lo, hi, opt("--min-share", 2.0), opt("--cell", CELL), "--all" in a or lo is not None, opt("--lookback", 0) or None)


if __name__ == "__main__":
    main()
