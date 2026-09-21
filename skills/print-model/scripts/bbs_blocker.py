#!/usr/bin/env python3
"""Add a support-blocker box to an object of a Studio project (what the GUI does with "Add support blocker"):
no support is generated for overhangs inside the box, so trees stop growing into places you cannot clean
(between louvres, inside blinds) while the rest of the part keeps its supports. The box is given in BED
coordinates; the object's build transform must be a pure translation (bbs_calib.build makes such projects).
Written as an extra <component> of the object pointing at a second mesh in its 3D/Objects/object_N.model, plus a
<part ... subtype="support_blocker"> entry in model_settings.config — the layout Studio itself writes.

Usage: bbs_blocker.py <in.3mf> <out.3mf> <object order 1..n> x0 y0 z0 x1 y1 z1 [name]"""
import re, sys, zipfile

def _read(p):
    z = zipfile.ZipFile(p); return {n: z.read(n) for n in z.namelist()}

def _write(p, files):
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ["[Content_Types].xml"] + [k for k in files if k != "[Content_Types].xml"]:
            if n in files: z.writestr(n, files[n])

def box_mesh(x0, y0, z0, x1, y1, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    t = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v, t

def blocker(inp, out, order, box, name="support blocker"):
    files = _read(inp); model = files["3D/3dmodel.model"].decode(); ms = files["Metadata/model_settings.config"].decode()
    objs = re.findall(r'<object id="(\d+)" [^>]*type="model">\s*<components>(.*?)</components>', model, re.S)
    if order < 1 or order > len(objs): raise SystemExit(f"object order {order} out of 1..{len(objs)}")
    oid, comps = objs[order - 1]
    item = re.search(r'<item objectid="%s" [^>]*transform="([^"]+)"' % oid, model).group(1).split()
    if [round(float(v), 6) for v in item[:9]] != [1, 0, 0, 0, 1, 0, 0, 0, 1]: raise SystemExit("object is rotated in the build; give the box in its local frame instead")
    tx, ty, tz = (float(v) for v in item[9:12])
    first = re.search(r'<component p:path="([^"]+)" objectid="(\d+)"', comps); path, base_part = first.group(1).lstrip("/"), int(first.group(2))
    used = [int(i) for i in re.findall(r'<component [^>]*objectid="(\d+)"', comps)]; pid = max(used) + 1
    x0, y0, z0, x1, y1, z1 = box
    vs, ts = box_mesh(x0 - tx, y0 - ty, z0 - tz, x1 - tx, y1 - ty, z1 - tz)
    mesh = (f'  <object id="{pid}" p:UUID="{pid:08x}-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n    <vertices>\n'
            + "".join(f'     <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>\n' for x, y, z in vs)
            + '    </vertices>\n    <triangles>\n' + "".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in ts)
            + '    </triangles>\n   </mesh>\n  </object>\n')
    part_xml = files[path].decode(); part_xml = part_xml.replace(" </resources>", mesh + " </resources>", 1); files[path] = part_xml.encode()
    comp = f'    <component p:path="/{path}" objectid="{pid}" p:UUID="{pid:08x}-b206-40ff-9872-83e8017abed1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
    model = model.replace(comps + "</components>", comps + comp + "</components>", 1) if comps.endswith("\n") else model.replace(comps + "</components>", comps + "\n" + comp + "   </components>", 1)
    files["3D/3dmodel.model"] = model.encode()
    part = (f'    <part id="{pid}" subtype="support_blocker">\n      <metadata key="name" value="{name}"/>\n'
            f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
            f'      <mesh_stat face_count="12" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n    </part>\n')
    m = re.search(r'(<object id="%s">.*?)(  </object>)' % oid, ms, re.S)
    ms = ms[:m.end(1)] + part + ms[m.end(1):]; files["Metadata/model_settings.config"] = ms.encode()
    _write(out, files)
    print(f"support blocker part {pid} on object {oid}: bed x {x0}..{x1} y {y0}..{y1} z {z0}..{z1} (local shift -({tx:.2f}, {ty:.2f}, {tz:.2f})); written: {out}")

if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 9 or a[0] in ("-h", "--help"): sys.exit(__doc__)
    blocker(a[0], a[1], int(a[2]), tuple(float(v) for v in a[3:9]), a[9] if len(a) > 9 else "support blocker")
