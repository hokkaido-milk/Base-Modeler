"""Chin rigidity, connected core motion and practical hip bends."""

import json
from pathlib import Path
import bpy
import numpy as np

# Native constraint matrix round-trips introduce up to ~1.5 micrometres
# of float32 rest-pose error; bound absolute mesh checks to 3 micrometres.
import base_modeler as bm
from base_modeler.identity import region_name

ROOT = Path(__file__).resolve().parents[2]
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
cache = bm.cache_for(root)
neutral = cache["last_result"].copy()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)


def read():
    rig.update_tag()
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = np.empty_like(neutral)
    for ob, a, b in cache["slices"]:
        ev = ob.evaluated_get(graph)
        mesh = ev.to_mesh()
        mesh.vertices.foreach_get("co", result[a:b].ravel())
        ev.to_mesh_clear()
    return result


def reset():
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    read()


_, a, b = next(s for s in cache["slices"] if region_name(s[0]) == "Head")
# The jaw is below the skull pivot, but must retain the same rigid head motion.
face = np.arange(a, b)[(neutral[a:b, 1] < -0.060) & (neutral[a:b, 2] > 1.520)]
assert len(face) > 1000
worst_face_error = 0.0
for axis in range(3):
    for degrees in (-45, 45):
        reset()
        rig.pose.bones["head"].rotation_euler[axis] = np.radians(degrees)
        q = read()
        matrix = np.array(
            rig.pose.bones["head"].matrix
            @ rig.data.bones["head"].matrix_local.inverted()
        )
        expected = neutral[face] @ matrix[:3, :3].T + matrix[:3, 3]
        error = float(np.max(np.linalg.norm(q[face] - expected, axis=1)))
        assert error < 2e-6, (axis, degrees, error)
        worst_face_error = max(worst_face_error, error)
# Local hip response remains partial under root rotation, with no dependency cycle.
for axis in range(3):
    reset()
    rig.pose.bones["root"].rotation_euler = (0.1, -0.2, 0.15)
    read()
    rest = rig.pose.bones["pelvis"].matrix.to_quaternion()
    rig.pose.bones["core"].rotation_euler[axis] = np.radians(20)
    read()
    angle = rest.rotation_difference(
        rig.pose.bones["pelvis"].matrix.to_quaternion()
    ).angle
    assert abs(np.degrees(angle) - 7.0) < 0.01, (axis, angle)
reset()
rig.pose.bones["core"].location = (0.04, 0.02, -0.01)
q = read()
assert np.max(np.ptp(q - neutral, axis=0)) < 2e-6, "Core translation split torso/hips"
# Exercise flexion, extension, abduction and twist independently on each leg.
triangles = []
for ob, a, b in cache["slices"]:
    ob.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in ob.data.loop_triangles]) + a
    triangles.append(tri)
tri = np.concatenate(triangles)
p = neutral[tri]
area0 = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
valid = area0 > 2e-9
rows = []
for side in ("L", "R"):
    for axis, angle in (
        (0, -25),
        (0, 45),
        (0, 90),
        (1, -30),
        (1, 30),
        (2, -35),
        (2, 35),
    ):
        reset()
        rig.pose.bones["thigh." + side].rotation_euler[axis] = np.radians(angle)
        q = read()
        p = q[tri]
        areas = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
        collapsed = int(np.count_nonzero(valid & (areas < area0 * 0.01)))
        if collapsed:
            bad = tri[valid & (areas < area0 * 0.01)]
            for ob, a, b in cache["slices"]:
                owned = (bad[:, 0] >= a) & (bad[:, 0] < b)
                if owned.any():
                    print(
                        "COMPRESSED",
                        side,
                        axis,
                        angle,
                        region_name(ob),
                        bad[owned].tolist(),
                        neutral[bad[owned]].mean(1).tolist(),
                        flush=True,
                    )
        assert collapsed == 0, (side, axis, angle, collapsed)
        if axis == 0 and angle == 90:
            foot = rig.pose.bones["foot." + side]
            assert foot.head.y < -0.4, "X flexion did not lift the leg forward"
        rows.append(
            dict(side=side, axis=axis, degrees=angle, collapsed_faces=collapsed)
        )
reset()
assert np.max(abs(read() - neutral)) < 3e-6
report = dict(
    head_cases=6,
    worst_face_error_m=worst_face_error,
    core_rotation_axes=3,
    core_translation_rigid=True,
    hip_cases=rows,
    passed=True,
)
(ROOT / "artifacts/validation/anatomy_rig.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("ANATOMY RIG VALIDATION", json.dumps(report), flush=True)
