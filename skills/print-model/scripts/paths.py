#!/usr/bin/env python3
"""Where things live: Bambu Studio's data dir, its executable, its bundled resources, and this tool's own store.

  studio_data_dir()       presets and BambuStudio.conf. $BAMBU_STUDIO_DATA, else the platform default:
                            macOS    ~/Library/Application Support/BambuStudio
                            Windows  %APPDATA%/BambuStudio
                            Linux    ~/.config/BambuStudio
  studio_cli()            the Bambu Studio executable (it doubles as the CLI slicer). $BAMBU_STUDIO_CLI, else the
                          first that exists of /Applications/BambuStudio.app/Contents/MacOS/BambuStudio,
                          C:/Program Files/Bambu Studio/bambu-studio.exe, `bambu-studio` on PATH.
                          Exits with a message when none is found (studio_cli(required=False) returns None).
  studio_resources_dir()  Studio's bundled resources (calibration meshes under calib/). $BAMBU_STUDIO_RESOURCES,
                          else derived from the executable's location.
  home()                  the user's own store: calibrated filament presets, trusted machine G-code snapshots
                          (machine-gcode/<slug>.json, see bbs_project.py snapshot). $PRINT_MODEL_HOME, else ~/.print-model.

Run without arguments to print what resolves on this machine."""
import os, shutil, sys

_CLI_CANDIDATES = ["/Applications/BambuStudio.app/Contents/MacOS/BambuStudio",
                   "C:/Program Files/Bambu Studio/bambu-studio.exe"]

def studio_data_dir():
    p = os.environ.get("BAMBU_STUDIO_DATA")
    if p: return os.path.expanduser(p)
    if sys.platform == "darwin": return os.path.expanduser("~/Library/Application Support/BambuStudio")
    if sys.platform == "win32": return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "BambuStudio")
    return os.path.expanduser("~/.config/BambuStudio")

def studio_cli(required=True):
    p = os.environ.get("BAMBU_STUDIO_CLI")
    if p:
        if os.path.exists(os.path.expanduser(p)): return os.path.expanduser(p)
        if shutil.which(p): return shutil.which(p)
        raise SystemExit(f"BAMBU_STUDIO_CLI={p}: no such file")
    for c in _CLI_CANDIDATES:
        if os.path.exists(c): return c
    w = shutil.which("bambu-studio")
    if w: return w
    if not required: return None
    raise SystemExit("Bambu Studio executable not found: tried " + ", ".join(_CLI_CANDIDATES) +
                     " and `bambu-studio` on PATH. Set BAMBU_STUDIO_CLI to its path.")

def studio_resources_dir():
    p = os.environ.get("BAMBU_STUDIO_RESOURCES")
    if p: return os.path.expanduser(p)
    cands = []
    cli = studio_cli(required=False)
    if cli:
        d = os.path.dirname(os.path.realpath(cli))
        cands += [os.path.join(d, "..", "Resources"), os.path.join(d, "resources")]   # macOS bundle / Windows, Linux
    cands += ["/usr/share/BambuStudio", "/usr/share/bambu-studio", "/usr/lib/bambu-studio/resources"]
    for c in cands:
        if os.path.isdir(os.path.join(c, "calib")): return os.path.normpath(c)
    raise SystemExit("Bambu Studio resources dir (the one holding calib/) not found: tried " + ", ".join(cands) +
                     ". Set BAMBU_STUDIO_RESOURCES.")

def home():
    return os.path.expanduser(os.environ.get("PRINT_MODEL_HOME") or "~/.print-model")

if __name__ == "__main__":
    if sys.argv[1:] and sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    def mark(p, kind=os.path.isdir): return f"{p}  {'ok' if p and kind(p) else '(missing)'}"
    print("studio_data_dir      :", mark(studio_data_dir()))
    print("studio_cli           :", mark(studio_cli(required=False), os.path.exists))
    try: print("studio_resources_dir :", mark(studio_resources_dir()))
    except SystemExit as e: print("studio_resources_dir : (missing)", e)
    print("home                 :", mark(home()))
