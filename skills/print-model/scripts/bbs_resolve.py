#!/usr/bin/env python3
"""Resolve a Bambu Studio preset with its full `inherits` chain (system + user dirs).

Usage: bbs_resolve.py <filament|process|machine> "<preset name>" [key ...]
Prints the merged JSON (all keys) or only the requested keys.

Presets are read from paths.studio_data_dir(): user presets under user/<id>/<kind>/<name>.json (they hold
only the overrides plus `inherits`), vendor presets under system/BBL/<kind>/[<Vendor>/]<name>.json. The chain
is merged base first, overrides last; `_chain` lists the preset names from leaf to root.

Trap: for Bambu machines the resolved preset does NOT carry the real `*_gcode` blobs. Studio 2.x keeps them
out of the system machine JSON, so the chain ends in the generic fdm_machine_common placeholder (Ender-style:
un-indented `M109 S205`, purge line off the bed). Take machine G-code only from a project Studio itself saved
(bbs_project.py snapshot / retarget)."""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import studio_data_dir

BASE = studio_data_dir()

def load(kind, name):
    # user presets first, then system (vendor presets live in system/BBL/<kind>/<Vendor>/)
    pats = [os.path.join(BASE, "user", "*", kind, name + ".json"),
            os.path.join(BASE, "system", "BBL", kind, name + ".json"),
            os.path.join(BASE, "system", "BBL", kind, "*", name + ".json")]
    for pat in pats:
        hits = glob.glob(pat)
        if hits:
            return json.load(open(hits[0], encoding="utf-8")), hits[0]
    raise SystemExit(f"preset not found: {kind}/{name} (looked under {BASE})")

def resolve(kind, name):
    chain = []
    while name:
        j, p = load(kind, name); chain.append((name, j, p)); name = j.get("inherits")
    merged = {}
    for n, j, p in reversed(chain):       # base first, overrides last
        merged.update(j)
    merged["_chain"] = [n for n, _, _ in chain]
    return merged

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    kind, name, keys = sys.argv[1], sys.argv[2], sys.argv[3:]
    m = resolve(kind, name)
    if keys:
        for k in keys: print(f"{k} = {m.get(k, '<absent>')}")
    else:
        print(json.dumps(m, indent=1, ensure_ascii=False))
