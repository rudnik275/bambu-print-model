#!/usr/bin/env python3
"""Build and modify Bambu Studio project files (.3mf) without the UI.

  assemble <autosave_dir> <out.3mf>          full project from a Studio autosave
                                             (its settings-only .3mf + 3D/Objects/*.model)
  variant <in.3mf> <out.3mf> [--keep 1,2,3] [--set key=value ...] [--title T]
                                             keep only these object ids (as in model_settings.config),
                                             override settings in Metadata/project_settings.config
  show <in.3mf>                              objects and their ids
  retarget <in.3mf> <out.3mf> --machine M [--process P] [--filament F] [--bed B]
                                             move a foreign project (MakerWorld, another printer) onto your
                                             presets: the full preset values are written into the project,
                                             the author's *process* overrides (different_settings_to_system)
                                             are kept, their filament/machine overrides are dropped. Needs a
                                             machine G-code snapshot for M (see `snapshot`)
  snapshot <studio-saved.3mf> [slug]         store the trusted machine G-code of a project that Bambu Studio
                                             itself saved: every machine `*_gcode` key of its
                                             Metadata/project_settings.config -> <home>/machine-gcode/<slug>.json
                                             (home = $PRINT_MODEL_HOME or ~/.print-model; slug derived from
                                             printer_settings_id, e.g. "Bambu Lab A1 mini 0.4 nozzle" -> A1mini)
  move <in.3mf> <out.3mf> --at x,y [--id N]  put an object's footprint centre at (x, y) on the bed — foreign
                                             projects sit in their printer's coordinates (an H2S project at
                                             x up to 350 slices as "outside" on a 180 mm bed); default: first item
  ranges <in.3mf> <out.3mf> <obj> <min_z> <max_z> key=value ...
                                             height-range modifier (Studio: "Height range modifier"): per-object
                                             settings for z in [min_z, max_z] of the object, e.g. layer_height=0.08
                                             on a flat crown — the one way to vary layer height outside the GUI
                                             (layer_heights_profile.txt is ignored by the CLI). <obj> is the object's
                                             1-based ORDER in 3D/3dmodel.model (as `show` prints it), not its id;
                                             ranges of one object accumulate
  gcode3mf <in.gcode.3mf> <out.gcode.3mf>    turn a CLI slice export into what Studio calls a sliced file:
                                             geometry stripped, plate points at the G-code — Studio then opens
                                             it in Preview with "Print plate" active instead of as a project

Values for --set are written as strings; list-type keys (filament ones) take a single value.

Trap (variant): when Studio loads a 3MF it resets every key NOT listed in different_settings_to_system
(three ";"-joined lists: process; filament; machine) back to the current system preset — an edit that is not
listed there silently disappears. `variant --set` maintains the list itself; when editing the config by other
means, add the key to the right tab's list. A CLI slice (--slice 0 --export-3mf) is the check that the value
was actually applied.

Trap (retarget): Studio 2.x keeps the real Bambu machine G-code out of the system machine JSON, so resolving
the machine preset (bbs_resolve.py) yields the generic fdm_machine_common placeholder: Ender-style start
G-code with an un-indented `M109 S205` and a purge line off the bed, and almost no `M1002`. A project printed
with it heats to the wrong temperature, skips the nozzle wipe and purges into the void. That is why the real
blobs come only from a project Bambu Studio itself saved for that printer, stored once with `snapshot`.
Sanity check on any G-code before printing: `M1002` should appear hundreds of times and `^M109 S205` never;
an *indented* `M109 S205` inside the filament-change block is part of Bambu's own macro and is fine."""
import json, os, re, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def _read_zip(p):
    z = zipfile.ZipFile(p); return {n: z.read(n) for n in z.namelist()}
def _write_zip(p, files):
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ["[Content_Types].xml"] + [k for k in files if k != "[Content_Types].xml"]:
            if n in files: z.writestr(n, files[n])

def assemble(src, out):
    files = _read_zip(os.path.join(src, ".3mf"))
    objdir = os.path.join(src, "3D", "Objects")
    for f in sorted(os.listdir(objdir)):
        if f.endswith(".model"): files["3D/Objects/" + f] = open(os.path.join(objdir, f), "rb").read()
    _write_zip(out, files); print("assembled:", out, "objects:", [f for f in files if f.startswith("3D/Objects/")])

