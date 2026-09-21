#!/usr/bin/env python3
"""Compare two sliced plates — the one-variable experiment in numbers, before either is printed.

  gcode_compare.py <a/plate_1.gcode> <b/plate_1.gcode>

Prints: settings that differ (from the G-code header, machine G-code blobs skipped), totals (time, grams,
layers), per-feature extrusion and — when result.json sits next to the file (CLI export dir) — per-feature
time, then the forecast inputs side by side: bridge max span, overhang walls, gap fill and its tiny-segment
share, support, top surface. Deltas are b relative to a. Borrowed from orcaslicer-mcp's compare_slices idea."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_features import parse

SKIP = ("_gcode", "different_settings_to_system", "filament_colour", "printer_settings_id", "print_settings_id",
        "filament_settings_id", "version", "inherits", "compatible", "printer_model", "filament_ids", "date")

def header(path):
    s, tot = {}, {}
    for line in open(path, errors="replace"):
        if not line.startswith("; "):
            if line.startswith("G1 ") or line.startswith("M"):
                if len(tot) >= 3 and s: break
            continue
        if " = " in line:
            k, v = line[2:].split(" = ", 1); s[k.strip()] = v.strip()
        elif line.startswith("; model printing time:"):
            tot["time"] = line.split(":", 1)[1].split(";")[0].strip()
        elif line.startswith("; total filament weight [g] :"): tot["g"] = float(line.split(":")[1])
        elif line.startswith("; total layer number:"): tot["layers"] = int(line.split(":")[1])
    return s, tot

def secs(t):
    m = re.findall(r"(\d+)\s*([hms])", t); return sum(int(v) * {"h": 3600, "m": 60, "s": 1}[u] for v, u in m)

def features(path):
    acc, z = parse(path)
    E, tiny, seg, span = {}, {}, {}, {}
    for (L, f), (x0, y0, x1, y1, e, n, t, longest) in acc.items():   # 8 fields; the last is the longest single extrusion
        E[f] = E.get(f, 0.0) + e; seg[f] = seg.get(f, 0) + n; tiny[f] = tiny.get(f, 0) + t
        if f == "Bridge": span[f] = max(span.get(f, 0.0), longest)       # the real span, not the region's box
    return E, tiny, seg, span

def times(path):
    p = os.path.join(os.path.dirname(os.path.abspath(path)), "result.json")
    if not os.path.exists(p): return {}
    r = json.load(open(p)); pl = r["sliced_plates"][0]
    return {k: v for k, v in pl["feature_type_times"].items()}

def pct(a, b): return f"{(b - a) / a * 100:+.0f} %" if a else "—"

def main():
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    a, b = sys.argv[1], sys.argv[2]
    sa, ta = header(a); sb, tb = header(b)
    print(f"A: {a}\nB: {b}\n")
    diff = [(k, sa.get(k), sb.get(k)) for k in sorted(set(sa) | set(sb)) if sa.get(k) != sb.get(k) and not any(x in k for x in SKIP)]
    print("settings that differ:" if diff else "settings: identical")
    for k, va, vb in diff: print(f"  {k}: {va}  ->  {vb}")
    Ta, Tb = secs(ta.get("time", "")), secs(tb.get("time", ""))
    print(f"\ntime    : {ta.get('time','?')}  ->  {tb.get('time','?')}  ({pct(Ta, Tb)})")
    print(f"filament: {ta.get('g','?')} g  ->  {tb.get('g','?')} g  ({pct(ta.get('g',0), tb.get('g',0))})")
    print(f"layers  : {ta.get('layers','?')}  ->  {tb.get('layers','?')}")
    Ea, tya, sga, spa = features(a); Eb, tyb, sgb, spb = features(b); ma, mb = times(a), times(b)
    print("\nfeature              E mm A     E mm B    ΔE      time A   time B")
    for f in sorted(set(Ea) | set(Eb), key=lambda f: -(Ea.get(f, 0) + Eb.get(f, 0))):
        t = f"{ma[f]:7.0f}s {mb[f]:7.0f}s" if f in ma and f in mb else ""
        print(f"{f:20s} {Ea.get(f,0):8.1f} {Eb.get(f,0):8.1f}   {pct(Ea.get(f,0), Eb.get(f,0)):>7s}   {t}")
    def tiny_share(ty, sg, f): return f"{100*ty.get(f,0)/sg[f]:.0f} % tiny" if sg.get(f) else "—"
    print("\nforecast inputs:")
    print(f"  bridge max span   : {spa.get('Bridge',0):.1f} mm  ->  {spb.get('Bridge',0):.1f} mm")
    print(f"  overhang wall E   : {Ea.get('Overhang wall',0):.1f}  ->  {Eb.get('Overhang wall',0):.1f}")
    print(f"  gap infill E      : {Ea.get('Gap infill',0):.1f} ({tiny_share(tya, sga, 'Gap infill')})  ->  {Eb.get('Gap infill',0):.1f} ({tiny_share(tyb, sgb, 'Gap infill')})")
    print(f"  support E         : {Ea.get('Support',0)+Ea.get('Support interface',0):.1f}  ->  {Eb.get('Support',0)+Eb.get('Support interface',0):.1f}")
    print(f"  top surface E     : {Ea.get('Top surface',0):.1f}  ->  {Eb.get('Top surface',0):.1f}")

if __name__ == "__main__":
    main()
