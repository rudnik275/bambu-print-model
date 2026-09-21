#!/usr/bin/env -S uv run --quiet --with trimesh --with numpy --with scipy --with shapely --with mapbox_earcut python3
# /// script
# dependencies = ["trimesh", "numpy", "scipy", "shapely", "mapbox_earcut"]
# ///
"""Cut a watertight mesh between two Z planes and cap the openings (what Studio's Cut tool does).

  mesh_cut.py <in.stl> <out.stl> <z_lo> <z_hi>      keep z_lo <= z <= z_hi (mesh coordinates), cap both ends

Used by bbs_calib.py temp: the wizard's temperature_tower.stl is all 35 blocks (350 mm, labels 350 -> 180 °C
from the bed up); a range is cut out of it. Prints the result's z bounds and whether it stayed watertight and
exits non-zero when it did not (do not slice such a mesh). Run it directly (the shebang lets uv fetch trimesh)
or as `uv run mesh_cut.py ...`."""
import sys

def cut(src, dst, z_lo, z_hi):
    import trimesh
    m = trimesh.load(src, force="mesh")
    a = m.slice_plane([0, 0, z_lo], [0, 0, 1], cap=True)
    b = a.slice_plane([0, 0, z_hi], [0, 0, -1], cap=True)
    b.export(dst)
    print("cut: z %.2f..%.2f -> %d faces, watertight=%s, volume %.0f mm3, written %s" % (b.bounds[0][2], b.bounds[1][2], len(b.faces), b.is_watertight, b.volume, dst))
    if not b.is_watertight: raise SystemExit("cut mesh is not watertight — do not slice it")

if __name__ == "__main__":
    if len(sys.argv) < 5 or sys.argv[1] in ("-h", "--help"): sys.exit(__doc__)
    cut(sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
