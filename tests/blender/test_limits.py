"""Actual evaluated native constraints, mirrored hinges, and twist distribution."""

from pathlib import Path
import json
import bpy
import numpy as np
import base_modeler as bm
from base_modeler.limits import rotation_limits

bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.object
bpy.ops.base_modeler.generate_rig()
rig = bm.rig_for(root)


def update():
    rig.update_tag()
    bpy.context.view_layer.update()


def reset():
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    update()


def local(pb):
    return rig.convert_space(
        pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL"
    )


def evaluated_skin():
    ob = next(
        o for o in bm.meshes_for(root) if o.get("base_modeler_region") == "Body_Surface"
    )
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    points = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", points)
    ev.to_mesh_clear()
    return points


reset()
initial_skin = evaluated_skin()


cases = 0
for pb in rig.pose.bones:
    if pb.name.startswith("forearm_twist."):
        continue
    bounds = rotation_limits(pb.name)
    if bounds is not None:
        for axis, (low, high) in enumerate(bounds):
            for requested in (low - 20, high + 20):
                reset()
                pb.rotation_euler[axis] = np.radians(requested)
                update()
                actual = np.degrees(local(pb).to_euler(pb.rotation_mode)[axis])
                expected = np.clip(requested, low, high)
                assert abs(actual - expected) < 0.002, (
                    pb.name,
                    axis,
                    requested,
                    actual,
                    expected,
                )
                cases += 1
    reset()
    pb.location = (0.2, -0.3, 0.4)
    pb.scale = (0.2, 3.0, 1.7)
    update()
    matrix = local(pb)
    assert np.max(abs(np.array(matrix.to_scale()) - 1)) < 2e-6, pb.name
    if pb.name not in ("root", "core"):
        assert matrix.translation.length < 2e-6, (pb.name, tuple(matrix.translation))
# Each elbow bends toward the anterior side, not backward or sideways.
for side in ("L", "R"):
    reset()
    fore = rig.pose.bones["forearm." + side]
    fore.rotation_euler.x = np.radians(90)
    update()
    assert fore.tail.y < fore.head.y - 0.1, side
    for twist in (-80, 80):
        fore.rotation_euler.y = np.radians(twist)
        update()
        helper = rig.pose.bones["forearm_twist." + side]
        # A bent forearm's twist must not change its bone axis.
        assert (fore.head - helper.head).length < 2e-6
        assert (fore.tail - helper.tail).length < 2e-6
        difference = (
            fore.matrix.to_quaternion()
            .rotation_difference(helper.matrix.to_quaternion())
            .angle
        )
        assert abs(np.degrees(difference) - abs(twist) * 0.75) < 0.01, (
            side,
            twist,
            difference,
        )
reset()
rig.pose.bones["neck"].rotation_euler.y = np.radians(179)
rig.pose.bones["head"].rotation_euler.y = np.radians(179)
update()
rotation = (
    rig.pose.bones["head"]
    .matrix.to_quaternion()
    .rotation_difference(rig.data.bones["head"].matrix_local.to_quaternion())
    .angle
)
assert np.degrees(rotation) < 81, np.degrees(rotation)
reset()
path = Path(__file__).resolve().parents[2] / "artifacts/validation"
assert (
    np.max(abs(evaluated_skin() - initial_skin)) < 2e-7
), "Constraint reset accumulated drift"
report = dict(
    rotation_endpoint_cases=cases,
    local_translations_locked=True,
    scales_locked=True,
    neck_head_combined_yaw_degrees=float(np.degrees(rotation)),
    forearm_twist_preserves_bend_axis=True,
    passed=True,
)
(path / "limits.json").write_text(json.dumps(report, indent=2) + "\n")
bpy.ops.wm.save_as_mainfile(filepath=str(path / "Limited_Rig.blend"), compress=True)
print("LIMIT VALIDATION", json.dumps(report), flush=True)
