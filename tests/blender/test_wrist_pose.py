"""Wrist bends keep the palm/nails attached without collapsing the wrist band."""

import bpy
import json
import numpy as np
from pathlib import Path
import base_modeler as bm
from base_modeler.identity import region_name

ROOT = Path(__file__).resolve().parents[2]
bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.object
cache = bm.cache_for(root)
neutral = cache["last_result"].copy()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
skin, start, end = next(
    s for s in cache["slices"] if region_name(s[0]) == "Body_Surface"
)
skin.data.calc_loop_triangles()
triangles = np.array([t.vertices[:] for t in skin.data.loop_triangles]) + start
ax = abs(neutral[:, 0] - bm.deform.CENTER_X)
wrist = (ax > 0.50) & (ax < 0.615) & (neutral[:, 2] > 1.30)
triangles = triangles[wrist[triangles].all(1)]


def areas(q):
    p = q[triangles]
    return np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)


baseline = areas(neutral)
valid = baseline > 2e-9
_, inverse = np.unique(cache["rest"], axis=0, return_inverse=True)
order = np.argsort(inverse)
a, b = order[:-1], order[1:]
mask = inverse[a] == inverse[b]
a, b = a[mask], b[mask]


def evaluated():
    rig.update_tag()
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = np.empty_like(neutral)
    for ob, start, end in cache["slices"]:
        evaluated = ob.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        mesh.vertices.foreach_get("co", result[start:end].ravel())
        evaluated.to_mesh_clear()
    return result


checks = []
for side, sign in (("L", 1), ("R", -1)):
    name = "hand." + side
    owned = []
    for ob, start, end in cache["slices"]:
        group = ob.vertex_groups.get(name)
        if group is None:
            continue
        for vertex in ob.data.vertices:
            i = start + vertex.index
            if (
                ax[i] > 0.585
                and (neutral[i, 0] - bm.deform.CENTER_X) * sign > 0
                and any(
                    g.group == group.index and g.weight > 0.99999 for g in vertex.groups
                )
            ):
                owned.append(i)
    owned = np.array(owned)
    assert len(owned) > 500
    opposite = (neutral[:, 0] - bm.deform.CENTER_X) * sign < -0.5
    bone = rig.pose.bones[name]
    for axis in range(3):
        for angle in (-60, 60):
            bone.matrix_basis.identity()
            bone.rotation_euler[axis] = np.radians(angle)
            q = evaluated()
            transform = np.array(bone.matrix @ bone.bone.matrix_local.inverted())
            expected = neutral[owned] @ transform[:3, :3].T + transform[:3, 3]
            error = float(np.max(abs(q[owned] - expected)))
            assert error < 2e-6, (side, axis, angle, error)
            assert np.max(abs(q[opposite] - neutral[opposite])) < 1e-6
            assert np.max(abs(q[a] - q[b])) < 2e-6
            ratio = areas(q)[valid] / baseline[valid]
            assert ratio.min() > 0.01, (side, axis, angle, float(ratio.min()))
            checks.append(
                {
                    "side": side,
                    "axis": axis,
                    "angle": angle,
                    "rigid_hand_error_m": error,
                    "minimum_wrist_face_area_ratio": float(ratio.min()),
                }
            )
    bone.matrix_basis.identity()
    assert np.max(abs(evaluated() - neutral)) < 1e-6
report = {
    "wrist_pose_cases": len(checks),
    "cases": checks,
    "seams_preserved": True,
    "reset_no_drift": True,
    "passed": True,
}
(ROOT / "artifacts/validation/wrist_pose.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("WRIST POSE VALIDATION", json.dumps(report), flush=True)
