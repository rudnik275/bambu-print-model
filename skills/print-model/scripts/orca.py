#!/usr/bin/env python3
"""OrcaSlicer instead of Bambu Studio: presets moved over value for value, CLI slicing, projects the GUI keeps.

  orca.py presets [--dry-run]
      every Bambu Studio user preset -> an Orca user preset in <orca data>/user/default/<kind>/, value for value
  orca.py slice <out dir> <model.3mf|.stl> --machine M --process P --filament F [--set key=value ...]
      CLI slice with the three presets fully resolved: <out dir>/{plate_1.gcode, <model>.gcode.3mf, cli.log,
      result.json}; the exported project gets its different_settings_to_system filled; prints time, layers, the
      M1002 count and the plate
  orca.py fix-project <project.3mf> [out.3mf]
      fill different_settings_to_system of a CLI-exported Orca 2.4 project (in place, or into out.3mf)

Orca 2.5 and later (system presets shipped as <vendor>.opc caches, no BBL.json) — the script switches by itself:
- The CLI resolves `inherits` and `include` on its own, but a --load-settings file only by identity: the file must be a
  preset its bundle loaded, and that preset's resolved config replaces the file's contents. So `slice` hands the CLI a
  scratch data dir (Orca's system/ caches plus the chosen user presets) and the user presets' own files; a system preset
  gets a one-line user stand-in inheriting it, renamed back in the exported project. --set goes on the command line
  (--key=value), which the CLI applies last and records in different_settings_to_system itself.
- Resolving the chain here instead would miss `include`: Bambu machines keep their real start/end G-code in
  "<preset> template <key>" presets they include, and the inherits chain alone ends in fdm_machine_common's
  placeholder start (M109 S205, purge line at x 10) — the M1002 count of the start block exposes it.
- `presets` reads Orca's system parent through the CLI (--export-settings) and the version from the .opc stamp.
- The CLI writes result.json on Linux only; `slice` writes one for gcode_forecast.py (object boxes from the G-code).

Why each part exists (Orca 2.4.2 against Studio 02.08.02.61):
- Orca reads presets only at start, and silently skips a user preset without a `version` key.
- Orca's CLI takes the --load-settings files as complete configs: it does not follow `inherits`. It refuses the whole
  config on one out-of-range value — Studio's tree_support_wall_count = -1 ("auto") is outside Orca's 0..2.
- A CLI-exported project carries different_settings_to_system = ['', '', '']; Orca's GUI resets every key not listed
  there to the system preset of inherits_group when it opens the project — the same trap as Studio's. Listed are the
  keys the user presets set on top of the system ones, plus the --set keys.
- Machine G-code: Orca's system machine presets carry the real Bambu start/end blocks (Studio's preset files do not),
  so no snapshot is needed; the M1002 count still confirms it.
- Plate: the CLI has no plate option and slices for the Cool Plate unless the config carries `curr_bed_type`;
  `slice` takes the plate chosen in the Orca GUI (app.curr_bed_type) and prints it. The CLI also arranges the
  plate itself and may turn the part 90 degrees about Z; a project exported this way keeps that turn.
- Key names: Orca calls Studio's `no_slow_down_for_cooling_on_outwalls` (the quality package key) `dont_slow_down_outer_wall`;
  `presets` and `--set` translate the Studio name, Orca ignores it otherwise.
- Bridges, overhang walls, presets: references/orca.md."""
import glob, json, math, os, re, shutil, struct, subprocess, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import studio_data_dir, orca_data_dir, orca_cli, orca_profiles_dir

KINDS = ("machine", "process", "filament")
META = {"name", "inherits", "from", "setting_id", "base_id", "filament_id", "version", "instantiation", "description",
        "renamed_from", "type", "print_settings_id", "filament_settings_id", "printer_settings_id", "compatible_printers",
        "compatible_printers_condition", "compatible_prints", "compatible_prints_condition", "upward_compatible_machine",
        "filament_extruder_variant", "print_extruder_id", "print_extruder_variant", "is_custom_defined"}
