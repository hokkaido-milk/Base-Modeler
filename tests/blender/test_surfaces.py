"""Visible muscle-face interiors must remain outside the actual skin mesh."""

import bpy
import sys
import json
import numpy as np
from pathlib import Path
from mathutils.bvhtree import BVHTree
import base_modeler as bm


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.active_object
c = bm.cache_for(root)
skin, ss, se = next(s for s in c["slices"] if s[0].name == "Body_Surface")
skin.data.calc_loop_triangles()
st = [t.vertices[:] for t in skin.data.loop_triangles]
contact = c["fields"]["contacts"]
exposed = np.zeros(len(c["rest"]), bool)
exposed[contact["indices"][contact["clearance"] > 0.0025]] = True
faces = {}
for ob, start, end in c["slices"]:
    if ob.name not in ("Pectoralis_major", "Latissimus_dorsi"):
        continue
    ob.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in ob.data.loop_triangles]) + start
    faces[ob.name] = tri[exposed[tri].all(1)]
    assert len(faces[ob.name]) > 100


def penetration(q, tri):
    bvh = BVHTree.FromPolygons(q[ss:se], st, all_triangles=True)
    centers = q[tri].mean(1)
    depth = []
    for p in centers:
        co, n, _, _ = bvh.find_nearest(p)
        depth.append(float(np.dot(p - np.asarray(co), np.asarray(n))))
    a = np.array(depth)
    return int((a < -0.00005).sum()), float(a.min()), len(a)


base = bm.defaults()
checks = []
cases = [
    ("neutral", {}),
    ("wide", dict(shoulder_span=1.15, ribcage_width=1.15)),
    ("narrow", dict(shoulder_span=0.85, ribcage_width=0.85)),
    ("fuller", dict(build=1.15, fullness=1.0)),
    ("slender", dict(build=0.85, fullness=-1.0)),
    ("defined", dict(muscle=1.0)),
    ("soft", dict(muscle=-1.0)),
]
for label, changes in cases:
    vals = dict(base, **changes)
    q = bm.evaluate(c["rest"], c["fields"], vals)
    for name, tri in faces.items():
        count, minimum, total = penetration(q, tri)
        print(label, name, count, minimum, flush=True)
        assert count == 0, (label, name, count, minimum)
        checks.append(
            {
                "case": label,
                "mesh": name,
                "faces": total,
                "skin_intersections": count,
                "minimum_clearance_m": minimum,
            }
        )
report = {"cases": checks, "passed": True}
(R / "artifacts/validation/surface_layer_validation.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("SURFACE LAYERS PASSED", flush=True)