def show(p):
    files = _read_zip(p); ms = files["Metadata/model_settings.config"].decode()
    for oid, body in re.findall(r'<object id="(\d+)">(.*?)</object>', ms, re.S):
        name = re.search(r'key="name" value="([^"]*)"', body); src = re.search(r'key="source_file" value="([^"]*)"', body)
        print(f"  id {oid}: {name.group(1) if name else '?'}  ({src.group(1) if src else '-'})")

def variant(inp, out, keep=None, sets=(), title=None):
    files = _read_zip(inp)
    model = files["3D/3dmodel.model"].decode(); ms = files["Metadata/model_settings.config"].decode()
    if keep is not None:
        all_ids = re.findall(r'<object id="(\d+)">', ms); drop = [i for i in all_ids if i not in keep]
        for i in drop:
            model = re.sub(r'\s*<item objectid="%s" [^>]*/>' % i, "", model)
            m = re.search(r'<object id="%s" [^>]*>.*?</object>\s*' % i, model, re.S)
            path = re.search(r'p:path="([^"]+)"', m.group(0)).group(1) if m else None
            if m: model = model.replace(m.group(0), "")
            ms = re.sub(r'\s*<object id="%s">.*?</object>' % i, "", ms, flags=re.S)
            ms = re.sub(r'\s*<model_instance>\s*<metadata key="object_id" value="%s"/>.*?</model_instance>' % i, "", ms, flags=re.S)
            ms = re.sub(r'\s*<assemble_item object_id="%s" [^>]*/>' % i, "", ms)
            if path:
                files.pop(path.lstrip("/"), None)
                rels = files.get("3D/_rels/3dmodel.model.rels")
                if rels: files["3D/_rels/3dmodel.model.rels"] = re.sub(r'\s*<Relationship Target="%s" [^>]*/>' % re.escape(path), "", rels.decode()).encode()
        print("kept objects:", keep, "dropped:", drop)
    if title: model = re.sub(r'(<metadata name="Title">)[^<]*(</metadata>)', r'\g<1>%s\g<2>' % title, model)
    files["3D/3dmodel.model"] = model.encode(); files["Metadata/model_settings.config"] = ms.encode()
    if sets:
        cfg = json.loads(files["Metadata/project_settings.config"])
        for k, v in sets:
            if k not in cfg: print("warn: unknown key", k)
            cfg[k] = [v] if isinstance(cfg.get(k), list) else v
            print(f"set {k} = {cfg[k]}")
        # Studio marks changed keys per tab in different_settings_to_system = [process, filament, machine]
        # (";"-joined key names). Keeping it in sync is what makes the value survive loading (see the trap
        # in the module docstring) and gives the orange "modified" markers in the UI.
        from bbs_resolve import resolve
        fil = cfg.get("filament_settings_id", ["?"]); fil = fil[0] if isinstance(fil, list) else fil
        bases = [resolve("process", cfg.get("print_settings_id", "")), resolve("filament", fil), resolve("machine", cfg.get("printer_settings_id", ""))]
        diff = cfg.get("different_settings_to_system") or ["", "", ""]
        for k, v in sets:
            hit = [i for i, b in enumerate(bases) if k in b]
            i = hit[0] if hit else 0                       # keys absent from every base (project-only) count as process
            base_v = bases[i].get(k); base_v = base_v[0] if isinstance(base_v, list) else base_v
            if base_v is None or str(base_v) != str(v):
                keys = [x for x in diff[i].split(";") if x]
                if k not in keys: keys.append(k)
                diff[i] = ";".join(keys)
        cfg["different_settings_to_system"] = diff; print("different_settings_to_system =", diff)
        files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4, ensure_ascii=False).encode()
    _write_zip(out, files); print("written:", out)

# keys that describe a preset file, not a printing setting — never copied into a project
_PRESET_META = {"name", "from", "version", "inherits", "instantiation", "type", "setting_id", "description",
                "filament_id", "compatible_printers", "compatible_printers_condition", "compatible_prints",
                "compatible_prints_condition", "print_settings_id", "filament_settings_id", "printer_settings_id",
                "is_custom_defined", "_chain"}

def _slug(machine):
    """store name of a printer's G-code snapshot: 'Bambu Lab A1 mini 0.4 nozzle' -> 'A1mini'"""
    return machine.replace("Bambu Lab ", "").replace(" 0.4 nozzle", "").replace(" ", "")

def _gcode_store(slug):
    from paths import home
    return os.path.join(home(), "machine-gcode", slug + ".json")

