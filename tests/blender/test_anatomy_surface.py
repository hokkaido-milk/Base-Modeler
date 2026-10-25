"""Anatomy corrections preserve topology, winding, seams and finite geometry."""

import json
from pathlib import Path
import bpy
import numpy as np
import base_modeler as bm
from base_modeler.sculpt import foundation_reference, corrected_reference
from base_modeler.identity import region_name

bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
cache = bm.cache_for(bpy.context.object)
old = foundation_reference(cache["rest"])
new = corrected_reference(cache["rest"])
assert new.shape == old.shape and np.isfinite(new).all()
assert np.array_equal(new, corrected_reference(cache["rest"])), "Sculpt accumulated"
rows = []
for ob, a, b in cache["slices"]:
    name = region_name(ob)
    ob.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in ob.data.loop_triangles]) + a

    def normals(p):
        v = p[tri]
        return np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])

    n0, n1 = normals(old), normals(new)
    area0, area1 = np.linalg.norm(n0, axis=1), np.linalg.norm(n1, axis=1)
    valid = area0 > 2e-9
    flipped = int(np.count_nonzero(valid & (np.einsum("ij,ij->i", n0, n1) <= 0)))
    collapsed = int(np.count_nonzero(valid & (area1 < 0.05 * area0)))
    displacement = np.linalg.norm(new[a:b] - old[a:b], axis=1)
    assert not flipped and not collapsed, (name, flipped, collapsed)
    assert displacement.max() < 0.015, (name, "excessive sculpt")
    if name in ("Body_Surface", "Head", "Fingernails", "Toenails"):
        assert np.array_equal(old[a:b], new[a:b]), name
    rows.append(
        dict(
            region=name,
            flipped=flipped,
            collapsed=collapsed,
            maximum_offset_mm=float(displacement.max() * 1000),
        )
    )
_, inverse = np.unique(cache["rest"], axis=0, return_inverse=True)
order = np.argsort(inverse)
a, b = order[:-1], order[1:]
same = inverse[a] == inverse[b]
assert np.array_equal(new[a[same]], new[b[same]]), "Shared seams separated"
report = dict(
    regions=rows, vertex_bindings_preserved=True, deterministic=True, passed=True
)
out = Path(__file__).resolve().parents[2] / "artifacts/validation/anatomy_surface.json"
out.write_text(json.dumps(report, indent=2) + "\n")
print("ANATOMY SURFACE VALIDATION", json.dumps(report), flush=True)
