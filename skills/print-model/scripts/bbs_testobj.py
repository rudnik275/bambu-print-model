#!/usr/bin/env python3
"""Put a synthetic test object into an existing single-object project, keeping its presets and overrides.

  bbs_testobj.py pillars <container.3mf> <out.3mf> [--n 6] [--d 6] [--h 12] [--gap 12] [--segs 96] [--at 90,90] [--ballast 45]

pillars: N cylinders in a row — many small closed loops per layer with travel between them, the same load
as thin organic features (ribs, twigs): the cheap stand-in for a multi-hour print when hunting ripple or
ringing. --at is the row centre in bed coordinates (default 90,90 = the centre of a 180 mm bed). --ballast W
adds a WxWxh block behind the row so each layer has enough work that the cooling slowdown never fires and the
pillars print at the commanded speeds (needed for gcode_speedbands.py). Mesh is written in bed coordinates,
object transform reset to identity."""
import math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbs_project import _read_zip, _write_zip
from bbs_rebuild import HEAD, TAIL

def cylinder(cx, cy, d, h, segs, v0):
    r = d / 2; vs = []; ts = []
    for k in range(segs):
        a = 2 * math.pi * k / segs; vs.append((cx + r * math.cos(a), cy + r * math.sin(a), 0.0))
    for k in range(segs):
        a = 2 * math.pi * k / segs; vs.append((cx + r * math.cos(a), cy + r * math.sin(a), h))
    vs.append((cx, cy, 0.0)); vs.append((cx, cy, h)); cb, ct = v0 + 2 * segs, v0 + 2 * segs + 1
    for k in range(segs):
        n = (k + 1) % segs; b0, b1, t0, t1 = v0 + k, v0 + n, v0 + segs + k, v0 + segs + n
        ts += [(b0, t0, b1), (b1, t0, t1)]            # side, outward normals
        ts += [(cb, b1, b0), (ct, t0, t1)]            # caps
    return vs, ts

def box(cx, cy, w, h, v0):
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - w / 2, cy + w / 2
    vs = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h)]
    q = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (3, 2, 1, 0), (4, 5, 6, 7)]     # sides outward, bottom, top
    ts = []
    for a, b, c, d in q: ts += [(v0 + a, v0 + b, v0 + c), (v0 + a, v0 + c, v0 + d)]
    return vs, ts

def pillars(n, d, h, gap, segs, at, ballast=0.0):
    """ballast: a WxWxh block behind the row — enough work per layer that the cooling slowdown
    (slow_down_layer_time) never kicks in, so the pillars print at the commanded speeds"""
    vs = []; ts = []; x0 = at[0] - (n - 1) * gap / 2
    for i in range(n):
        v, t = cylinder(x0 + i * gap, at[1], d, h, segs, len(vs)); vs += v; ts += t
    if ballast:
        v, t = box(at[0], at[1] + d / 2 + 12 + ballast / 2, ballast, h, len(vs)); vs += v; ts += t
    return vs, ts

def main():
    a = sys.argv[1:]
    if len(a) < 3 or a[0] in ("-h", "--help"): sys.exit(__doc__)
    opt = lambda k, dflt: type(dflt)(a[a.index(k) + 1]) if k in a else dflt
    kind, inp, out = a[0], a[1], a[2]
    if kind != "pillars": raise SystemExit("only 'pillars' for now\n\n" + __doc__)
    n, d, h, gap, segs = opt("--n", 6), opt("--d", 6.0), opt("--h", 12.0), opt("--gap", 12.0), opt("--segs", 96)
    at = tuple(float(v) for v in opt("--at", "90,90").split(",")); ballast = opt("--ballast", 0.0)
    vs, ts = pillars(n, d, h, gap, segs, at, ballast)
    files = _read_zip(inp); model = files["3D/3dmodel.model"].decode(); ms = files["Metadata/model_settings.config"].decode()
    comp = re.search(r'<object id="(\d+)" [^>]*>\s*<components>\s*<component p:path="([^"]+)"', model, re.S)
    if not comp: raise SystemExit("container must be a project with one component object (3D/Objects/*.model)")
    oid, path = comp.group(1), comp.group(2).lstrip("/")
    part = re.search(r'<part id="(\d+)"', ms).group(1)
    xml = [HEAD, f'  <object id="{part}" p:UUID="{int(oid):04x}0000-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n    <vertices>\n']
    xml += [f'     <vertex x="{x:.6g}" y="{y:.6g}" z="{z:.6g}"/>\n' for x, y, z in vs]
    xml += ['    </vertices>\n    <triangles>\n'] + [f'     <triangle v1="{p}" v2="{q}" v3="{r}"/>\n' for p, q, r in ts] + ['    </triangles>\n', TAIL]
    files[path] = "".join(xml).encode()
    ident = "1 0 0 0 1 0 0 0 1 0 0 0"
    model = re.sub(r'(<item objectid="%s" [^>]*transform=")[^"]+(")' % oid, r'\g<1>' + ident + r'\2', model)
    model = re.sub(r'(<component [^>]*transform=")[^"]+(")', r'\g<1>' + ident + r'\2', model)
    ms = re.sub(r'(key="matrix" value=")[^"]+(")', r'\g<1>1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1\2', ms)
    ms = re.sub(r'(key="name" value=")[^"]*(")', r'\g<1>' + f'pillars-{n}x{d:g}x{h:g}' + r'\2', ms, count=1)
    ms = re.sub(r'face_count="\d+"', f'face_count="{len(ts)}"', ms)
    ms = re.sub(r'<assemble>.*?</assemble>', '', ms, flags=re.S)
    files["3D/3dmodel.model"] = model.encode(); files["Metadata/model_settings.config"] = ms.encode()
    _write_zip(out, files); print(f"pillars: {n} x d{d:g} x {h:g} mm, {segs} segs -> {len(vs)} verts, {len(ts)} tris; written: {out}")

if __name__ == "__main__":
    main()
