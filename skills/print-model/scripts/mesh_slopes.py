#!/usr/bin/env python3
"""Where a model will show layer stair-steps: shallow slopes per height band, straight from the mesh.

  mesh_slopes.py <project.3mf | model.stl> [--layer 0.2] [--band 1] [--wmin 0.3] [--wmax 2.0] [--min 20]

A surface tilted θ from horizontal prints as steps of width layer_height / tan θ. Steps read as contour
lines ("topographic map" on ribs, backs, domes) when that width is between --wmin and --wmax (0.3–2 mm):
narrower is ordinary layer texture, wider is a terrace the eye takes for design (a Benchy roof at 4.5°
gives 2.5 mm terraces and no visible steps). Speed, temperature and resolution do not change this —
only a thinner layer where the slope is shallow (variable layer height) or another orientation.

Per band of z: face area, area of "stepping" faces (step width within the window), share, and the step
width for the shallowest such face of the band.
A band is flagged when shallow area >= --min mm² per 1 mm of height (default 20): a lying rod always has
its crown shallow, so the share is small even where every rib shows contour lines — absolute area is
what the eye sees. 3MF: Studio projects (3D/Objects/*.model components) and plain 3MF, build transforms
applied. STL as is."""
import math, os, re, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _mesh(xml):
    out = {}
    for tag, body in re.findall(r'(<object [^>]*>)(.*?)</object>', xml, re.S):
        oid = re.search(r'\bid="(\d+)"', tag).group(1)
        vs = [tuple(float(v) for v in m) for m in re.findall(r'<vertex\s+x="([^"]+)"\s+y="([^"]+)"\s+z="([^"]+)"', body)]
        ts = [tuple(int(v) for v in m) for m in re.findall(r'<triangle\s+v1="(\d+)"\s+v2="(\d+)"\s+v3="(\d+)"', body)]
        comps = re.findall(r'<component [^>]*>', body)
        out[oid] = (vs, ts, comps)
    return out

def _apply(t, vs):
    t = [float(v) for v in t.split()]
    return [(t[0]*x+t[3]*y+t[6]*z+t[9], t[1]*x+t[4]*y+t[7]*z+t[10], t[2]*x+t[5]*y+t[8]*z+t[11]) for x, y, z in vs]

def load(path):
    """[(name, verts, tris)] in bed coordinates"""
    if path.lower().endswith(".stl"):
        from bbs_calib import stl_mesh
        vs, ts = stl_mesh(path); return [(os.path.basename(path), vs, ts)]
    z = zipfile.ZipFile(path); root = _mesh(z.read("3D/3dmodel.model").decode("utf8", "ignore"))
    parts = {}
    for n in z.namelist():
        if n.startswith("3D/Objects/") and n.endswith(".model"): parts[n] = _mesh(z.read(n).decode("utf8", "ignore"))
    out = []
    for tag in re.findall(r'<item [^>]*>', z.read("3D/3dmodel.model").decode("utf8", "ignore")):
        oid = re.search(r'objectid="(\d+)"', tag).group(1); trm = re.search(r'transform="([^"]+)"', tag)
        tr = trm.group(1) if trm else "1 0 0 0 1 0 0 0 1 0 0 0"
        vs, ts, comps = root.get(oid, ([], [], []))
        if vs: out.append((f"object {oid}", _apply(tr, vs), ts)); continue
        for c in comps:
            p = re.search(r'p:path="([^"]+)"', c); cid = re.search(r'objectid="(\d+)"', c).group(1)
            ctr = re.search(r'transform="([^"]+)"', c); ctr = ctr.group(1) if ctr else "1 0 0 0 1 0 0 0 1 0 0 0"
            src = parts.get(p.group(1).lstrip("/"), {}) if p else root
            cvs, cts, _ = src.get(cid, ([], [], []))
            if cvs: out.append((f"object {oid}/{cid}", _apply(tr, _apply(ctr, cvs)), cts))
    return out

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
    path = a[0]; lh = opt("--layer", 0.2); band = opt("--band", 1.0); amin = opt("--min", 20.0)
    wmin, wmax = opt("--wmin", 0.3), opt("--wmax", 2.0)
    tmin = math.degrees(math.atan(lh / wmax)); tmax = math.degrees(math.atan(lh / wmin))   # tilt window for this layer
    objs = load(path)
    if not objs: raise SystemExit("no mesh found")
    z0 = min(v[2] for _, vs, _ in objs for v in vs)
    bands = {}   # z band -> [area, shallow area, min tilt]
    for name, vs, ts in objs:
        for i, j, k in ts:
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = vs[i], vs[j], vs[k]
            ux, uy, uz = bx - ax, by - ay, bz - az; wx, wy, wz = cx - ax, cy - ay, cz - az
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            n2 = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n2 < 1e-12: continue
            tilt = math.degrees(math.acos(min(1.0, abs(nz) / n2)))   # face angle from horizontal: 0 flat, 90 wall
            b = round(math.floor(((az + bz + cz) / 3 - z0) / band) * band, 3)
            rec = bands.setdefault(b, [0.0, 0.0, 90.0]); rec[0] += n2 / 2
            if tmin <= tilt <= tmax: rec[1] += n2 / 2; rec[2] = min(rec[2], tilt)
    tot = sum(r[0] for r in bands.values()); sh = sum(r[1] for r in bands.values())
    print(f"{os.path.basename(path)}: {len(objs)} object(s), layer {lh} mm, steps {wmin:g}–{wmax:g} mm wide = tilt {tmin:.1f}–{tmax:.1f}° from horizontal, bands {band:g} mm")
    print(f"stepping area overall: {sh:.0f} / {tot:.0f} mm² = {100 * sh / tot:.1f} %")
    print("     z      area  stepping  share  min tilt  step width")
    flagged = []
    for b in sorted(bands):
        t, s, m = bands[b]
        share = s / t if t else 0.0; w = lh / math.tan(math.radians(m)) if m < 90 else 0.0
        mark = "  <-- steps" if s >= amin * band else ""
        if mark: flagged.append([b, b + band])
        print(f"{b:6.1f} {t:9.0f} {s:9.0f} {100 * share:5.1f}%   {m:5.1f}°   {w:5.2f} mm{mark}")
    runs = []
    for lo, hi in flagged:
        if runs and abs(runs[-1][1] - lo) < 1e-6: runs[-1][1] = hi
        else: runs.append([lo, hi])
    print("steps expected at z:", ", ".join(f"{lo:g}–{hi:g}" for lo, hi in runs) + " mm" if runs else f"none (no band with >= {amin:g} mm² stepping faces per mm)")

if __name__ == "__main__":
    main()
