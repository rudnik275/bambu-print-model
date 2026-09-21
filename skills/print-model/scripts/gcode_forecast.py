#!/usr/bin/env python3
"""The G-code half of the print forecast in one pass, per CLI-export directory (plate_1.gcode + result.json +
<name>.gcode.3mf): checks 1, 2, 5, 7, 10, 11, 12 of the forecast checklist (references/forecast.md), plus the
start-G-code sanity check (M1002 count vs an un-indented `M109 S205` = the generic placeholder that slips in
when machine G-code is taken from presets instead of a Studio-saved project) and where the support sits by z.
Feature checks (3, 4, 6, 8, 13, 14) stay in gcode_features.py; 15 in mesh_slopes.py; 16 in gcode_airtravel.py.

Usage: gcode_forecast.py <cli export dir> [...]

Bed size comes from the G-code header (`; printable_area = 0x0,180x0,180x180,0x180`, `; printable_height`),
falling back to 180 x 180 x 180 when absent. The "x<20" flag is A1 mini specific: its left 20 mm is a collision
zone at purge; it is raised only when the header's printer_model contains "A1 mini" (or the header has no
printer_model). Other printers: check their own exclusion areas (`; bed_exclude_area` is printed when set)."""
import json, os, re, sys, zipfile
from collections import defaultdict

def gcode_path(d):
    return os.path.join(d, "plate_1.gcode")

def header(path):
    s = {}
    for line in open(path, errors="replace"):
        if line.startswith("; ") and " = " in line:
            k, v = line[2:].split(" = ", 1); s[k.strip()] = v.strip()
        elif line.startswith("; total layer number:"): s["_layers"] = int(line.split(":")[1])
        elif line.startswith("; model printing time:"): s["_time"] = line.split(":", 1)[1].split(";")[0].strip()
        elif line.startswith("; total filament weight [g] :"): s["_g"] = float(line.split(":")[1])
        elif line.startswith("; EXECUTABLE_BLOCK_START"): break
    return s

def bed_from_header(h):
    """(x0, y0, x1, y1, zmax) from printable_area / printable_height; a 180 mm cube when the header lacks them"""
    try:
        pts = [tuple(float(v) for v in p.split("x")) for p in h["printable_area"].split(",")]
        x0, y0, x1, y1 = min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
    except (KeyError, ValueError, IndexError): x0, y0, x1, y1 = 0.0, 0.0, 180.0, 180.0
    try: zmax = float(h["printable_height"])
    except (KeyError, ValueError): zmax = 180.0
    return x0, y0, x1, y1, zmax

def layers(path):
    """per layer: z, seconds (from M73 remaining-minute steps, spread evenly), E total, E by feature, xy-weighted E centre"""
    out = []; cur = None; feat = None; x = y = 0.0; m73 = None
    for line in open(path, errors="replace"):
        if line.startswith("; CHANGE_LAYER"):
            cur = {"z": None, "E": 0.0, "feat": defaultdict(float), "sx": 0.0, "sy": 0.0, "m73": m73}; out.append(cur); continue
        if line.startswith("; Z_HEIGHT:") and cur is not None:
            try: cur["z"] = float(line.split(":")[1])
            except ValueError: pass
            continue
        m = re.match(r"M73 P\d+ R(\d+)", line)
        if m: m73 = int(m.group(1)); continue
        if line.startswith("; FEATURE: "): feat = line[11:].strip(); continue
        if cur is None or line[:3] not in ("G1 ", "G2 ", "G3 "): continue
        mx = re.search(r"X([-\d.]+)", line); my = re.search(r"Y([-\d.]+)", line); me = re.search(r"E([-\d.]+)", line)
        nx = float(mx.group(1)) if mx else x; ny = float(my.group(1)) if my else y
        if me and (mx or my):
            e = float(me.group(1))
            if e > 0:
                cur["E"] += e; cur["feat"][feat or "?"] += e; cur["sx"] += e * (x + nx) / 2; cur["sy"] += e * (y + ny) / 2
        x, y = nx, ny
    # layer seconds: M73 R is minutes remaining at the layer start; interpolate between changes
    ts = [l["m73"] for l in out]; n = len(out); secs = [None] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ts[j + 1] == ts[i]: j += 1
        nxt = ts[j + 1] if j + 1 < n else None
        if ts[i] is not None and nxt is not None:
            per = (ts[i] - nxt) * 60.0 / (j - i + 1)
            for k in range(i, j + 1): secs[k] = per
        i = j + 1
    for l, s in zip(out, secs): l["s"] = s
    return out

