#!/usr/bin/env python3
"""Write a Bambu Studio user preset JSON (the on-disk format Studio itself uses: only the overrides
plus `inherits`). Import it in Studio via File > Import > Import Configs; Studio then syncs it to the cloud.

Usage: bbs_preset.py filament|process "<name>" "<inherits>" key=value [key=value ...] [--out dir]
  e.g. bbs_preset.py filament "Brand PLA @BBL A1M" "Generic PLA @BBL A1M" nozzle_temperature=220 filament_flow_ratio=0.98

Default --out: <home>/presets ($PRINT_MODEL_HOME or ~/.print-model) — your store of calibrated presets.
Filament values are stored as one-element lists (Studio's convention); process values as strings.
Do not write into Studio's own user/ preset dir while Studio runs: its cloud sync overwrites files there."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import home

def main():
    a = sys.argv[1:]
    if len(a) < 3 or a[0] not in ("filament", "process"): sys.exit(__doc__)
    kind, name, base = a[0], a[1], a[2]
    out = a[a.index("--out") + 1] if "--out" in a else os.path.join(home(), "presets")
    sets = [x for x in a[3:] if "=" in x]
    j = {"from": "User", "inherits": base, "name": name, "version": "2.8.0.6"}
    if kind == "filament":
        j["filament_settings_id"] = [name]; j["filament_extruder_variant"] = ["Direct Drive Standard"]
        for kv in sets: k, v = kv.split("=", 1); j[k] = [v]
        if "nozzle_temperature" in j and "nozzle_temperature_initial_layer" not in j: j["nozzle_temperature_initial_layer"] = j["nozzle_temperature"]
    else:
        j["print_settings_id"] = name; j["print_extruder_id"] = ["1"]; j["print_extruder_variant"] = ["Direct Drive Standard"]
        for kv in sets: k, v = kv.split("=", 1); j[k] = v
    os.makedirs(out, exist_ok=True); p = os.path.join(out, name + ".json")
    json.dump(dict(sorted(j.items())), open(p, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
    print("written:", p); print(json.dumps(j, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
