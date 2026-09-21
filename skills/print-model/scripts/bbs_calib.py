#!/usr/bin/env python3
"""Build Bambu Studio calibration plates without the GUI wizard, replicating CalibUtils.cpp.

  bbs_calib.py flow1 <base_project.3mf> <out.3mf>            flow-rate coarse: 9 blocks, -20..+20 %
  bbs_calib.py flow2 <base_project.3mf> <out.3mf> <coarse>   flow-rate fine: 10 blocks, -9..0 % on top of
                                                             the coarse flow ratio (e.g. 0.95)
  bbs_calib.py fix-sliced <sliced.gcode.3mf> [model_id]     set printer_model_id in a CLI-sliced file. Default N1 = A1 mini;
                                                             A1 N2S, P1P C11, P1S C12, X1C BL-P001, X1 BL-P002, X1E C13,
                                                             H2D O1D, H2S O1S (model_id of the machine_model JSON under
                                                             system/BBL/machine/ in Studio's data dir)
  bbs_calib.py temp <base.3mf> <out.3mf> <tower.stl> <t_hi> <t_lo>   temperature tower project (hot block at the bottom); the
                                                             wizard's full 350-mm tower is cut to the t_hi..t_lo blocks (mesh_cut.py)
  bbs_calib.py inject-temps <sliced.gcode.3mf> <t_hi>       M104 per 10 mm block after CLI slicing
  bbs_calib.py speed <base.3mf> <out.3mf> <f_lo> <f_hi> [lw lh]      max volumetric speed: single-wall spiral cylinder
  bbs_calib.py speed-ramp <sliced.gcode.3mf> <f_lo> <f_hi> [lw lh]   write the flow ramp into the sliced gcode; f_hi <= 26 if the
                                                             file goes through Studio: 2.8 silently refuses a gcode.3mf whose
                                                             volumetric flow exceeds ~26-28 mm3/s whatever the feedrate (4-30 and
                                                             20-40 on a 0.6x0.28 line opened as an empty plate, 4-26 was fine);
                                                             above that, put the file on the SD card and start it from the printer

base_project supplies printer/filament/process settings (Metadata/project_settings.config) and the bed size —
its printable_area; blocks are laid out around the bed centre, 10 mm in from the edges.
Per-object settings follow the wizard: print_flow_ratio = 1 + k/100, wall_loops 3, top 5, bottom 1,
infill 35 %, monotonic top, no ironing, detect_thin_wall; global reduce_crossing_wall = 1.
The wizard's meshes come from Studio's bundled resources (calib/filament_flow, see paths.studio_resources_dir())."""
import json, os, re, shutil, subprocess, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbs_project import _read_zip, _write_zip
from bbs_rebuild import HEAD, TAIL
from paths import studio_resources_dir

def calib_dir():
    return os.path.join(studio_resources_dir(), "calib", "filament_flow")

def bed_box(base):
    """(x0, y0, x1, y1) of the base project's printable_area. Studio stores the polygon as a list
    ['0x0', '180x0', '180x180', '0x180'] in project_settings.config (a '0x0,180x0,...' string in G-code headers)."""
    cfg = json.loads(zipfile.ZipFile(base).read("Metadata/project_settings.config"))
    pa = cfg.get("printable_area")
    if not pa: raise SystemExit(f"{base}: no printable_area in Metadata/project_settings.config")
    if isinstance(pa, str): pa = pa.split(",")
    pts = [tuple(float(v) for v in p.split("x")) for p in pa]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)

