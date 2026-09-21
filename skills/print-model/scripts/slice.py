#!/usr/bin/env python3
"""CLI-slice Bambu Studio projects, several at a time, and summarise each result.

  slice.py <out dir> <project.3mf> [project.3mf ...] [--jobs 3]

Per project <name>.3mf: <out dir>/<name>/{<name>.gcode.3mf, plate_1.gcode, result.json, cli.log}, produced by
  <studio> --slice 0 --export-3mf <name>.gcode.3mf --outputdir <out dir>/<name> --debug 0 <project.3mf>
where <studio> is paths.studio_cli() ($BAMBU_STUDIO_CLI, or the platform default). Then one line per project
from result.json: error_string, warning_message, model print time h:mm, prep time (total minus model), grams —
sliced_plates[0].{main_predication, total_predication, filaments[0].total_used_g, warning_message}; with no
result.json, the tail of cli.log. Lines come out in completion order.

A CLI slice is the truth test for any project edit: a key missing from different_settings_to_system, a wrong
preset name or an object outside the bed shows up here, before Studio is even opened."""
import json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import studio_cli

def hm(sec):
    sec = int(sec); return f"{sec // 3600}:{sec % 3600 // 60:02d}"

def summarise(name, d):
    rp = os.path.join(d, "result.json")
    if not os.path.exists(rp):
        lp = os.path.join(d, "cli.log")
        tail = open(lp, errors="replace").read().splitlines()[-3:] if os.path.exists(lp) else []
        return f"{name}: NO result.json" + "".join("\n    " + l for l in tail)
    r = json.load(open(rp)); p = r["sliced_plates"][0]
    prep = p["total_predication"] - p["main_predication"]
    g = p["filaments"][0]["total_used_g"] if p.get("filaments") else float("nan")
    return f"{name}: {r.get('error_string')} | warn: {p.get('warning_message')!r} | model {hm(p['main_predication'])} + prep {hm(prep)} | g: {g:.1f}"

def slice_one(cli, out, proj):
    name = os.path.splitext(os.path.basename(proj))[0]; d = os.path.join(out, name)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    with open(os.path.join(d, "cli.log"), "w") as log:
        subprocess.run([cli, "--slice", "0", "--export-3mf", name + ".gcode.3mf", "--outputdir", d, "--debug", "0", os.path.abspath(proj)],
                       stdout=log, stderr=subprocess.STDOUT)
    return summarise(name, d)

def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] in ("-h", "--help"):
        cli = studio_cli(required=False)
        sys.exit(__doc__ + f"\n\nstudio cli: {cli or 'NOT FOUND (set BAMBU_STUDIO_CLI)'}")
    jobs = 3
    if "--jobs" in a: i = a.index("--jobs"); jobs = int(a[i + 1]); del a[i:i + 2]
    out, projects = a[0], a[1:]
    missing = [p for p in projects if not os.path.exists(p)]
    if missing: raise SystemExit("no such project: " + ", ".join(missing))
    cli = studio_cli(); os.makedirs(out, exist_ok=True)
    print(f"studio cli: {cli}\n{len(projects)} project(s), {jobs} at a time -> {out}/")
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        for fut in as_completed([ex.submit(slice_one, cli, out, p) for p in projects]): print(fut.result(), flush=True)

if __name__ == "__main__":
    main()
