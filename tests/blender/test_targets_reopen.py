"""Target constraints and widgets work without the add-on or Python auto-run."""

import bpy
from mathutils import Vector, Matrix
from math import radians

assert not hasattr(bpy.types.Object, "base_modeler")
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for ch in ("hand.L", "hand.R", "foot.L", "foot.R"):
    ctrl = rig.pose.bones["target_" + ch]
    # Solid widgets are clickable from any angle and survive without the add-on.
    assert ctrl.custom_shape and len(ctrl.custom_shape.data.polygons) > 100
    m = ctrl.matrix @ Matrix.Rotation(radians(3), 4, "X")
    m.translation += Vector((0, -0.01, 0.01))
    ctrl.matrix = m
    rig.update_tag()
    bpy.context.view_layer.update()
    part = rig.pose.bones[ch]
    assert (part.tail - ctrl.head).length < 0.002, ch
    assert part.matrix.to_quaternion().rotation_difference(
        ctrl.matrix.to_quaternion()
    ).angle < radians(1), ch
head = rig.pose.bones["head"]
ctrl = rig.pose.bones["target_head"]
m = ctrl.matrix.copy()
m.translation += Vector((0.01, 0, 0.01))
ctrl.matrix = m
rig.update_tag()
bpy.context.view_layer.update()
assert head.matrix.col[2].xyz.angle(ctrl.head - head.head) < radians(0.2)
assert all(fc.driver.is_valid for fc in rig.animation_data.drivers)
print("NATIVE TARGETS REOPEN PASSED", flush=True)
