"""Five target handles: neutral install, endpoint goals, switches and cleanup."""

import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix
import base_modeler as bm
from base_modeler.targets import CHANNELS, TAG, set_mode
from base_modeler.widgets import TAG as WIDGET

ROOT = Path(__file__).resolve().parents[2]
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.ops.base_modeler.create()
root = bpy.context.object
cache = bm.cache_for(root)
bpy.ops.base_modeler.generate_rig()
rig = bm.rig_for(root)
neutral = {pb.name: pb.matrix.copy() for pb in rig.pose.bones}
counts = [len(o.data.vertices) for o, _, _ in cache["slices"]]
assert bpy.ops.base_modeler.target_controls() == {"FINISHED"}
assert len(rig.data.bones) == 88 and rig[TAG]
assert bpy.ops.base_modeler.target_controls() == {"FINISHED"}
assert len(rig.data.bones) == 88
assert [len(o.data.vertices) for o, _, _ in cache["slices"]] == counts
for name, m in neutral.items():
    pb = rig.pose.bones[name]
    assert (pb.head - m.translation).length < 0.003, (
        name,
        "install moved joint",
        (pb.head - m.translation).length,
    )
    assert m.to_quaternion().rotation_difference(
        pb.matrix.to_quaternion()
    ).angle < np.radians(0.6), (name, "install rotated joint")
for ch in CHANNELS:
    target = rig.pose.bones["target_" + ch]
    assert not target.bone.use_deform and target.custom_shape is not None
    assert target.bone.parent.name == "root"
    assert target.lock_scale[:] == (True, True, True)

assert rig.pose.bones["upper_arm.L"].hide
assert not rig.pose.bones["target_hand.L"].hide

rows = []
for ch, delta in [
    ("hand.L", (-0.1, -0.15, -0.15)),
    ("hand.R", (0.1, -0.15, -0.15)),
    ("foot.L", (0, -0.12, 0.12)),
    ("foot.R", (0, -0.12, 0.12)),
]:
    ctrl = rig.pose.bones["target_" + ch]
    part = rig.pose.bones[ch]
    m = ctrl.matrix.copy()
    m.translation += Vector(delta)
    ctrl.matrix = m
    rig.update_tag()
    bpy.context.view_layer.update()
    distance = (part.tail - ctrl.head).length
    assert distance < 0.002, (ch, "position", distance)
    # Rotate the ball in its own frame; both position and orientation are goals.
    ctrl.matrix = ctrl.matrix @ Matrix.Rotation(np.radians(10), 4, "X")
    rig.update_tag()
    bpy.context.view_layer.update()
    distance = (part.tail - ctrl.head).length
    angle = (
        part.matrix.to_quaternion()
        .rotation_difference(ctrl.matrix.to_quaternion())
        .angle
    )
    assert distance < 0.002 and angle < np.radians(1), (ch, distance, angle)
    before = part.matrix.copy()
    set_mode(bpy.context, rig, ch, False)
    drift = (part.tail - (before.translation + before.col[1].xyz * part.length)).length
    assert drift < 0.01, (ch, "FK switch", drift)
    set_mode(bpy.context, rig, ch, True)
    assert (part.tail - rig.pose.bones["target_" + ch].head).length < 0.002, ch
    assert bpy.ops.base_modeler.select_target(channel=ch) == {"FINISHED"}
    assert rig.data.bones.active.name == "target_" + ch
    rows.append(
        dict(
            channel=ch,
            position_error_m=distance,
            orientation_error_degrees=float(np.degrees(angle)),
            fk_switch_drift_m=drift,
        )
    )
ctrl = rig.pose.bones["target_head"]
m = ctrl.matrix.copy()
m.translation += Vector((0.08, 0, 0.03))
ctrl.matrix = m
rig.update_tag()
bpy.context.view_layer.update()
head = rig.pose.bones["head"]
direction = (ctrl.head - head.head).normalized()
gaze = head.matrix.col[2].xyz.normalized()
assert gaze.angle(direction) < np.radians(0.2)
# A distant target never stretches the limb bones.
ctrl = rig.pose.bones["target_hand.L"]
saved = ctrl.matrix.copy()
m = ctrl.matrix.copy()
m.translation += Vector((2, 0, 0))
ctrl.matrix = m
rig.update_tag()
bpy.context.view_layer.update()
for name in ("upper_arm.L", "forearm.L", "hand.L"):
    pb = rig.pose.bones[name]
    assert abs((pb.tail - pb.head).length - pb.bone.length) < 2e-6, name
ctrl.matrix = saved
rig.update_tag()
bpy.context.view_layer.update()
# The saved rig is the reopen fixture, with all targets active.
path = ROOT / "artifacts/validation/Target_Rig.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
report = dict(cases=rows, head_tracks=True, no_stretch=True, passed=True)
(ROOT / "artifacts/validation/targets.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
assert bm.rig_for(root) is None
assert not any(ob.get(TAG) or ob.get(WIDGET) for ob in bpy.data.objects), "Orphans"
print("TARGET CONTROLS", json.dumps(report), flush=True)
