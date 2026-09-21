#!/usr/bin/env python3
"""Rebuild a full Bambu Studio project from a settings-only autosave .3mf (no meshes) plus the
original source meshes it was made from. Studio's autosave copy references 3D/Objects/object_N.model
files that are gone once the autosave dir rotated; the meshes are re-generated from the sources and
re-centred with the recorded source_offset_* so the saved item transforms still apply.

Usage: bbs_rebuild.py <settings-only.3mf> <out.3mf> source_file=path [source_file=path ...]
  source_file is the value of <metadata key="source_file"> in Metadata/model_settings.config."""
import os, re, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbs_project import _read_zip, _write_zip

HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
        'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n')
TAIL = '   </mesh>\n  </object>\n </resources>\n <build/>\n</model>\n'

def source_mesh(path):
    z = zipfile.ZipFile(path); x = z.read([n for n in z.namelist() if n.endswith(".model")][0]).decode("utf8", "ignore")
    vs = [tuple(float(v) for v in m) for m in re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', x)]
    ts = [tuple(int(v) for v in m) for m in re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', x)]
    m = re.search(r'<item [^>]*transform="([^"]+)"', x)
    if m:
        t = [float(v) for v in m.group(1).split()]
        if len(t) == 12 and t != [1,0,0,0,1,0,0,0,1,0,0,0]:
            vs = [(t[0]*x_+t[3]*y+t[6]*z+t[9], t[1]*x_+t[4]*y+t[7]*z+t[10], t[2]*x_+t[5]*y+t[8]*z+t[11]) for x_, y, z in vs]
    return vs, ts

def main():
    if len(sys.argv) < 4 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    inp, out = sys.argv[1], sys.argv[2]; srcs = dict(a.split("=", 1) for a in sys.argv[3:])
    files = _read_zip(inp); ms = files["Metadata/model_settings.config"].decode(); model = files["3D/3dmodel.model"].decode()
    for oid, body in re.findall(r'<object id="(\d+)">(.*?)</object>', ms, re.S):
        part = re.search(r'<part id="(\d+)"', body).group(1); src = re.search(r'key="source_file" value="([^"]*)"', body).group(1)
        off = [float(re.search(r'key="source_offset_%s" value="([^"]*)"' % a, body).group(1)) for a in "xyz"]
        comp = re.search(r'<object id="%s" [^>]*>\s*<components>\s*<component p:path="([^"]+)"' % oid, model, re.S)
        path = comp.group(1).lstrip("/")
        if src not in srcs: raise SystemExit(f"no source given for {src} (object {oid})")
        vs, ts = source_mesh(srcs[src]); n = int(oid)
        xml = [HEAD, f'  <object id="{part}" p:UUID="{n:04x}0000-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n    <vertices>\n']
        xml += [f'     <vertex x="{x-off[0]:.8g}" y="{y-off[1]:.8g}" z="{z-off[2]:.8g}"/>\n' for x, y, z in vs]
        xml += ['    </vertices>\n    <triangles>\n'] + [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in ts] + ['    </triangles>\n', TAIL]
        files[path] = "".join(xml).encode(); print(f"object {oid} ({src}): {len(vs)} verts, {len(ts)} tris -> {path}")
    _write_zip(out, files); print("written:", out)

if __name__ == "__main__":
    main()