REPLACE = {("tree_support_wall_count", "-1"): "0"}      # Studio-only values -> the nearest Orca accepts
RENAMES = {"no_slow_down_for_cooling_on_outwalls": "dont_slow_down_outer_wall"}   # Studio name -> Orca name, same meaning


def one(v):
    return v[0] if isinstance(v, list) and len(v) == 1 else v


def norm(v):
    """A value as it reads, not as it is spelled: Orca's resolved config writes 1 and 100% where Studio's JSON has
    1.0 and 100."""
    v = one(v)
    if isinstance(v, list):
        return [norm(x) for x in v]
    try:
        return float(str(v).strip().rstrip("%"))
    except ValueError:
        return str(v)


def _find(roots, kind, name):
    for root in roots:
        for pat in (f"{root}/{kind}/{glob.escape(name)}.json", f"{root}/{kind}/*/{glob.escape(name)}.json"):
            hits = glob.glob(pat)
            if hits:
                return json.load(open(hits[0]))
    return None


def chain(roots, kind, name):
    """[preset, parent, ...] as loaded JSON; SystemExit when a link is missing."""
    out = []
    while name:
        j = _find(roots, kind, name)
        if j is None:
            raise SystemExit(f"preset not found: {kind}/{name}")
        out.append(j)
        name = j.get("inherits")
    return out


def merged(c):
    m = {}
    for j in reversed(c):
        m.update(j)
    return m


def studio_roots():
    return [f"{studio_data_dir()}/system/BBL"]


def orca_system_roots():
    p = orca_profiles_dir()
    return [f"{p}/BBL", f"{p}/OrcaFilamentLibrary"]


def orca_roots():
    return sorted(glob.glob(f"{orca_data_dir()}/user/*")) + orca_system_roots()


def user_layer_keys(c):
    """Keys set by the user presets of a chain (those with from == User), i.e. what differs from the system root."""
    return {k for j in c if str(j.get("from", "")).lower() == "user" for k in j if k not in META}


# --- Orca 2.5+: the CLI resolves presets itself ----------------------------------------------------------------------

ID_KEY = {"process": "print_settings_id", "filament": "filament_settings_id", "machine": "printer_settings_id"}
STAND_IN = " - print-model"     # a user preset standing in for a system one; renamed back in the exported project


def _system_dirs():
    cli = orca_cli(required=False)
    d = os.path.dirname(os.path.realpath(cli)) if cli else None
    return [os.path.join(orca_data_dir(), "system")] + ([os.path.join(d, "..", "Resources", "profiles"),
                                                         os.path.join(d, "resources", "profiles")] if d else [])


def native():
    """True for Orca 2.5+, whose system presets are <vendor>.opc caches and whose CLI resolves presets itself."""
    return os.environ.get("ORCA_NATIVE", "") != "0" and any(glob.glob(os.path.join(glob.escape(p), "*.opc"))
                                                             for p in _system_dirs())


def vendor_version(vendor="BBL"):
    """The vendor profile version Orca stamps into user presets: <vendor>.json's "version", else the .opc cache's stamp
    (a 20-byte header, then u32 format, the u64-sized vendor name, the u64-sized version)."""
    for d in _system_dirs():
        if os.path.isfile(os.path.join(d, vendor + ".json")):
            return json.load(open(os.path.join(d, vendor + ".json")))["version"]
        if os.path.isfile(os.path.join(d, vendor + ".opc")):
            b = open(os.path.join(d, vendor + ".opc"), "rb").read(4096)
            i = 24; n = struct.unpack_from("<Q", b, i)[0]; i += 8 + n
            n = struct.unpack_from("<Q", b, i)[0]
            return b[i + 8:i + 8 + n].decode()
    raise SystemExit(f"no {vendor}.json or {vendor}.opc under " + ", ".join(_system_dirs()) + ": open OrcaSlicer once")