def _is_machine_gcode(k):
    # machine-tab blobs are strings; filament_start/end_gcode are filament-tab lists and come from the filament preset
    return k.endswith("_gcode") and not k.startswith("filament_")

def snapshot(inp, slug=None):
    """Store the machine G-code of a project Bambu Studio saved (see the retarget trap in the module docstring)."""
    files = _read_zip(inp); cfg = json.loads(files["Metadata/project_settings.config"])
    machine = cfg.get("printer_settings_id")
    if not machine: raise SystemExit("no printer_settings_id in Metadata/project_settings.config — not a Studio project?")
    start = cfg.get("machine_start_gcode") or ""
    m1002 = start.count("M1002"); placeholder = re.search(r"^M109 S205", start, re.M) is not None
    if machine.startswith("Bambu Lab") and (placeholder or m1002 < 5):
        raise SystemExit(f"{inp}: machine_start_gcode looks like the generic placeholder (M1002 x{m1002}, un-indented M109 S205: "
                         f"{placeholder}), not Bambu's real start G-code. Save the project from Bambu Studio itself "
                         f"(File > Save project) with '{machine}' selected and snapshot that file.")
    app = re.search(r'<metadata name="Application">([^<]*)</metadata>', files.get("3D/3dmodel.model", b"").decode("utf8", "ignore"))
    out = {"_source": f"{os.path.basename(inp)} — saved by {app.group(1) if app else 'Bambu Studio'}, printer_settings_id {machine}",
           "_why": "Studio 2.x keeps the real Bambu machine G-code out of the system machine JSON; resolving the preset falls "
                   "through to the generic fdm_machine_common placeholder (M109 S205, purge line off the bed). Trusted blobs "
                   "come only from a project Bambu Studio itself saved for this printer.",
           "printer_settings_id": machine}
    for k in sorted(cfg):
        if _is_machine_gcode(k): out[k] = cfg[k]
    slug = slug or _slug(machine); path = _gcode_store(slug)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"snapshot: {machine} -> {path}")
    print(f"  {len(out) - 3} gcode keys; machine_start_gcode {len(start)} chars, M1002 x{m1002}"
          + ("" if machine.startswith("Bambu Lab") else " (non-Bambu printer: no placeholder check applied)"))

