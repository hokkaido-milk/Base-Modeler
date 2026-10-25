"""Limits and distributed twist survive reopening without the add-on."""

import bpy
import numpy as np
from pathlib import Path
import json

assert not hasattr(bpy.types.Object, "base_modeler")
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
for name in ("head", "neck", "forearm.L", "shin.R", "finger_index.02.L"):
    pb = rig.pose.bones[name]
    limit = next(c for c in pb.constraints if c.type == "LIMIT_ROTATION")
    pb.rotation_euler.x = np.radians(170)
    pb.location = (0.2, 0.2, 0.2)
    pb.scale = (2, 2, 2)
    rig.update_tag()
    bpy.context.view_layer.update()
    matrix = rig.convert_space(
        pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL"
    )
    angle = matrix.to_euler(pb.rotation_mode).x
    # Very large angles may clamp to the nearer endpoint across the +/-pi
    # wrap; either endpoint must still be inside the anatomical interval.
    assert limit.min_x - 2e-5 <= angle <= limit.max_x + 2e-5, (name, angle)
    assert matrix.translation.length < 2e-6
    assert np.max(abs(np.array(matrix.to_scale()) - 1)) < 2e-6
    pb.matrix_basis.identity()
rig.pose.bones["forearm.L"].rotation_euler = (np.radians(90), np.radians(80), 0)
rig.update_tag()
bpy.context.view_layer.update()
a, b = rig.pose.bones["forearm.L"], rig.pose.bones["forearm_twist.L"]
assert (a.tail - b.tail).length < 2e-6
angle = a.matrix.to_quaternion().rotation_difference(b.matrix.to_quaternion()).angle
assert abs(np.degrees(angle) - 60) < 0.01
report = dict(
    native_limits_without_addon=True, native_twist_without_addon=True, passed=True
)
(
    Path(__file__).resolve().parents[2] / "artifacts/validation/limits_reopen.json"
).write_text(json.dumps(report, indent=2) + "\n")
print("NATIVE LIMITS REOPEN PASSED", flush=True)