def user_preset_file(kind, name):
    """<orca data>/user/*/<kind>/<name>.json, the newest copy: Orca keeps default/ and one folder per signed-in account."""
    hits = glob.glob(f"{glob.escape(orca_data_dir())}/user/*/{kind}/{glob.escape(name)}.json")
    return max(hits, key=os.path.getmtime) if hits else None


def scratch_datadir(tmp, picks):
    """A data dir for the CLI: Orca's system/ caches plus the picked presets as user presets; returns {kind: file}.
    A user preset comes with every user preset above it; a system one gets a stand-in that only inherits it."""
    system = os.path.join(orca_data_dir(), "system")
    if not os.path.isdir(system):
        raise SystemExit(f"{system} missing: open OrcaSlicer once so it installs its system presets")
    if not os.path.isdir(os.path.join(tmp, "system")):
        shutil.copytree(system, os.path.join(tmp, "system"))
    files = {}
    for kind, name in picks:
        dst = os.path.join(tmp, "user", "default", kind)
        os.makedirs(dst, exist_ok=True)
        f, seen = user_preset_file(kind, name), set()
        if f:
            files[kind] = os.path.join(dst, os.path.basename(f))
            while f and f not in seen:
                seen.add(f)
                shutil.copy(f, os.path.join(dst, os.path.basename(f)))
                parent = json.load(open(f)).get("inherits")
                f = user_preset_file(kind, parent) if parent else None
        else:
            stand = name + STAND_IN
            files[kind] = os.path.join(dst, stand + ".json")
            json.dump({"type": kind, "name": stand, "inherits": name, "from": "User", "version": vendor_version(),
                       ID_KEY[kind]: [stand] if kind == "filament" else stand}, open(files[kind], "w"), indent=4)
    return files


_FLAT = {}


def orca_flat(kind, name):
    """A system preset as Orca 2.5 resolves it (inherits and include), through the CLI's --export-settings."""
    if (kind, name) not in _FLAT:
        with tempfile.TemporaryDirectory() as tmp:
            f = scratch_datadir(tmp, [(kind, name)])[kind]
            out = os.path.join(tmp, "flat.json")
            r = subprocess.run([orca_cli(), "--datadir", tmp, "--load-filaments" if kind == "filament" else "--load-settings",
                                f, "--export-settings", out], capture_output=True, text=True)
            if r.returncode or not os.path.exists(out):
                raise SystemExit(f"Orca could not resolve {kind}/{name} (exit {r.returncode}): "
                                 + " | ".join((r.stdout + r.stderr).strip().splitlines()[-3:]))
            _FLAT[(kind, name)] = json.load(open(out))
    return _FLAT[(kind, name)]


# --- presets -----------------------------------------------------------------------------------------------------

def bridges(keys):
    """Studio's bridge is Orca's thick bridge; Orca's internal bridge and overhang walls multiply its thread."""
    bf = float(one(keys.get("bridge_flow", "1")))
    inv = f"{1 / bf:.3f}".rstrip("0").rstrip(".")
    # internal_bridge_speed defaults to 150 % of bridge_speed — 15 mm/s under a slow 10 mm/s visible-bridge setting;
    # 50 is the speed Studio's system presets give every bridge, internal ones included
    out = {"thick_bridges": "1", "thick_internal_bridges": "1", "internal_bridge_speed": "50", "internal_bridge_flow": inv}
    if bf != 1:
        out.update({"set_other_flow_ratios": "1", "overhang_flow_ratio": inv})
    return out


