#!/usr/bin/env python3
"""Per-layer view of a Bambu Studio G-code: height, layer time (slicer's M73 estimate and a naive
distance/feedrate estimate), objects printed on the layer, extrusion per object, fan, nozzle temp.
Use it to see where layer time jumps (a neighbour object ends, geometry changes) — the usual
source of horizontal bands. Reads a plain .gcode or the Metadata/plate_N.gcode inside a sliced .3mf.

Usage: gcode_layers.py <file.gcode|sliced.3mf> [--csv out.csv] [--object <label>] [--totals]
  --object <label>  one object only: z, its E, its time per layer (E jumps > 35 % flagged)
  --totals          per-object total extrusion relative to the median (flow-rate plates)"""
import math, re, sys, zipfile

def read(path):
    if path.endswith(".3mf"):
        z = zipfile.ZipFile(path)
        name = next(n for n in z.namelist() if re.match(r"Metadata/plate_\d+\.gcode$", n))
        return z.read(name).decode("utf8", "ignore").splitlines()
    return open(path, encoding="utf8", errors="ignore").read().splitlines()

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    path = sys.argv[1]; lines = read(path)
    csv = sys.argv[sys.argv.index("--csv") + 1] if "--csv" in sys.argv else None
    only = sys.argv[sys.argv.index("--object") + 1] if "--object" in sys.argv else None   # one object: z, its E, its time
    labels, heights = [], []
    for l in lines[:60]:
        if l.startswith("; model label id:"): labels = l.split(":")[1].split(",")
        if l.startswith("; object max height:"): heights = l.split(":")[1].split(",")
    objh = {a.strip(): float(b) for a, b in zip(labels, heights)}
    layers = []; cur = None; obj = None; x = y = 0.0; f = 0.0; fan = 0; temp = 0; last_m73 = None
    for l in lines:
        if l.startswith("; CHANGE_LAYER"):
            cur = {"z": None, "n": len(layers) + 1, "t_naive": 0.0, "m73_r": last_m73, "objs": {}, "t_obj": {}, "fan": fan, "temp": temp, "travel": 0.0}
            layers.append(cur); continue
        if cur is None:
            m = re.match(r"M73 P\d+ R(\d+)", l)
            if m: last_m73 = int(m.group(1))
            continue
        if l.startswith("; Z_HEIGHT:"): cur["z"] = float(l.split(":")[1]); continue
        m = re.match(r"M73 P\d+ R(\d+)", l)
        if m:
            last_m73 = int(m.group(1))
            if cur["m73_r"] is None: cur["m73_r"] = last_m73
            continue
        m = re.match(r"; start printing object, unique label id: (\d+)", l)
        if m: obj = m.group(1); cur["objs"].setdefault(obj, 0.0); continue
        if l.startswith("M625"): obj = None; continue
        if l.startswith("M106 "):
            m = re.search(r"S(\d+)", l)
            if m: fan = int(m.group(1)); cur["fan"] = fan
            continue
        if l.startswith("M104 ") or l.startswith("M109 "):
            m = re.search(r"S(\d+)", l)
            if m: temp = int(m.group(1)); cur["temp"] = temp
            continue
        if l[:2] in ("G1", "G0", "G2", "G3"):
            nx, ny, e = x, y, 0.0
            for tok in l.split(";")[0].split()[1:]:
                k, v = tok[0], tok[1:]
                try: v = float(v)
                except ValueError: continue
                if k == "X": nx = v
                elif k == "Y": ny = v
                elif k == "E": e = v
                elif k == "F": f = v
            d = math.hypot(nx - x, ny - y); x, y = nx, ny
            if f > 0 and d > 0:
                cur["t_naive"] += d / (f / 60.0)
                if obj is not None: cur["t_obj"][obj] = cur["t_obj"].get(obj, 0.0) + d / (f / 60.0)
                if e <= 0: cur["travel"] += d
            if e > 0 and obj is not None: cur["objs"][obj] = cur["objs"].get(obj, 0.0) + e
    # per-layer M73 delta (minutes remaining decreases as we go)
    for i, L in enumerate(layers):
        nxt = next((M["m73_r"] for M in layers[i + 1:] if M["m73_r"] is not None), None)
        L["m73_dt"] = (L["m73_r"] - nxt) * 60 if (L["m73_r"] is not None and nxt is not None) else None
    print(f"file: {path}\nobjects (label: max height): {objh}\nlayers: {len(layers)}\n")
    if "--totals" in sys.argv:   # per-object total extrusion, relative to the median (flow-rate plates)
        tot = {}
        for L in layers:
            for k, v in L["objs"].items(): tot[k] = tot.get(k, 0.0) + v
        vals = sorted(tot.items(), key=lambda x: x[1]); mid = vals[len(vals)//2][1] if vals else 1
        print("per-object E (mm) relative to median: " + "  ".join(f"{k}:{v/mid:.2f}" for k, v in vals)); return
    if only:
        print(f"object {only}: {'n':>3} {'z':>6} {'E_mm':>6} {'t_obj':>6} {'t_layer':>7} {'fan':>3}")
        pe = None
        for L in layers:
            if only not in L["objs"]: continue
            e = L["objs"][only]; flag = "  <- E jump" if pe and abs(e - pe) / pe > 0.35 else ""
            print(f"            {L['n']:>3} {L['z']:>6.2f} {e:>6.1f} {L['t_obj'].get(only, 0):>6.1f} {L['t_naive']:>7.1f} {L['fan']:>3}{flag}"); pe = e
        return
    print(f"{'n':>3} {'z':>6} {'t_naive':>7} {'m73':>5} {'fan':>3} {'°C':>3}  objects -> extrusion mm (E)")
    prev = None
    for L in layers:
        objs = " ".join(f"{k}:{v:.0f}" for k, v in sorted(L["objs"].items()))
        key = tuple(sorted(L["objs"]))
        mark = " <- object set changed" if prev is not None and key != prev else ""
        prev = key
        m73 = f"{L['m73_dt']:.0f}" if L["m73_dt"] is not None else "-"
        print(f"{L['n']:>3} {L['z']:>6.2f} {L['t_naive']:>7.1f} {m73:>5} {L['fan']:>3} {L['temp']:>3}  {objs}{mark}")
    if csv:
        with open(csv, "w") as fh:
            fh.write("layer,z,t_naive_s,m73_dt_s,fan,temp,objects,extrusion_by_object\n")
            for L in layers:
                fh.write(f"{L['n']},{L['z']},{L['t_naive']:.1f},{L['m73_dt'] if L['m73_dt'] is not None else ''},{L['fan']},{L['temp']},{'|'.join(sorted(L['objs']))},{'|'.join(f'{k}:{v:.1f}' for k,v in sorted(L['objs'].items()))}\n")
        print("csv:", csv)

if __name__ == "__main__":
    main()