def generic_objects(path):
    """objects of a plain 3MF: [(name, verts, tris)] with build transforms applied"""
    z = zipfile.ZipFile(path); x = z.read("3D/3dmodel.model").decode("utf8", "ignore")
    objs = {}
    for tag, body in re.findall(r'(<object [^>]*>)(.*?)</object>', x, re.S):
        oid = re.search(r'\bid="(\d+)"', tag).group(1); nm = re.search(r'\bname="([^"]*)"', tag)
        name = nm.group(1) if nm else f"object_{oid}"
        vs = [tuple(float(v) for v in m) for m in re.findall(r'<vertex\s+x="([^"]+)"\s+y="([^"]+)"\s+z="([^"]+)"', body)]
        ts = [tuple(int(v) for v in m) for m in re.findall(r'<triangle\s+v1="(\d+)"\s+v2="(\d+)"\s+v3="(\d+)"', body)]
        if vs: objs[oid] = (name, vs, ts)
    out = []
    for tag in re.findall(r'<item [^>]*>', x):
        oid = re.search(r'objectid="(\d+)"', tag).group(1); trm = re.search(r'transform="([^"]+)"', tag)
        tr = trm.group(1) if trm else "1 0 0 0 1 0 0 0 1 0 0 0"
        if oid not in objs: continue
        name, vs, ts = objs[oid]; t = [float(v) for v in tr.split()]
        vs = [(t[0]*a+t[3]*b+t[6]*c+t[9], t[1]*a+t[4]*b+t[7]*c+t[10], t[2]*a+t[5]*b+t[8]*c+t[11]) for a, b, c in vs]
        out.append((name, vs, ts))
    return out