def convert(kind, user, version):
    parent = user["inherits"]
    s = merged(chain(studio_roots(), kind, parent))
    o = orca_flat(kind, parent) if native() else merged(chain(orca_system_roots(), kind, parent))
    parity = {k: s[k] for k in s if k in o and k not in META and not k.endswith("_gcode") and norm(s[k]) != norm(o[k])}
    keys = {**parity, **{k: v for k, v in user.items() if k not in META}}
    keys = {RENAMES.get(k, k): v for k, v in keys.items()}
    if kind == "process":
        keys.update(bridges(keys))
    keys = {k: REPLACE.get((k, str(one(v))), v) for k, v in keys.items()}
    keys = {k: v for k, v in keys.items() if not (k == "tree_support_wall_count" and o.get(k) == v)}
    out = {"from": "User", "version": version, "inherits": parent, "name": user["name"],
           {"process": "print_settings_id", "filament": "filament_settings_id", "machine": "printer_settings_id"}[kind]:
               [user["name"]] if kind == "filament" else user["name"]}
    out.update(keys)
    return out, parity


def pending_delete(json_path):
    """A preset deleted through its .info file (sync_info = delete) keeps its JSON until Studio next starts — weeks, for
    someone who slices in Orca; carried over, it would come back as an Orca preset."""
    info = json_path[:-5] + ".info"
    return os.path.isfile(info) and any(l.split("=", 1)[1].strip() == "delete"
                                         for l in open(info) if l.startswith("sync_info"))


def presets(dry):
    version = vendor_version() if native() else json.load(open(f"{orca_profiles_dir()}/BBL.json"))["version"]
    dest = f"{orca_data_dir()}/user/default"
    for d in sorted(glob.glob(f"{studio_data_dir()}/user/*/")):
        for kind in KINDS:
            for f in sorted(glob.glob(f"{glob.escape(d)}{kind}/*.json")):
                user = json.load(open(f))
                if pending_delete(f):
                    print(f"{kind:8s} {user['name']:32s} skipped: marked sync_info = delete, Studio removes it on its next start")
                    continue
                out, parity = convert(kind, user, version)
                print(f"{kind:8s} {user['name']:32s} <- {user['inherits']}   parity: {sorted(parity) or '-'}")
                if not dry:
                    os.makedirs(f"{dest}/{kind}", exist_ok=True)
                    json.dump(out, open(f"{dest}/{kind}/{user['name']}.json", "w"), indent=4, ensure_ascii=False)
    if not dry:
        print(f"written to {dest}; restart Orca to load them")


# --- slice -------------------------------------------------------------------------------------------------------

def full_config(kind, name):
    c = chain(orca_roots(), kind, name)
    m = merged(c)
    m.pop("instantiation", None)
    users = [j for j in c if str(j.get("from", "")).lower() == "user"]
    m["from"] = "User" if users else "system"
    m["inherits"] = users[-1]["inherits"] if users else ""
    for k, v in list(m.items()):
        m[k] = REPLACE.get((k, str(one(v))), v)
    return m, user_layer_keys(c)


BED_TYPES = {"1": "Cool Plate", "2": "Engineering Plate", "3": "High Temp Plate", "4": "Textured PEI Plate"}


def orca_bed_type():
    """The plate chosen in the Orca GUI (app.curr_bed_type in OrcaSlicer.conf), as the config string."""
    try:
        return BED_TYPES.get(str(json.load(open(f"{orca_data_dir()}/OrcaSlicer.conf"))["app"]["curr_bed_type"]))
    except (OSError, KeyError, ValueError):
        return None


def run_cli(out, args):
    with open(os.path.join(out, "cli.log"), "w") as log:
        r = subprocess.run([orca_cli()] + args, stdout=log, stderr=subprocess.STDOUT)
    if r.returncode or not os.path.exists(os.path.join(out, "plate_1.gcode")):
        log = open(os.path.join(out, "cli.log"), errors="replace").read().splitlines()
        # a bad option makes the CLI print its whole help after the one line that says why
        why = [s for s in log if not s[:1].isspace()
               and re.search(r"invalid|can ?not|error|failed|need values", s, re.I)][:4] or log[-4:]
        raise SystemExit(f"slice failed (exit {r.returncode}):\n  " + "\n  ".join(why))


