#!/usr/bin/env python3
"""Speed tower from any sliced plate: rewrite wall feedrates per height band inside a .gcode.3mf.

  gcode_speedbands.py <in.gcode.3mf> <out.gcode.3mf> "0-5:40,5-10:60,10-15:80,15-20:120,20-25:160,25-30:220" [features]

Bands are "z_from-z_to:mm_per_s". Only extrusion moves (G1 with E>0) inside the listed features
(default: Outer wall, Inner wall) are touched; travels, infill, first layer stay as sliced.
The slicer's own cooling slowdown is baked into F already — pair with a ballast object so it did
not fire (bbs_testobj.py --ballast), otherwise the commanded speeds are lower than the bands say.
Updates Metadata/plate_1.gcode.md5 so the printer accepts the file."""
import hashlib, re, sys, zipfile

def bands_of(spec):
    out = []
    for part in spec.split(","):
        rng, v = part.split(":"); a, b = rng.split("-"); out.append((float(a), float(b), float(v)))
    return out

def rewrite(gcode, bands, feats):
    """Bambu G-code sets a feature's speed with a standalone 'G1 F<n>' and then emits moves without F;
    retracts ('G1 E-.04 F1800') and travels ('G1 X.. Y.. F42000') carry their own F and are left alone."""
    z = 0.0; feat = None; lines = gcode.split("\n"); n = 0
    for i, l in enumerate(lines):
        if l.startswith("; Z_HEIGHT:"):
            try: z = float(l.split(":")[1])
            except ValueError: pass
            continue
        if l.startswith("; FEATURE: "): feat = l[11:].strip(); continue
        if feat not in feats or not re.match(r"G1 F[\d.]+\s*$", l): continue
        for a, b, v in bands:
            if a <= z < b:
                lines[i] = f"G1 F{int(v * 60)}"; n += 1; break
    return "\n".join(lines), n

def main():
    if len(sys.argv) < 4 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    inp, out, spec = sys.argv[1], sys.argv[2], sys.argv[3]
    feats = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else {"Outer wall", "Inner wall"}
    bands = bands_of(spec)
    zi = zipfile.ZipFile(inp)
    text, n = rewrite(zi.read("Metadata/plate_1.gcode").decode("utf-8", "replace"), bands, feats)
    gcode = text.encode(); md5 = hashlib.md5(gcode).hexdigest().upper()
    zo = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
    for name in zi.namelist():
        data = {"Metadata/plate_1.gcode": gcode, "Metadata/plate_1.gcode.md5": md5.encode()}.get(name) or zi.read(name)
        zo.writestr(name, data)
    zo.close(); print(f"rewrote {n} wall moves; md5 {md5}; written: {out}")

if __name__ == "__main__":
    main()
