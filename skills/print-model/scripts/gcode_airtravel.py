#!/usr/bin/env -S uv run --quiet --with pillow python3
# /// script
# dependencies = ["pillow"]
# ///
"""Travel moves through air *inside* the part — string candidates in cavities (whistle windows and
windways, channels, closed chambers). `reduce_crossing_wall` only avoids crossing walls; a notch or a
window is open air, so the slicer hops straight across it. Every such hop at printing temperature is a
possible string, and inside a whistle a string sits in the air-jet path.

Usage: gcode_airtravel.py <plate.gcode> [--bands z0:z1:label,...] [--png out.png z1,z2,...]

Per height band: layers, retractions per layer, in-part travels that cross air per layer and their length
in air, totals. A travel "crosses air" when >= 2 of its 0.5 mm samples fall farther than 0.8 mm from every
extrusion of the same layer (rasterised at 0.25 mm). Travels leaving the part's bounding box (+2 mm) are
ignored — Bambu's timelapse block parks at X0 every layer even when timelapse is off (M622-conditional).
Arcs G2/G3 are counted. This is forecast check 16 (references/forecast.md).

Scale, from a six-window whistle: 0.12 mm layers gave ~830 hops / 3.4 m of air travel, 0.08 mm ~1440 hops
/ 5.6 m — about 4 hops per layer across the windows either way; the print whistled weakly with strings inside.
Needs Pillow (the shebang lets uv fetch it; or `uv run gcode_airtravel.py ...`)."""
import re, math, sys

def parse(path):
    layers = []; cur = None; feat = None; x = y = None
    for line in open(path, errors="ignore"):
        if line.startswith("; CHANGE_LAYER"):
            cur = {"z": None, "ext": [], "trav": [], "retr": 0, "feats": {}}; layers.append(cur); continue
        if cur is None: continue
        if line.startswith("; Z_HEIGHT:"): cur["z"] = float(line.split(":")[1]); continue
        if line.startswith("; FEATURE:"): feat = line.split(":", 1)[1].strip(); continue
        if line[:3] not in ("G1 ", "G2 ", "G3 "): continue
        mx = re.search(r" X(-?[\d.]+)", line); my = re.search(r" Y(-?[\d.]+)", line); me = re.search(r" E(-?[\d.]+)", line)
        e = float(me.group(1)) if me else None
        if e is not None and e < 0 and not mx and not my: cur["retr"] += 1; continue
        nx = float(mx.group(1)) if mx else x; ny = float(my.group(1)) if my else y
        if (mx or my) and x is not None:
            if e is not None and e > 0:
                if line[:3] in ("G2 ", "G3 "):
                    mi = re.search(r" I(-?[\d.]+)", line); mj = re.search(r" J(-?[\d.]+)", line)
                    i = float(mi.group(1)) if mi else 0.0; j = float(mj.group(1)) if mj else 0.0
                    cx, cy = x + i, y + j; r = math.hypot(i, j); a0 = math.atan2(y - cy, x - cx); a1 = math.atan2(ny - cy, nx - cx)
                    da = a1 - a0; cw = line[:3] == "G2 "
                    if cw and da > 0: da -= 2 * math.pi
                    if not cw and da < 0: da += 2 * math.pi
                    n = max(2, int(abs(da) * r / 0.3) + 1); px, py = x, y
                    for k in range(1, n + 1):
                        a = a0 + da * k / n; qx, qy = cx + r * math.cos(a), cy + r * math.sin(a); cur["ext"].append((feat, px, py, qx, qy)); px, py = qx, qy
                else: cur["ext"].append((feat, x, y, nx, ny))
                cur["feats"][feat] = cur["feats"].get(feat, 0.0) + e
            elif e is None: cur["trav"].append((x, y, nx, ny))
        x, y = nx, ny
    return layers