def slice_flat(out, model, project, machine, process, filament, sets):
    """Orca 2.4: the presets resolved here and handed over as complete configs."""
    cfg = {"machine": full_config("machine", machine), "process": full_config("process", process),
           "filament": full_config("filament", filament)}
    changed = {k: set(v[1]) for k, v in cfg.items()}
    for key, val in sets:
        kind = next((k for k in ("process", "filament", "machine") if key in cfg[k][0]), "process")
        cur = cfg[kind][0].get(key)
        cfg[kind][0][key] = [val] * len(cur) if isinstance(cur, list) else val
        changed[kind].add(key)
    paths = {}
    for k, (m, _) in cfg.items():
        paths[k] = os.path.join(out, f"_{k}.json")
        json.dump(m, open(paths[k], "w"), indent=1)
    run_cli(out, ["--slice", "0", "--load-settings", f"{paths['machine']};{paths['process']}",
                  "--load-filaments", paths["filament"], "--outputdir", out,
                  "--export-3mf", os.path.basename(project), os.path.abspath(model)])
    fix_project(project, extra=changed)


def slice_native(out, model, project, machine, process, filament, sets):
    """Orca 2.5+: the CLI resolves the presets from a scratch data dir; --set goes on its command line."""
    with tempfile.TemporaryDirectory() as tmp:
        f = scratch_datadir(tmp, [("machine", machine), ("process", process), ("filament", filament)])
        run_cli(out, ["--datadir", tmp, "--slice", "0", "--export-statistics",
                      "--load-settings", f"{f['machine']};{f['process']}", "--load-filaments", f["filament"]]
                + [f"--{k.replace('_', '-')}={v}" for k, v in sets]
                + ["--outputdir", out, "--export-3mf", os.path.basename(project), os.path.abspath(model)])
    unstand(project)


def unstand(path):
    """Put the system preset names back where a stand-in sliced: *_settings_id, and an empty inherits_group entry —
    the GUI then selects the system preset, and different_settings_to_system (vs the stand-in's parent) stays right."""
    z = zipfile.ZipFile(path)
    files = {n: z.read(n) for n in z.namelist()}
    z.close()
    cfg = json.loads(files["Metadata/project_settings.config"])
    order = ["print_settings_id"] + ["filament_settings_id"] * len(cfg.get("filament_settings_id") or []) + ["printer_settings_id"]
    group = cfg.get("inherits_group") or [""] * len(order)
    fixed = []
    for k in ("print_settings_id", "filament_settings_id", "printer_settings_id"):
        v = cfg.get(k)
        if v is None:
            continue
        vs = v if isinstance(v, list) else [v]
        for i, s in enumerate(vs):
            if isinstance(s, str) and s.endswith(STAND_IN):
                vs[i] = s[:-len(STAND_IN)]
                fixed.append(vs[i])
                gi = 0 if k == "print_settings_id" else len(order) - 1 if k == "printer_settings_id" else 1 + i
                if gi < len(group):
                    group[gi] = ""
        cfg[k] = vs if isinstance(v, list) else vs[0]
    if not fixed:
        return
    cfg["inherits_group"] = group
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4).encode()
    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as w:
        for n, b in files.items():
            w.writestr(n, b)
    os.replace(tmp, path)


