"""Regression gates for wrist tessellation and every native pose control."""

import bpy
import sys
import json
import numpy as np
from pathlib import Path
import base_modeler as bm
from base_modeler.topology import repair_tessellation


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

OUT = R / "artifacts/validation/poses"
OUT.mkdir(exist_ok=True)
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
objects = bm.meshes_for(root)
skin = next(o for o in objects if o.name.startswith("Body_Surface"))
assert repair_tessellation(objects) == 0
assert skin["base_modeler_tessellation_schema"] == 1
c = bm.cache_for(root)


def evaluated():
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    out = []
    for ob, a, b in c["slices"]:
        ev = ob.evaluated_get(graph)
        m = ev.to_mesh()
        q = np.empty((b - a) * 3, np.float32)
        m.vertices.foreach_get("co", q)
        out.append(q.reshape(-1, 3))
        ev.to_mesh_clear()
    return np.concatenate(out)


neutral = evaluated()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
assert rig["base_modeler_binding_schema"] == bm.rig.BINDING_SCHEMA
# Catch the original medial leg/foot pinning and thigh muscle attachment bugs.
for ob, a, b in c["slices"]:
    if ob.name.startswith(("Body_Surface", "Vastus_lateralis", "Vastus_medialis")):
        group = ob.vertex_groups.get("pelvis")
        for v in ob.data.vertices:
            if ob != skin or neutral[a + v.index, 2] < 0.7:
                assert (
                    not any(
                        g.group == group.index and g.weight > 1e-7 for g in v.groups
                    )
                    if group
                    else True
                )
_, inverse = np.unique(c["rest"], axis=0, return_inverse=True)
order = np.argsort(inverse)
a, b = order[:-1], order[1:]
take = inverse[a] == inverse[b]
a, b = a[take], b[take]


def reset():
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    rig.update_tag()


checks = []
for pb in rig.pose.bones:
    for axis in range(3):
        for sign in (-1, 1):
            reset()
            pb.rotation_euler[axis] = sign * np.radians(20)
            rig.update_tag()
            q = evaluated()
            assert np.isfinite(q).all(), (pb.name, axis, sign)
            assert np.max(abs(q - neutral)) > 1e-4, (
                pb.name,
                axis,
                sign,
                "control did not move mesh",
            )
            assert np.max(abs(q[a] - q[b])) < 2e-6, (pb.name, "seam split")
            checks.append({"bone": pb.name, "axis": axis, "angle": sign * 20})
    reset()
    pb.location = (0.005, 0.01, 0.005)
    rig.update_tag()
    q = evaluated()
    assert np.isfinite(q).all() and np.max(abs(q - neutral)) > 0.001
    reset()
    assert np.max(abs(evaluated() - neutral)) < 1e-6, (pb.name, "reset drift")
# A practical seated bend must not collapse valid source faces.
for name, amount in [
    ("thigh.L", 90),
    ("thigh.R", 90),
    ("shin.L", -90),
    ("shin.R", -90),
]:
    rig.pose.bones[name].rotation_euler.x = np.radians(amount)
rig.update_tag()
q = evaluated()
collapsed = 0
for ob, start, end in c["slices"]:
    ob.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in ob.data.loop_triangles]) + start
    p0 = neutral[tri]
    p = q[tri]
    ar0 = np.linalg.norm(np.cross(p0[:, 1] - p0[:, 0], p0[:, 2] - p0[:, 0]), axis=1)
    ar = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
    collapsed += int(((ar0 > 2e-9) & (ar < ar0 * 0.01)).sum())
assert collapsed == 0, collapsed
reset()
assert np.max(abs(evaluated() - neutral)) < 1e-6
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
root.base_modeler.waist_size = 0.92
assert not bm._ERRORS
report = {
    "tessellation_prepared": True,
    "idempotent": True,
    "bone_rotation_cases": len(checks),
    "translated_bones": 22,
    "seam_pairs": len(a),
    "seated_collapsed_faces": collapsed,
    "reset_no_drift": True,
    "sliders_after_rig_removal": True,
    "passed": True,
}
(OUT / "regression.json").write_text(json.dumps(report, indent=2) + "\n")
print("AUDIT REGRESSION", report, flush=True)