def features_e(path):
    """E by feature over the whole file (Support / Support interface for check 12, Brim presence)"""
    tot = defaultdict(float); feat = None
    for line in open(path, errors="replace"):
        if line.startswith("; FEATURE: "): feat = line[11:].strip(); continue
        if line[:3] not in ("G1 ", "G2 ", "G3 ") or feat is None: continue
        me = re.search(r"E([-\d.]+)", line)
        if me and ("X" in line or "Y" in line):
            e = float(me.group(1))
            if e > 0: tot[feat] += e
    return tot

def report(d):
    g = gcode_path(d); name = os.path.basename(d.rstrip("/\\")); print(f"\n##### {name}")
    h = header(g); lh = float(h.get("layer_height", 0.2)); slow = float(h.get("slow_down_layer_time", "6").split(",")[0])
    print(f"time {h.get('_time')}  {h.get('_g')} g  layers {h.get('_layers')}  layer {lh}  process {h.get('print_settings_id')}  filament {h.get('filament_settings_id')}")
    r = json.load(open(os.path.join(d, "result.json"))); p = r["sliced_plates"][0]
    # 1, 2: fit on the bed, and the A1 mini's left 20 mm
    bx0, by0, bx1, by1, bz = bed_from_header(h); pm = h.get("printer_model")
    a1mini = pm is None or "A1 mini" in pm
    print(f"  bed: x {bx0:g}..{bx1:g}  y {by0:g}..{by1:g}  z ..{bz:g}  ({pm or 'printer_model header missing'})"
          + (f"; bed_exclude_area = {h['bed_exclude_area']}" if h.get("bed_exclude_area") else ""))
    def box(o):   # result.json: {"x","y","z","width","depth","height"} -> [x0,y0,z0,x1,y1,z1]
        b = o["bbox"]; return [b["x"], b["y"], b["z"], b["x"] + b["width"], b["y"] + b["depth"], b["z"] + b["height"]]
    left20 = False
    for o in p["objects"]:
        b = box(o); flags = []
        if a1mini and b[0] < 20: flags.append("x<20"); left20 = True
        if b[0] < bx0 or b[1] < by0 or b[3] > bx1 or b[4] > by1 or b[5] > bz: flags.append(f"OUTSIDE {bx1 - bx0:g}x{by1 - by0:g}x{bz:g}")
        print(f"  object {o['name']}: x {b[0]:.1f}..{b[3]:.1f}  y {b[1]:.1f}..{b[4]:.1f}  z ..{b[5]:.1f}  {' '.join(flags) or 'ok'}")
    if left20: print("  note: A1 mini: left 20 mm is a collision zone at purge; other printers: check their exclusion areas")
    # 11: warnings
    warn = p.get("warning_message") or ""
    z3 = [f for f in os.listdir(d) if f.endswith(".gcode.3mf")]
    if z3:
        si = zipfile.ZipFile(os.path.join(d, z3[0])).read("Metadata/slice_info.config").decode("utf8", "ignore")
        w2 = re.findall(r"<warning[^>]*>([^<]*)</warning>|<warning[^>]*msg=\"([^\"]*)\"", si)
        warn += " " + " ".join(a or b for a, b in w2)
    print(f"  warnings: {warn.strip() or '—'}   error: {r.get('error_string')}")
    # start-G-code sanity
    txt = open(g, errors="replace").read()
    m1002 = txt.count("M1002"); s205 = len(re.findall(r"^M109 S205", txt, re.M))
    print(f"  start gcode: M1002 x{m1002}, un-indented `M109 S205` x{s205} -> {'OK (Bambu)' if m1002 > 100 and s205 == 0 else 'WRONG: generic placeholder? (see bbs_project.py snapshot)'}")
    first_m109 = re.search(r"^M109 S(\d+)", txt, re.M); first_m140 = re.search(r"^M140 S(\d+)", txt, re.M)
    print(f"  first M109 S{first_m109.group(1) if first_m109 else '?'}, M140 S{first_m140.group(1) if first_m140 else '?'}")
    # 12: support share, brim presence
    fe = features_e(g); tot = sum(fe.values()) or 1.0; sup = fe.get("Support", 0) + fe.get("Support interface", 0)
    print(f"  support {100 * sup / tot:.1f} % of E ({'>40 %: reconsider the orientation' if sup / tot > 0.4 else 'ok'}); brim E {fe.get('Brim', 0):.0f} mm; features: " +
          ", ".join(f"{k} {100 * v / tot:.1f}%" for k, v in sorted(fe.items(), key=lambda t: -t[1])[:6]))
    L = layers(g)
    # support by z band
    band = defaultdict(float)
    for l in L:
        s = l["feat"].get("Support", 0) + l["feat"].get("Support interface", 0)
        if s and l["z"] is not None: band[int(l["z"] // 10) * 10] += s
    if band: print("  support by z: " + ", ".join(f"{z}-{z + 10}: {e:.0f}" for z, e in sorted(band.items())))
    # 10: first layer area (mm² at 0.2 mm, 1.75 filament: E mm * 2.405 mm² / 0.2 mm), height/width, extrusion centre vs first layer box
    l1 = L[0]; area = l1["E"] * 2.405 / float(h.get("initial_layer_print_height", 0.2))
    cx = sum(l["sx"] for l in L) / (sum(l["E"] for l in L) or 1.0); cy = sum(l["sy"] for l in L) / (sum(l["E"] for l in L) or 1.0)
    bb = box(p["objects"][0]) if len(p["objects"]) == 1 else None
    hmax = max(box(o)[5] for o in p["objects"])
    if bb:
        w = min(bb[3] - bb[0], bb[4] - bb[1]); print(f"  first layer: {area:.0f} mm² of footprint {(bb[3] - bb[0]) * (bb[4] - bb[1]):.0f}; h/w {hmax / w:.1f}; E-centre ({cx:.1f}, {cy:.1f}) {'inside' if bb[0] <= cx <= bb[3] and bb[1] <= cy <= bb[4] else 'OUTSIDE'} first-layer box; brim {h.get('brim_type')}")
    else:
        print(f"  first layer: {area:.0f} mm² over {len(p['objects'])} objects; h {hmax:.0f}; brim {h.get('brim_type')}")
    # 7: consecutive layers faster than slow_down_layer_time
    runs = []; cur = []
    for i, l in enumerate(L):
        if l["s"] is not None and l["s"] < slow: cur.append(i)
        else:
            if len(cur) >= 5: runs.append((L[cur[0]]["z"], L[cur[-1]]["z"], len(cur), min(L[k]["s"] for k in cur)))
            cur = []
    if len(cur) >= 5: runs.append((L[cur[0]]["z"], L[cur[-1]]["z"], len(cur), min(L[k]["s"] for k in cur)))
    print(f"  layers < {slow:.0f} s (slow_down_layer_time), runs >= 5: " + ("; ".join(f"z {a:.1f}-{b:.1f} ({n} layers, min {s:.1f} s)" for a, b, n, s in runs) if runs else "—"))
    # 5: E jumps >= 2x vs neighbours while walls continue above (floor line candidates), skipping the first 3 and last 3 layers
    jumps = []
    for i in range(3, len(L) - 3):
        e = L[i]["E"]; prev = sum(L[k]["E"] for k in range(i - 3, i)) / 3; nxt = sum(L[k]["E"] for k in range(i + 1, i + 4)) / 3
        if prev > 0 and e >= 2 * prev and e >= 2 * nxt and L[i + 1]["feat"].get("Outer wall", 0) > 0:
            jumps.append((L[i]["z"], e / prev))
    # merge neighbouring jumps
    merged = []
    for z, k in jumps:
        if merged and z - merged[-1][1] < 1.0: merged[-1] = (merged[-1][0], z, max(merged[-1][2], k))
        else: merged.append((z, z, k))
    print("  E jumps >= 2x with walls above (floor line?): " + ("; ".join(f"z {a:.1f}{'' if a == b else f'-{b:.1f}'} (x{k:.1f})" for a, b, k in merged) if merged else "—"))
    # per-object longest layer time context
    smax = max((l["s"] or 0) for l in L); print(f"  layer time: max {smax:.0f} s, median {sorted(l['s'] or 0 for l in L)[len(L) // 2]:.0f} s")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    for d in sys.argv[1:]: report(d)