def _arc_box(x, y, nx, ny, i, j, cw):
    """Axis extremes an arc G2 (cw) / G3 from (x, y) to (nx, ny) around (x + i, y + j) passes through, plus its ends."""
    cx, cy = x + i, y + j
    r = math.hypot(i, j)
    a0, a1 = math.atan2(y - cy, x - cx), math.atan2(ny - cy, nx - cx)
    sweep = (a0 - a1) % (2 * math.pi) if cw else (a1 - a0) % (2 * math.pi)
    sweep = sweep or 2 * math.pi
    pts = [(x, y), (nx, ny)]
    for q in range(4):
        a = q * math.pi / 2
        d = (a0 - a) % (2 * math.pi) if cw else (a - a0) % (2 * math.pi)
        if d <= sweep:
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def write_result(out, project):
    """result.json as Studio's CLI writes it, for gcode_forecast.py: Orca's CLI writes one on Linux only. Object boxes
    come from the G-code — extrusion between the object labels, arcs included — names from slice_info.config."""
    if os.path.exists(os.path.join(out, "result.json")):
        return
    names = {}
    try:
        si = zipfile.ZipFile(project).read("Metadata/slice_info.config").decode("utf8", "ignore")
        names = {int(i): n for i, n in re.findall(r'<object identify_id="(\d+)" name="([^"]*)"', si)}
    except (OSError, KeyError, zipfile.BadZipFile):
        pass
    boxes, cur, feat, x, y, z = {}, None, None, 0.0, 0.0, 0.0
    num = re.compile(r"([XYIJE])(-?[\d.]+)")
    for line in open(os.path.join(out, "plate_1.gcode"), errors="replace"):
        if line.startswith("; start printing object, unique label id: "):
            cur = int(line.rsplit(":", 1)[1])
        elif line.startswith("; stop printing object, unique label id"):
            cur = None
        elif line.startswith("; FEATURE:"):
            feat = line.split(":", 1)[1].strip()
        elif line.startswith("; Z_HEIGHT:"):
            z = float(line.split(":", 1)[1])
        elif line.startswith(("G1 ", "G2 ", "G3 ")):
            v = dict((k, float(n)) for k, n in num.findall(line.split(";", 1)[0]))
            nx, ny = v.get("X", x), v.get("Y", y)
            if v.get("E", 0) > 0 and feat != "Custom":     # Custom: the purge line, outside any object
                pts = _arc_box(x, y, nx, ny, v.get("I", 0), v.get("J", 0), line[1] == "2") if line[1] in "23" else [(x, y), (nx, ny)]
                b = boxes.setdefault(cur if cur is not None else 0, [1e9, 1e9, -1e9, -1e9, 0.0])
                for px, py in pts:
                    b[0], b[1], b[2], b[3] = min(b[0], px), min(b[1], py), max(b[2], px), max(b[3], py)
                b[4] = max(b[4], z)
            x, y = nx, ny
    if len(boxes) > 1:
        boxes.pop(0, None)      # skirt, prime tower: printed outside the labels, not an object (as in Studio's file)
    objs = [{"id": k, "name": names.get(k, f"object {k}"),
             "bbox": {"x": b[0], "y": b[1], "z": 0.0, "width": b[2] - b[0], "depth": b[3] - b[1], "height": b[4]}}
            for k, b in sorted(boxes.items())]
    json.dump({"error_string": "Success", "return_code": 0, "sliced_plates": [{"id": 1, "objects": objs}],
               "note": "written by orca.py from plate_1.gcode: Orca's CLI writes result.json on Linux only"},
              open(os.path.join(out, "result.json"), "w"), indent=1)


