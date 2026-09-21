#!/usr/bin/env python3
"""What Bambu Studio has open right now (its autosave) — or any saved .3mf project.
Prints selected presets, bed type, objects, and every setting that differs from the
base presets (system + user, `inherits` resolved). Nothing is modified.

Usage: bbs_current.py [project.3mf] [--all]
  no path  -> newest live autosave: <temp dir>/bamboo_model/<day>/<time>#<pid>#N/.3mf, where <temp dir> is
              $TMPDIR (macOS: the per-user Darwin temp dir), %TEMP% on Windows, /tmp on Linux. One autosave
              dir per open Studio window; lock.txt holds the pid and only dirs of a running pid count. The
              autosave lives only while the project is open — copy anything you will need later.
  --all    -> dump the full merged project config as JSON instead of the diff

The G-code blobs are expected to differ from the resolved base: the base machine preset only carries the
generic fdm_machine_common placeholder (Studio hides Bambu's G-code), the project's copy is the real one."""
import glob, json, os, re, subprocess, sys, tempfile, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bbs_resolve import resolve

SKIP = {"_chain", "inherits", "name", "from", "version", "is_custom_defined", "instantiation",
        "print_settings_id", "filament_settings_id", "printer_settings_id", "filament_ids",
        "print_compatible_printers", "compatible_printers", "compatible_prints",
        "filament_start_gcode", "filament_end_gcode", "machine_start_gcode", "machine_end_gcode",
        "change_filament_gcode", "layer_change_gcode", "before_layer_change_gcode",
        "time_lapse_gcode", "template_custom_gcode", "machine_pause_gcode", "change_extrusion_role_gcode",
        "printer_notes", "filament_notes", "print_notes", "filament_settings_id", "printer_model", "printer_variant"}
GCODE = {k for k in SKIP if k.endswith("gcode")}

def tmpdir():
    t = os.environ.get("TMPDIR")
    if not t and sys.platform == "darwin":
        try: t = subprocess.run(["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True).stdout.strip()
        except OSError: t = ""
    return t or tempfile.gettempdir()

def _alive(pid):
    if sys.platform == "win32":
        # never os.kill(pid, 0) here: on Windows that is TerminateProcess, it would close Studio
        import ctypes
        k32 = ctypes.windll.kernel32; h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h: return False
        code = ctypes.c_ulong(); ok = k32.GetExitCodeProcess(h, ctypes.byref(code)); k32.CloseHandle(h)
        return bool(ok) and code.value == 259                                    # STILL_ACTIVE
    try: os.kill(pid, 0); return True
    except PermissionError: return True
    except OSError: return False

def newest_autosave():
    # one autosave dir per open Studio window: <day>/<time>#<pid>#<n>/; lock.txt holds the pid
    dirs = glob.glob(os.path.join(tmpdir(), "bamboo_model", "*", "*", ""))
    live = []
    for d in dirs:
        try: pid = int(open(os.path.join(d, "lock.txt")).read().strip())
        except (OSError, ValueError): continue
        if _alive(pid) and os.path.exists(os.path.join(d, ".3mf")): live.append((pid, d))
    if not live: raise SystemExit("no live Bambu Studio autosave found (is Studio running with a project open?)\n"
                                  "Usage: bbs_current.py [project.3mf] [--all]")
    if len(live) > 1: print("note: several Studio windows are open:", ", ".join(f"pid {p} -> {os.path.basename(d.rstrip('/'))}" for p, d in live), "— using the most recent .3mf")
    return max((os.path.join(d, ".3mf") for _, d in live), key=os.path.getmtime)

def norm(v):
    if isinstance(v, list) and len(v) == 1: v = v[0]
    if isinstance(v, (list, dict)): return json.dumps(v, ensure_ascii=False)
    s = str(v).strip().rstrip("%").replace("x", ",")
    try: return ",".join(f"{float(t):g}" for t in s.split(","))   # 1.0 == 1, 100% == 100, 0.7x0.5 == 0.7,0.5
    except ValueError: return str(v)

def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]): sys.exit(__doc__)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else newest_autosave()
    z = zipfile.ZipFile(path)
    proj = json.loads(z.read("Metadata/project_settings.config"))
    if "--all" in sys.argv: print(json.dumps(proj, indent=1, ensure_ascii=False)); return
    fil = proj.get("filament_settings_id", ["?"]); fil = fil[0] if isinstance(fil, list) else fil
    prc, mach = proj.get("print_settings_id", "?"), proj.get("printer_settings_id", "?")
    print(f"project : {path}")
    print(f"machine : {mach}\nprocess : {prc}\nfilament: {fil}   (type {norm(proj.get('filament_type'))})")
    print(f"bed     : {proj.get('curr_bed_type')}")
    # objects and per-object overrides
    if "Metadata/model_settings.config" in z.namelist():
        x = z.read("Metadata/model_settings.config").decode("utf8", "ignore")
        print("objects :")
        for ob in re.findall(r"<object id=\"(\d+)\">(.*?)</object>", x, re.S):
            oid, body = ob
            name = re.search(r'key="name" value="([^"]*)"', body); src = re.search(r'key="source_file" value="([^"]*)"', body)
            faces = re.search(r'face_count="(\d+)"', body)
            std = {"name", "extruder", "matrix", "source_file", "source_object_id", "source_volume_id", "source_offset_x", "source_offset_y", "source_offset_z"}
            over = [(k, v) for k, v in re.findall(r'<metadata key="([^"]+)" value="([^"]*)"', body) if k not in std]
            print(f"  [{oid}] {name.group(1) if name else '?'}  src={src.group(1) if src else '-'}  faces={faces.group(1) if faces else '?'}" + (f"  overrides={over}" if over else ""))
        pl = re.search(r"<plate>(.*?)</plate>", x, re.S)
        if pl:
            pm = dict(re.findall(r'<metadata key="([^"]+)" value="([^"]*)"', pl.group(1)))
            print("plate   :", {k: pm[k] for k in pm if k in ("plater_id", "plater_name", "bed_type", "print_sequence", "filament_map_mode")})
    base = {}
    for kind, name in (("machine", mach), ("process", prc), ("filament", fil)):
        try: base.update(resolve(kind, name))
        except SystemExit as e: print("warn:", e)
    print("\n--- differs from base presets ---")
    n, g = 0, []
    for k in sorted(proj):
        if k not in base or (k in SKIP and k not in GCODE): continue
        if norm(proj[k]) != norm(base[k]):
            if k in GCODE: g.append(k); continue
            n += 1
            print(f"  {k}: {norm(base[k])[:60]}  ->  {norm(proj[k])[:80]}")
    print(f"  ({n} keys)" + (f"; gcode blobs differ from the resolved base — expected: the base only has fdm_machine_common's placeholder (Studio hides Bambu G-code), the project copy is the real one, keep it: {', '.join(g)}" if g else ""))
    only = [k for k in proj if k not in base and k not in SKIP]
    print(f"--- project-only keys ({len(only)}): " + ", ".join(sorted(only)[:40]) + (" ..." if len(only) > 40 else ""))

if __name__ == "__main__":
    main()