def build(base, out, objects, per_obj, global_sets, title):
    """objects: [(name, verts, tris, (cx, cy))] placed with their bbox centre at (cx, cy), z on the bed"""
    files = _read_zip(base)
    cfg = json.loads(files["Metadata/project_settings.config"])
    diff = cfg.get("different_settings_to_system") or ["", "", ""]
    for k, v in global_sets.items():
        cfg[k] = v; keys = [x for x in diff[0].split(";") if x]; keys.append(k) if k not in keys else None; diff[0] = ";".join(keys)
    cfg["different_settings_to_system"] = diff
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4, ensure_ascii=False).encode()
    model = [files["3D/3dmodel.model"].decode().split("<resources>")[0] + "<resources>\n"]
    model[0] = re.sub(r'(<metadata name="Title">)[^<]*(</metadata>)', r'\g<1>%s\g<2>' % title, model[0])
    items, rels, ms_objs, ms_inst = [], [], [], []
    for n, (name, vs, ts, (cx, cy)) in enumerate(objects, 1):
        xs, ys, zs = [v[0] for v in vs], [v[1] for v in vs], [v[2] for v in vs]
        ox, oy, oz = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2   # Studio centres meshes
        part = 65536 + n; path = f"3D/Objects/object_{n}.model"
        xml = [HEAD, f'  <object id="{part}" p:UUID="{n:04x}0000-81cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <mesh>\n    <vertices>\n']
        xml += [f'     <vertex x="{x-ox:.6g}" y="{y-oy:.6g}" z="{z-oz:.6g}"/>\n' for x, y, z in vs]
        xml += ['    </vertices>\n    <triangles>\n'] + [f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>\n' for a, b, c in ts] + ['    </triangles>\n', TAIL]
        files[path] = "".join(xml).encode()
        model.append(f'  <object id="{n}" p:UUID="{n:08x}-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n   <components>\n'
                     f'    <component p:path="/{path}" objectid="{part}" p:UUID="{n:04x}0000-b206-40ff-9872-83e8017abed1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n   </components>\n  </object>\n')
        zh = (max(zs)-min(zs))/2
        items.append(f'  <item objectid="{n}" p:UUID="{n:08x}-b1ec-4553-aec9-835e5b724bb4" transform="1 0 0 0 1 0 0 0 1 {cx:.4f} {cy:.4f} {zh:.4f}" printable="1"/>\n')
        rels.append(f' <Relationship Target="/{path}" Id="rel-{n}" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n')
        meta = "".join(f'    <metadata key="{k}" value="{v}"/>\n' for k, v in per_obj(name).items())
        ms_objs.append(f'  <object id="{n}">\n    <metadata key="name" value="{name}"/>\n    <metadata key="extruder" value="1"/>\n{meta}'
                       f'    <part id="{part}" subtype="normal_part">\n      <metadata key="name" value="{name}"/>\n      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                       f'      <mesh_stat face_count="{len(ts)}" edges_fixed="0" degenerate_facets="0" facets_removed="0" facets_reversed="0" backwards_edges="0"/>\n    </part>\n  </object>\n')
        ms_inst.append(f'    <model_instance>\n      <metadata key="object_id" value="{n}"/>\n      <metadata key="instance_id" value="0"/>\n      <metadata key="identify_id" value="{100+n}"/>\n    </model_instance>\n')
    model.append(" </resources>\n <build>\n" + "".join(items) + " </build>\n</model>\n")
    files["3D/3dmodel.model"] = "".join(model).encode()
    files["3D/_rels/3dmodel.model.rels"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n' + "".join(rels) + "</Relationships>\n").encode()
    files["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "".join(ms_objs) +
        '  <plate>\n    <metadata key="plater_id" value="1"/>\n    <metadata key="plater_name" value=""/>\n    <metadata key="locked" value="false"/>\n    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
        + "".join(ms_inst) + "  </plate>\n</config>\n").encode()
    for k in list(files):
        if k.startswith("3D/Objects/") and not any(k == f"3D/Objects/object_{i}.model" for i in range(1, len(objects)+1)): del files[k]
    _write_zip(out, files); print("written:", out, "objects:", [o[0] for o in objects])

def flow_plate(base, out, pass_no, coarse=1.0):
    src = os.path.join(calib_dir(), f"flowrate-test-pass{pass_no}.3mf")
    objs = generic_objects(src)
    def mod(name):
        s = name[9:]; return -float(s[1:]) if s.startswith("m") else float(s)
    objs.sort(key=lambda o: mod(o[0]))
    w = max(max(v[0] for v in o[1]) - min(v[0] for v in o[1]) for o in objs)
    d = max(max(v[1] for v in o[1]) - min(v[1] for v in o[1]) for o in objs)
    x0, y0, x1, y1 = bed_box(base); bw, bd = x1 - x0, y1 - y0; bcx, bcy = (x0 + x1) / 2, (y0 + y1) / 2
    px, py = w + 5, d + 5                      # pitch = block + 5 mm gap
    uw, ud = bw - 20, bd - 20                  # keep 10 mm from the edges (purge line / exclusion corner)
    cols = max(1, min(4, int(uw // px))); rows = -(-len(objs) // cols)
    if rows * py > ud: raise SystemExit(f"{len(objs)} blocks of {w:.0f}x{d:.0f} mm do not fit the {bw:g}x{bd:g} mm bed")
    placed = []
    for i, (name, vs, ts) in enumerate(objs):
        r, c = divmod(i, cols)
        cx = bcx + (c - (cols-1)/2) * px; cy = bcy + ((rows-1)/2 - r) * py
        placed.append((name, vs, ts, (cx, cy)))
    def per_obj(name):
        return {"print_flow_ratio": f"{coarse * (1 + mod(name)/100):.4f}", "wall_loops": "3", "top_shell_layers": "5",
                "bottom_shell_layers": "1", "sparse_infill_density": "35%", "ironing_type": "no ironing",
                "top_surface_pattern": "monotonic", "detect_thin_wall": "1"}
    build(base, out, placed, per_obj, {"reduce_crossing_wall": "1"}, f"Flow rate pass {pass_no}")
    print("layout: %d objects on a %gx%g mm bed, block %.0fx%.0f mm, %d per row, pitch %.0f/%.0f mm; order back(+Y)->front, left->right: "
          % (len(objs), bw, bd, w, d, cols, px, py) + " | ".join(f"{mod(o[0]):+.0f}%" for o in objs))

def stl_mesh(path):
    """binary STL -> (verts, tris) with shared vertices"""
    import struct
    f = open(path, "rb"); f.read(80); n = struct.unpack("<I", f.read(4))[0]
    idx, vs, ts = {}, [], []
    for _ in range(n):
        v = struct.unpack("<12f", f.read(50)[:48]); tri = []
        for j in range(3):
            key = (round(v[3+3*j], 5), round(v[4+3*j], 5), round(v[5+3*j], 5))
            if key not in idx: idx[key] = len(vs); vs.append(key)
            tri.append(idx[key])
        ts.append(tuple(tri))
    return vs, ts

TOWER_TOP = 350   # Studio's temperature_tower.stl: 35 blocks of 10 mm, labels 350 °C (bed) -> 180 °C (top)

def _mesh_cut(stl, dst, z_lo, z_hi):
    """run mesh_cut.py: through uv when available (the script declares its deps, PEP 723), else the current python"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mesh_cut.py")
    uv = shutil.which("uv")
    cmd = [uv, "run", "--quiet", script] if uv else [sys.executable, script]
    subprocess.run(cmd + [stl, dst, str(z_lo), str(z_hi)], check=True)

def tower_range(stl, t_hi, t_lo):
    """cut the t_hi..t_lo blocks out of the full wizard tower (CalibUtils::calib_temp_tower); returns the STL to use"""
    import tempfile
    vs, _ = stl_mesh(stl); z0 = min(v[2] for v in vs); h = max(v[2] for v in vs) - z0
    if abs(h - (TOWER_TOP - 180) / 5 * 10 - 10) > 1: return stl          # not the full 35-block tower: use as is
    if t_hi % 5 or t_lo % 5 or not 180 <= t_lo <= t_hi <= TOWER_TOP: raise SystemExit("tower temps must be multiples of 5 within 180..350")
    z_lo = z0 + (TOWER_TOP - t_hi) / 5 * 10 + 0.01; z_hi = z0 + (TOWER_TOP - t_lo) / 5 * 10 + 10 + 0.01   # +eps: off the block faces, as the wizard does
    dst = os.path.join(tempfile.gettempdir(), f"temp_tower_{t_hi}_{t_lo}.stl")
    _mesh_cut(stl, dst, z_lo, z_hi)
    return dst

def temp_plate(base, out, stl, t_hi, t_lo):
    """temperature tower project: hottest block at the bottom, -5 °C per 10 mm (wizard convention)"""
    vs, ts = stl_mesh(tower_range(stl, t_hi, t_lo))
    x0, y0, x1, y1 = bed_box(base)
    per_obj = lambda name: {"brim_type": "outer_only"}
    cfg_sets = {}
    build(base, out, [("temp_tower_%d_%d" % (t_hi, t_lo), vs, ts, ((x0 + x1) / 2, (y0 + y1) / 2))], per_obj, cfg_sets, "Temperature tower %d-%d" % (t_hi, t_lo))
    # filament temps live in list-type keys: set both to t_hi and mark them modified on the filament tab
    files = _read_zip(out); cfg = json.loads(files["Metadata/project_settings.config"])
    for k in ("nozzle_temperature", "nozzle_temperature_initial_layer"): cfg[k] = [str(t_hi)]
    diff = cfg.get("different_settings_to_system") or ["", "", ""]; diff[1] = "nozzle_temperature;nozzle_temperature_initial_layer"
    cfg["different_settings_to_system"] = diff
    # temperature steps as per-layer custom G-code, so Studio's own Slice keeps them (no post-injection needed)
    layers = "".join(f'  <layer top_z="{10*j + 0.2:.2f}" type="4" extruder="1" color="" extra="M104 S{t_hi - 5*j}" gcode="M104 S{t_hi - 5*j}"/>\n' for j in range(1, (t_hi - t_lo)//5 + 1))
    files["Metadata/custom_gcode_per_layer.xml"] = ('<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n <plate>\n  <plate_info id="1"/>\n' + layers + '  <mode value="SingleExtruder"/>\n </plate>\n</custom_gcodes_per_layer>\n').encode()
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4, ensure_ascii=False).encode(); _write_zip(out, files)
    print("blocks:", (t_hi - t_lo)//5 + 1, "| block j (from bed) = %d - 5*j °C | custom_gcode_per_layer.xml written" % t_hi)

def inject_temps(sliced, t_hi, block_mm=10.0):
    """after CLI slicing: M104 at every block boundary of the tower gcode; refresh the md5"""
    import hashlib
    files = _read_zip(sliced); g = files["Metadata/plate_1.gcode"].decode("utf8", "ignore").splitlines()
    out, cur, n = [], None, 0
    for line in g:
        out.append(line)
        if line.startswith("; Z_HEIGHT:"):
            z = float(line.split(":")[1]); t = t_hi - 5 * int((z - 0.001) // block_mm)
            if t != cur: out.append(f"M104 S{t} ; temp tower block"); cur = t; n += 1
    data = ("\n".join(out) + "\n").encode()
    files["Metadata/plate_1.gcode"] = data; files["Metadata/plate_1.gcode.md5"] = hashlib.md5(data).hexdigest().upper().encode()
    _write_zip(sliced, files); print("M104 inserted:", n, "times; md5 refreshed")

def cylinder_mesh(d=40.0, h=60.0, n=144):
    """closed cylinder (solid) — spiral vase mode turns it into a single-wall tube"""
    import math
    vs, ts = [], []
    for z in (0.0, h):
        for i in range(n):
            a = 2*math.pi*i/n; vs.append((d/2*math.cos(a), d/2*math.sin(a), z))
    vs.append((0, 0, 0.0)); vs.append((0, 0, h)); cb, ct = 2*n, 2*n+1
    for i in range(n):
        j = (i+1) % n
        ts.append((i, j, n+i)); ts.append((j, n+j, n+i))          # side
        ts.append((cb, j, i)); ts.append((ct, n+i, n+j))          # caps
    return vs, ts

def speed_plate(base, out, f_lo, f_hi, lw=0.42, lh=0.2, d=40.0, h=60.0):
    """max volumetric speed test: single-wall spiral cylinder; the flow ramp is written into the
    sliced gcode afterwards by speed_ramp() (print the sliced file, do not re-slice in Studio).
    lw/lh: a thicker line keeps the feedrate low for high flows (0.6 x 0.28: 40 mm3/s = 238 mm/s) — a 40 mm
    circle cannot hold much above 300 mm/s; max_layer_height 0.28. Studio still refuses the file (flow > ~26-28
    mm3/s), so such a plate is printed from the SD card."""
    vs, ts = cylinder_mesh(d, h)
    x0, y0, x1, y1 = bed_box(base)
    per_obj = lambda name: {"brim_type": "outer_only"}
    sets = {"spiral_mode": "1", "wall_loops": "1", "top_shell_layers": "0", "bottom_shell_layers": "2", "sparse_infill_density": "0%",
            "outer_wall_speed": str(int(f_hi/(lw*lh))), "slow_down_layer_time": "0", "enable_overhang_speed": "0",
            "only_one_wall_top": "0", "resolution": "0.05"}
    if (lw, lh) != (0.42, 0.2):
        sets.update({"layer_height": str(lh), "initial_layer_print_height": str(lh), "line_width": str(lw), "outer_wall_line_width": str(lw),
                     "inner_wall_line_width": str(lw), "initial_layer_line_width": str(lw)})
    build(base, out, [("mvs_%d_%d" % (f_lo, f_hi), vs, ts, ((x0 + x1) / 2, (y0 + y1) / 2))], per_obj, sets, "MVS test %d-%d" % (f_lo, f_hi))
    files = _read_zip(out); cfg = json.loads(files["Metadata/project_settings.config"])
    cfg["filament_max_volumetric_speed"] = ["50"]; cfg["slow_down_for_layer_cooling"] = ["0"]; cfg["slow_down_layer_time"] = ["0"]
    diff = cfg.get("different_settings_to_system") or ["", "", ""]
    keys = [k for k in diff[1].split(";") if k] + [k for k in ("filament_max_volumetric_speed", "slow_down_for_layer_cooling", "slow_down_layer_time") if k not in diff[1].split(";")]
    diff[1] = ";".join(keys)                       # append: the base's own filament overrides (temperature, flow) must survive
    cfg["different_settings_to_system"] = diff
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4, ensure_ascii=False).encode(); _write_zip(out, files)
    print("mvs plate: ramp %d -> %d mm3/s over z 0.4..%.1f (line %.2f x %.2f => %.0f..%.0f mm/s)" % (f_lo, f_hi, h, lw, lh, f_lo/(lw*lh), f_hi/(lw*lh)))

def speed_ramp(sliced, f_lo, f_hi, z0=0.4, lw=0.42, lh=0.2):
    """rewrite F of extrusion moves per layer so volumetric flow ramps linearly from f_lo at z0 to f_hi at the top"""
    import hashlib
    files = _read_zip(sliced); g = files["Metadata/plate_1.gcode"].decode("utf8", "ignore").splitlines()
    zs = [float(l.split(":")[1]) for l in g if l.startswith("; Z_HEIGHT:")]; top = max(zs)
    out, z, n = [], 0.0, 0
    for line in g:
        if line.startswith("; Z_HEIGHT:"): z = float(line.split(":")[1])
        if z > z0 and line.startswith("G1 ") and " E" in line and ("X" in line or "Y" in line) and not line.startswith("G1 E"):
            e = re.search(r"\bE(-?[\d.]+)", line)
            if e and float(e.group(1)) > 0:
                flow = f_lo + (f_hi - f_lo) * (z - z0) / (top - z0); f = int(round(flow / (lw*lh) * 60))
                line = re.sub(r"\bF[\d.]+", "F%d" % f, line) if re.search(r"\bF[\d.]+", line) else line + " F%d" % f; n += 1
        out.append(line)
    data = ("\n".join(out) + "\n").encode()
    files["Metadata/plate_1.gcode"] = data; files["Metadata/plate_1.gcode.md5"] = hashlib.md5(data).hexdigest().upper().encode()
    _write_zip(sliced, files)
    print("speed ramp applied to %d moves; top z %.1f; flow(z) = %g + %g*(z-%g)/%g mm3/s" % (n, top, f_lo, f_hi-f_lo, z0, top-z0))

def fix_sliced(path, model_id="N1"):
    """CLI export leaves printer_model_id empty in slice_info.config; the printer wants it (see the docstring for ids)."""
    f = _read_zip(path); s = f["Metadata/slice_info.config"].decode()
    f["Metadata/slice_info.config"] = s.replace('<metadata key="printer_model_id" value=""/>', f'<metadata key="printer_model_id" value="{model_id}"/>').encode()
    _write_zip(path, f); print("printer_model_id set:", path)

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    try:
        if a[0] == "flow1": flow_plate(a[1], a[2], 1)
        elif a[0] == "flow2": flow_plate(a[1], a[2], 2, float(a[3]))
        elif a[0] == "fix-sliced": fix_sliced(a[1], a[2] if len(a) > 2 else "N1")
        elif a[0] == "temp": temp_plate(a[1], a[2], a[3], int(a[4]), int(a[5]))
        elif a[0] == "inject-temps": inject_temps(a[1], int(a[2]))
        elif a[0] == "speed": speed_plate(a[1], a[2], float(a[3]), float(a[4]), *(float(x) for x in a[5:7]))
        elif a[0] == "speed-ramp":
            lw, lh = (float(a[4]), float(a[5])) if len(a) > 5 else (0.42, 0.2)
            speed_ramp(a[1], float(a[2]), float(a[3]), z0=2*lh, lw=lw, lh=lh)
        else: sys.exit(f"unknown subcommand: {a[0]}\n\n{__doc__}")
    except (IndexError, ValueError) as e:
        sys.exit(f"bad arguments for '{a[0]}' ({e})\n\n{__doc__}")