def slice_(out, model, machine, process, filament, sets):
    out = os.path.abspath(out)   # a relative --outputdir slices but the --export-3mf step then fails (exit 243)
    # The CLI knows no plate: without curr_bed_type it slices for the Cool Plate, and the first layer gets that
    # plate's temperature (35 C for PLA instead of 65 on the textured plate). Default to the plate chosen in the GUI.
    if not any(k == "curr_bed_type" for k, _ in sets):
        bed = orca_bed_type()
        if bed:
            sets = list(sets) + [("curr_bed_type", bed)]
        else:
            print('warning: plate unknown (no OrcaSlicer.conf) - pass --set "curr_bed_type=Textured PEI Plate"')
    sets = [(RENAMES.get(k, k), v) for k, v in sets]
    os.makedirs(out, exist_ok=True)
    name = os.path.splitext(os.path.basename(model))[0]
    project = os.path.join(out, name + ".gcode.3mf")
    (slice_native if native() else slice_flat)(out, model, project, machine, process, filament, sets)
    g = os.path.join(out, "plate_1.gcode")
    write_result(out, project)
    head = open(g, errors="replace").read(4000)
    t = re.search(r"total estimated time: ([^\n;]+)", head); n = re.search(r"total layer number: (\d+)", head)
    # the total alone hides a placeholder start: per-layer timelapse lines and the end block still bring hundreds;
    # the start block (before the first layer) holds ~25 in Bambu's real one and none in the placeholder
    m1002 = start = 0
    bed = "?"
    for line in open(g, errors="replace"):
        if line.startswith("; CHANGE_LAYER") and not start:
            start = m1002 or -1
        elif line.startswith("; curr_bed_type = "):     # the config block: head in 2.4, tail in 2.5
            bed = line.split("=", 1)[1].strip()
        m1002 += "M1002" in line
    print(f"{name}: {t.group(1).strip() if t else '?'} | layers {n.group(1) if n else '?'}"
          f" | M1002 x{m1002}, start block x{max(start, 0)} | plate {bed} | {out}")
    if start <= 0:
        print("warning: no M1002 before the first layer — a placeholder start G-code, not the printer's real one")


# --- fix-project ---------------------------------------------------------------------------------------------------

def fix_project(path, out=None, extra=None):
    z = zipfile.ZipFile(path)
    files = {n: z.read(n) for n in z.namelist()}
    z.close()
    cfg = json.loads(files["Metadata/project_settings.config"])
    fils = cfg.get("filament_settings_id") or []
    fils = fils if isinstance(fils, list) else [fils]
    extra = extra or {}

    def keys_for(kind, name):
        try:
            c = chain(orca_roots(), kind, name)
        except SystemExit:
            return set(extra.get(kind, ()))
        m = merged(c)
        ks = user_layer_keys(c) | {k for k in m if k in cfg and k not in META and not k.endswith("_gcode")
                                    and str(one(cfg[k])) != str(one(m[k])) and not isinstance(cfg[k], list)}
        return (ks | set(extra.get(kind, ()))) & set(cfg)

    entries = [";".join(sorted(keys_for("process", cfg.get("print_settings_id", ""))))]
    entries += [";".join(sorted(keys_for("filament", f))) for f in fils]
    entries += [";".join(sorted(keys_for("machine", cfg.get("printer_settings_id", ""))))]
    cfg["different_settings_to_system"] = entries
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4).encode()
    dst = out or path
    tmp = dst + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as w:
        for n, b in files.items():
            w.writestr(n, b)
    os.replace(tmp, dst)
    print("different_settings_to_system:", [len(e.split(";")) if e else 0 for e in entries], "keys ->", dst)


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    cmd = a.pop(0)
    if cmd == "presets":
        presets("--dry-run" in a)
    elif cmd == "slice":
        def opt(n):
            i = a.index(n); v = a[i + 1]; del a[i:i + 2]; return v
        machine, process, filament = opt("--machine"), opt("--process"), opt("--filament")
        sets = []
        while "--set" in a:
            k, _, v = opt("--set").partition("="); sets.append((k, v))
        out, model = a
        slice_(out, model, machine, process, filament, sets)
    elif cmd == "fix-project":
        if native():    # the 2.5 CLI writes the list itself; rebuilding it without Orca's JSON profiles would empty it
            if len(a) > 1:
                shutil.copy(a[0], a[1])
            unstand(a[-1])
            print("Orca 2.5+: the CLI fills different_settings_to_system itself; only stand-in names were put back")
        else:
            fix_project(a[0], a[1] if len(a) > 1 else None)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