def retarget(inp, out, machine, process=None, filament=None, bed=None):
    from bbs_resolve import resolve
    if not machine: raise SystemExit("retarget needs --machine \"<printer preset name>\"")
    files = _read_zip(inp); cfg = json.loads(files["Metadata/project_settings.config"])
    m = resolve("machine", machine)
    process = process or m["default_print_profile"]
    dfp = m["default_filament_profile"]; filament = filament or (dfp[0] if isinstance(dfp, list) else dfp)
    p = resolve("process", process); f = resolve("filament", filament)
    for kind, base in (("process", p), ("filament", f)):
        cps = base.get("compatible_printers") or []
        if cps and machine not in cps: raise SystemExit(f"{kind} preset '{base['name']}' is not for '{machine}': {cps}")

    # the author's overrides live in different_settings_to_system = [process; filament; machine] (";"-joined).
    # Process tweaks describe the model (walls, supports) — keep; filament/machine ones describe their setup — drop.
    # Keys like precise_outer_wall live only in the project (Studio defaults, absent from preset files) — keep those too.
    diff = cfg.get("different_settings_to_system") or ["", "", ""]
    old_n = len(cfg.get("filament_settings_id") or [1])   # the author's filament count (AMS projects: 4)
    keep = [k for k in diff[0].split(";") if k and k in cfg]
    author = {k: cfg[k] for k in keep}
    dropped = [k for k in diff[0].split(";") if k and k not in cfg] + [k for k in (diff[1] + ";" + diff[2]).split(";") if k]
    print("was    :", cfg.get("printer_settings_id"), "/", cfg.get("print_settings_id"), "/", cfg.get("filament_settings_id"))
    print("author :", author or "(no process overrides)")
    if dropped: print("dropped:", dropped)

    for base in (m, p, f):
        for k, v in base.items():
            if k not in _PRESET_META: cfg[k] = v
    # The resolved machine preset carries the generic placeholder G-code, not the printer's (module docstring):
    # overwrite the blobs from the snapshot store.
    slug = _slug(machine); gpath = _gcode_store(slug)
    if not os.path.exists(gpath):
        raise SystemExit(
            f"no trusted machine G-code snapshot for '{machine}' (expected {gpath}).\n"
            "Studio's system machine JSON hides the real start G-code, so it cannot be taken from the presets; a project\n"
            "retargeted without it would print with the generic placeholder (M109 S205, purge off the bed). To create the snapshot once:\n"
            f"  1. in Bambu Studio select the printer '{machine}' and open any model,\n"
            "  2. File > Save project (a .3mf),\n"
            f"  3. run: bbs_project.py snapshot that.3mf\n"
            "then run retarget again.")
    g = json.load(open(gpath, encoding="utf-8"))
    if g.get("printer_settings_id") and g["printer_settings_id"] != machine:
        print(f"warn   : snapshot {gpath} was taken from '{g['printer_settings_id']}', retargeting to '{machine}'")
    for k, v in g.items():
        if _is_machine_gcode(k) and v is not None: cfg[k] = v
    print("gcode  : machine blobs from", gpath, f"(start {len(cfg.get('machine_start_gcode', ''))} chars)")
    # Per-filament lists the author's setup left behind in project-only keys: a P1S project carries two extruder
    # variants (2-element lists), an AMS project carries one value per filament (4 — filament_colour, filament_map,
    # pressure_advance, fan keys, a 4x4 flush matrix). The target is a single-filament plate, so every project-only
    # list of the author's filament count is cut to its first value — otherwise Studio shows four filament slots
    # for a one-filament plate.
    for k, v in list(cfg.items()):
        if not isinstance(v, list) or len(v) < 2 or any(k in b for b in (m, p, f)): continue
        if k == "flush_volumes_matrix": cfg[k] = ["0"]
        elif len(v) == old_n or k.startswith("filament_"): cfg[k] = v[:1]
    cfg.update(author)
    cfg["printer_settings_id"] = machine; cfg["print_settings_id"] = process; cfg["filament_settings_id"] = [filament]
    cfg["print_compatible_printers"] = p.get("compatible_printers") or [machine]
    if f.get("filament_id"): cfg["filament_ids"] = [f["filament_id"]]
    if bed: cfg["curr_bed_type"] = bed
    cfg["different_settings_to_system"] = [";".join(keep), "", ""]
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4, ensure_ascii=False).encode()
    _write_zip(out, files)
    print("now    :", machine, "/", process, "/", filament, "/ bed:", cfg.get("curr_bed_type"))
    print("different_settings_to_system =", cfg["different_settings_to_system"]); print("written:", out)

def move(inp, out, at, oid=None):
    """shift a build item's translation so its footprint centre lands at `at` (mesh read with all transforms)"""
    from mesh_slopes import load
    files = _read_zip(inp); model = files["3D/3dmodel.model"].decode()
    items = re.findall(r'<item objectid="(\d+)"', model)
    oid = oid or items[0]
    vs = [v for name, verts, _ in load(inp) if name.split()[1].split("/")[0] == oid for v in verts]
    if not vs: raise SystemExit(f"no mesh for item {oid}; items: {items}")
    cx = (min(v[0] for v in vs) + max(v[0] for v in vs)) / 2; cy = (min(v[1] for v in vs) + max(v[1] for v in vs)) / 2
    dx, dy = at[0] - cx, at[1] - cy
    def shift(m):
        t = m.group(2).split(); t[9] = f"{float(t[9]) + dx:.6f}"; t[10] = f"{float(t[10]) + dy:.6f}"
        return m.group(1) + " ".join(t) + m.group(3)
    model, n = re.subn(r'(<item objectid="%s" [^>]*transform=")([^"]+)(")' % oid, shift, model)
    if n != 1: raise SystemExit(f"item {oid}: transform not found")
    files["3D/3dmodel.model"] = model.encode(); _write_zip(out, files)
    print(f"moved item {oid}: centre ({cx:.1f}, {cy:.1f}) -> ({at[0]:g}, {at[1]:g}), shift ({dx:+.1f}, {dy:+.1f}); written: {out}")