def air_travel(L, cell=0.25, pad=0.8):
    from PIL import Image, ImageDraw
    xs = [s[1] for s in L["ext"]] + [s[3] for s in L["ext"]]; ys = [s[2] for s in L["ext"]] + [s[4] for s in L["ext"]]
    if not xs: return 0, 0.0, []
    x0, y0 = min(xs) - 3, min(ys) - 3; W = int((max(xs) - x0 + 3) / cell) + 1; H = int((max(ys) - y0 + 3) / cell) + 1
    img = Image.new("1", (W, H), 0); d = ImageDraw.Draw(img); w = int(2 * pad / cell) + 1
    for f, ax, ay, bx, by in L["ext"]: d.line([(ax - x0) / cell, (ay - y0) / cell, (bx - x0) / cell, (by - y0) / cell], fill=1, width=w)
    px = img.load(); n = 0; mm = 0.0; segs = []
    bx0, bx1, by0, by1 = min(xs) - 2, max(xs) + 2, min(ys) - 2, max(ys) + 2
    for ax, ay, bx, by in L["trav"]:
        l = math.hypot(bx - ax, by - ay)
        if l < 1.0 or not (bx0 < ax < bx1 and bx0 < bx < bx1 and by0 < ay < by1 and by0 < by < by1): continue
        k = max(2, int(l / 0.5)); air = 0
        for t in range(k + 1):
            sx = ax + (bx - ax) * t / k; sy = ay + (by - ay) * t / k; ix = int((sx - x0) / cell); iy = int((sy - y0) / cell)
            if not (0 <= ix < W and 0 <= iy < H) or px[ix, iy] == 0: air += 1
        if air >= 2: n += 1; mm += l * air / (k + 1); segs.append((ax, ay, bx, by))
    return n, mm, segs

COL = {"Outer wall": (0, 0, 0), "Inner wall": (90, 90, 220), "Sparse infill": (210, 210, 210), "Internal solid infill": (150, 150, 150),
       "Top surface": (220, 80, 80), "Bottom surface": (220, 140, 60), "Bridge": (0, 170, 170), "Gap infill": (230, 120, 230),
       "Overhang wall": (255, 0, 0), "Floating vertical shell": (0, 140, 0), "Brim": (0, 160, 0)}

def render(layers, zs, out, S=16):
    from PIL import Image, ImageDraw
    W, H = 30 * S, 20 * S; img = Image.new("RGB", (W, len(zs) * H), "white"); d = ImageDraw.Draw(img)
    for ri, zw in enumerate(zs):
        L = min(layers, key=lambda l: abs((l["z"] or 0) - zw)); oy = ri * H
        xs = [s[1] for s in L["ext"]]; ys = [s[2] for s in L["ext"]]
        if not xs: continue
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        tr = lambda px, py: (W / 2 + (px - cx) * S, oy + H / 2 - (py - cy) * S)
        d.rectangle([0, oy, W - 1, oy + H - 1], outline=(200, 200, 200))
        for f, ax, ay, bx, by in L["ext"]: d.line([tr(ax, ay), tr(bx, by)], fill=COL.get(f, (0, 200, 0)), width=2 if f in ("Outer wall", "Inner wall") else 1)
        n, mm, segs = air_travel(L)
        for ax, ay, bx, by in segs: d.line([tr(ax, ay), tr(bx, by)], fill=(255, 0, 255), width=2)
        d.text((5, oy + 5), f"z {L['z']:.2f}  retracts {L['retr']}  air travels {n} ({mm:.0f} mm)", fill=(0, 0, 0))
    img.save(out); print("saved", out)

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    layers = parse(a[0])
    zmax = max(L["z"] for L in layers if L["z"] is not None)
    bands = [(0, zmax, "whole object")]
    if "--bands" in a:
        bands = []
        for b in a[a.index("--bands") + 1].split(","):
            z0, z1, lab = b.split(":"); bands.append((float(z0), float(z1), lab))
    print(f"{a[0]}: {len(layers)} layers, {sum(L['retr'] for L in layers)} retractions")
    print(f"{'band':34s} {'layers':>6s} {'retr/L':>7s} {'air/L':>7s} {'mm/L':>6s} {'air total':>10s} {'mm total':>8s}")
    tn = 0; tmm = 0.0
    for lo, hi, lab in bands:
        sel = [L for L in layers if L["z"] is not None and lo < L["z"] <= hi]
        if not sel: continue
        air = [air_travel(L) for L in sel]; n = sum(x[0] for x in air); mm = sum(x[1] for x in air); tn += n; tmm += mm
        print(f"{lab:34s} {len(sel):6d} {sum(L['retr'] for L in sel) / len(sel):7.1f} {n / len(sel):7.1f} {mm / len(sel):6.1f} {n:10d} {mm:8.0f}")
    print(f"total travels through air inside the part: {tn} hops, {tmm / 1000:.1f} m")
    if "--png" in a:
        i = a.index("--png"); render(layers, [float(z) for z in a[i + 2].split(",")], a[i + 1])
