#!/usr/bin/env python3
"""OrcaSlicer instead of Bambu Studio: presets moved over value for value, CLI slicing, projects the GUI keeps.

  orca.py presets [--dry-run]
      every Bambu Studio user preset -> an Orca user preset in <orca data>/user/default/<kind>/, value for value
  orca.py slice <out dir> <model.3mf|.stl> --machine M --process P --filament F [--set key=value ...]
      CLI slice with the three presets fully resolved: <out dir>/{plate_1.gcode, <model>.gcode.3mf, cli.log};
      the exported project gets its different_settings_to_system filled; prints time, layers and the M1002 count
  orca.py fix-project <project.3mf> [out.3mf]
      fill different_settings_to_system of a CLI-exported Orca project (in place, or into out.3mf)

Why each part exists (Orca 2.4.2 against Studio 02.08.02.61):
- Orca reads presets only at start, and silently skips a user preset without a `version` key.
- Orca's CLI takes the --load-settings files as complete configs: it does not follow `inherits`. It refuses the whole
  config on one out-of-range value — Studio's tree_support_wall_count = -1 ("auto") is outside Orca's 0..2.
- A CLI-exported project carries different_settings_to_system = ['', '', '']; Orca's GUI resets every key not listed
  there to the system preset of inherits_group when it opens the project — the same trap as Studio's. Listed are the
  keys the user presets set on top of the system ones, plus the --set keys.
- Machine G-code: Orca's system machine presets carry the real Bambu start/end blocks (Studio's preset files do not),
  so no snapshot is needed; the M1002 count still confirms it.
- Bridges, overhang walls, presets: references/orca.md."""
import glob, json, os, re, subprocess, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import studio_data_dir, orca_data_dir, orca_cli, orca_profiles_dir

KINDS = ("machine", "process", "filament")
META = {"name", "inherits", "from", "setting_id", "base_id", "filament_id", "version", "instantiation", "description",
        "renamed_from", "type", "print_settings_id", "filament_settings_id", "printer_settings_id", "compatible_printers",
        "compatible_printers_condition", "compatible_prints", "compatible_prints_condition", "upward_compatible_machine",
        "filament_extruder_variant", "print_extruder_id", "print_extruder_variant", "is_custom_defined"}
REPLACE = {("tree_support_wall_count", "-1"): "0"}      # Studio-only values -> the nearest Orca accepts


def one(v):
    return v[0] if isinstance(v, list) and len(v) == 1 else v


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
    o = merged(chain(orca_system_roots(), kind, parent))
    parity = {k: s[k] for k in s if k in o and k not in META and not k.endswith("_gcode") and one(s[k]) != one(o[k])}
    keys = {**parity, **{k: v for k, v in user.items() if k not in META}}
    if kind == "process":
        keys.update(bridges(keys))
    keys = {k: REPLACE.get((k, str(one(v))), v) for k, v in keys.items()}
    keys = {k: v for k, v in keys.items() if not (k == "tree_support_wall_count" and o.get(k) == v)}
    out = {"from": "User", "version": version, "inherits": parent, "name": user["name"],
           {"process": "print_settings_id", "filament": "filament_settings_id", "machine": "printer_settings_id"}[kind]:
               [user["name"]] if kind == "filament" else user["name"]}
    out.update(keys)
    return out, parity


def presets(dry):
    version = json.load(open(f"{orca_profiles_dir()}/BBL.json"))["version"]
    dest = f"{orca_data_dir()}/user/default"
    for d in sorted(glob.glob(f"{studio_data_dir()}/user/*/")):
        for kind in KINDS:
            for f in sorted(glob.glob(f"{glob.escape(d)}{kind}/*.json")):
                user = json.load(open(f))
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


def slice_(out, model, machine, process, filament, sets):
    cli = orca_cli()
    cfg = {"machine": full_config("machine", machine), "process": full_config("process", process),
           "filament": full_config("filament", filament)}
    changed = {k: set(v[1]) for k, v in cfg.items()}
    for key, val in sets:
        kind = next((k for k in ("process", "filament", "machine") if key in cfg[k][0]), "process")
        cur = cfg[kind][0].get(key)
        cfg[kind][0][key] = [val] * len(cur) if isinstance(cur, list) else val
        changed[kind].add(key)
    os.makedirs(out, exist_ok=True)
    paths = {}
    for k, (m, _) in cfg.items():
        paths[k] = os.path.join(out, f"_{k}.json")
        json.dump(m, open(paths[k], "w"), indent=1)
    name = os.path.splitext(os.path.basename(model))[0]
    with open(os.path.join(out, "cli.log"), "w") as log:
        r = subprocess.run([cli, "--slice", "0", "--load-settings", f"{paths['machine']};{paths['process']}",
                            "--load-filaments", paths["filament"], "--outputdir", out,
                            "--export-3mf", name + ".gcode.3mf", os.path.abspath(model)], stdout=log, stderr=subprocess.STDOUT)
    g = os.path.join(out, "plate_1.gcode")
    if r.returncode or not os.path.exists(g):
        tail = open(os.path.join(out, "cli.log"), errors="replace").read().splitlines()[-4:]
        raise SystemExit(f"slice failed (exit {r.returncode}):\n  " + "\n  ".join(tail))
    fix_project(os.path.join(out, name + ".gcode.3mf"), extra=changed)
    head = open(g, errors="replace").read(4000)
    t = re.search(r"total estimated time: ([^\n;]+)", head); n = re.search(r"total layer number: (\d+)", head)
    m1002 = sum(1 for line in open(g, errors="replace") if "M1002" in line)   # as `grep -c M1002`
    print(f"{name}: {t.group(1).strip() if t else '?'} | layers {n.group(1) if n else '?'} | M1002 x{m1002} | {out}")


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
        fix_project(a[0], a[1] if len(a) > 1 else None)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