def ranges(inp, out, obj, z_lo, z_hi, sets):
    """Metadata/layer_config_ranges.xml (PrusaSlicer format, read by Studio and its CLI): <objects><object id=N>
    <range min_z max_z><option opt_key=..>value. N = 1-based ORDER of the object in 3D/3dmodel.model, not the id
    from model_settings.config: on a two-object project, id 2 addressed the second object of the model file
    while model_settings called it id 7."""
    files = _read_zip(inp); path = "Metadata/layer_config_ranges.xml"
    xml = files.get(path, b'<?xml version="1.0" encoding="utf-8"?>\n<objects>\n</objects>\n').decode()
    opts = "".join(f'   <option opt_key="{k}">{v}</option>\n' for k, v in sets)
    block = f'  <range min_z="{z_lo:g}" max_z="{z_hi:g}">\n{opts}  </range>\n'
    m = re.search(r'( <object id="%d">\n)(.*?)( </object>\n)' % obj, xml, re.S)
    xml = xml[:m.end(2)] + block + xml[m.end(2):] if m else xml.replace("</objects>", f' <object id="{obj}">\n{block} </object>\n</objects>')
    files[path] = xml.encode(); _write_zip(out, files)
    print(f"range on object {obj}: z {z_lo:g}..{z_hi:g} -> {dict(sets)}; written: {out}")

def gcode3mf(inp, out):
    """Studio's own "export sliced file" carries no mesh: <resources/> <build/> and a model_settings.config with
    only the <plate> block. With a mesh present it loads the file as a project (Prepare, Print greyed)."""
    files = _read_zip(inp)
    if "Metadata/plate_1.gcode" not in files: raise SystemExit("no Metadata/plate_1.gcode — slice first (--slice 0 --export-3mf)")
    for n in [k for k in files if k.startswith("3D/Objects/") or k.startswith("3D/_rels/")]: files.pop(n)
    model = files["3D/3dmodel.model"].decode()
    model = re.sub(r'\s+xmlns:p="[^"]*"', "", model); model = re.sub(r'\s+requiredextensions="p"', "", model)
    model = re.sub(r"<resources>.*</resources>", "<resources>\n </resources>", model, flags=re.S)
    model = re.sub(r"<build[^>]*>.*</build>|<build/>", "<build/>", model, flags=re.S)
    files["3D/3dmodel.model"] = model.encode()
    ms = files["Metadata/model_settings.config"].decode()
    plates = re.findall(r"<plate>.*?</plate>", ms, re.S)
    keep = []
    for p in plates:
        p = re.sub(r"\s*<model_instance>.*?</model_instance>", "", p, flags=re.S)
        m = re.search(r'key="plater_id" value="(\d+)"', p); i = m.group(1) if m else "1"
        if "pattern_bbox_file" not in p:
            p = p.replace("</plate>", f'  <metadata key="pattern_bbox_file" value="Metadata/plate_{i}.json"/>\n  </plate>')
        keep.append(p)
    files["Metadata/model_settings.config"] = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  ' + "\n  ".join(keep) + "\n</config>\n").encode()
    si = files.get("Metadata/slice_info.config")
    if si: files["Metadata/slice_info.config"] = si.replace(b'key="printer_model_id" value=""', b'key="printer_model_id" value="N1"')
    _write_zip(out, files); print("gcode-only 3mf:", out, "plates:", len(keep))

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    try:
        if a[0] == "assemble": assemble(a[1], a[2])
        elif a[0] == "show": show(a[1])
        elif a[0] == "snapshot": snapshot(a[1], a[2] if len(a) > 2 else None)
        elif a[0] == "gcode3mf": gcode3mf(a[1], a[2])
        elif a[0] == "ranges": ranges(a[1], a[2], int(a[3]), float(a[4]), float(a[5]), [tuple(s.split("=", 1)) for s in a[6:]])
        elif a[0] == "move":
            at = tuple(float(v) for v in a[a.index("--at") + 1].split(","))
            move(a[1], a[2], at, a[a.index("--id") + 1] if "--id" in a else None)
        elif a[0] == "retarget":
            opt = lambda n: a[a.index(n) + 1] if n in a else None
            retarget(a[1], a[2], opt("--machine"), opt("--process"), opt("--filament"), opt("--bed"))
        elif a[0] == "variant":
            keep = a[a.index("--keep") + 1].split(",") if "--keep" in a else None
            title = a[a.index("--title") + 1] if "--title" in a else None
            sets = [(s.split("=", 1)[0], s.split("=", 1)[1]) for i, s in enumerate(a) if i > 0 and a[i - 1] == "--set"]
            variant(a[1], a[2], keep, sets, title)
        else: sys.exit(f"unknown subcommand: {a[0]}\n\n{__doc__}")
    except (IndexError, ValueError) as e:
        sys.exit(f"bad arguments for '{a[0]}' ({e})\n\n{__doc__}")
