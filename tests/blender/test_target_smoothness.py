"""Dragging target balls moves the body continuously; widgets are solid."""

import json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
import base_modeler as bm
from base_modeler.identity import region_name
from base_modeler.rig import DISPLAY_SCHEMA, upgrade_rig_display
from base_modeler.targets import CHANNELS, SOLVER_SCHEMA
from base_modeler.widgets import TAG as WIDGET

ROOT = Path(__file__).resolve().parents[2]
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
cache = bm.cache_for(root)
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
assert bpy.ops.base_modeler.target_controls() == {"FINISHED"}
skin = next(ob for ob, _, _ in cache["slices"] if region_name(ob) == "Body_Surface")

# Proportional bones; solid widgets for every movable control.
assert rig.data.display_type == "OCTAHEDRAL"
for name in ("root", "core", *("target_" + ch for ch in CHANNELS)):
    shape = rig.pose.bones[name].custom_shape
    assert shape and shape.get(WIDGET) and len(shape.data.polygons) > 100, name


def skin_points():
    ev = skin.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    q = np.empty((len(mesh.vertices), 3), np.float32)
    mesh.vertices.foreach_get("co", q.ravel())
    ev.to_mesh_clear()
    return q


report = {}
# Before tuning, these drags flipped knee/elbow twist: single 5 mm steps
# moved the skin 19-24x (feet) and 5x (hand) as far as a typical step.
for channel, offset, ceiling in (
    ("foot.L", (0, -0.45, 0.35), 5.0),
    ("foot.L", (0, 0.25, 0.25), 6.0),
    ("hand.L", (-0.345, -0.30, -0.07), 4.5),
):
    ball = rig.pose.bones["target_" + channel]
    start = ball.matrix.copy()
    previous, steps = None, []
    for s in np.linspace(0, 1, 100):
        m = start.copy()
        m.translation = start.translation + Vector(offset) * float(s)
        ball.matrix = m
        rig.update_tag()
        bpy.context.view_layer.update()
        q = skin_points()
        if previous is not None:
            steps.append(float(np.linalg.norm(q - previous, axis=1).max()))
        previous = q
    ratio = max(steps) / float(np.median(steps))
    assert ratio < ceiling, (channel, offset, ratio)
    report[f"{channel}{offset}_max_step_ratio"] = ratio
    if channel == "foot.L" and offset[2] == 0.35:
        # The hinged knee now reaches a forward kick instead of missing it.
        miss = (rig.pose.bones[channel].tail - ball.head).length
        assert miss < 0.002, miss
    ball.matrix = start
    rig.update_tag()
    bpy.context.view_layer.update()

# Rigs saved before these changes are upgraded on load.
del rig["base_modeler_display_schema"]
del rig["base_modeler_target_solver"]
rig.data.display_type = "BBONE"
for side in "LR":
    rig.pose.bones["shin." + side].lock_ik_y = False
    rig.pose.bones["hand." + side].constraints["Target limb IK"].orient_weight = 1.0
upgrade_rig_display(rig)
assert rig.data.display_type == "OCTAHEDRAL"
assert rig["base_modeler_display_schema"] == DISPLAY_SCHEMA
assert rig["base_modeler_target_solver"] == SOLVER_SCHEMA
assert rig.pose.bones["shin.L"].lock_ik_y
assert rig.pose.bones["hand.R"].constraints["Target limb IK"].orient_weight < 0.2
assert sum(bool(ob.get(WIDGET)) for ob in bpy.data.objects) == 3, "Duplicated widgets"
report["passed"] = True
(ROOT / "artifacts/validation/target_smoothness.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("TARGET SMOOTHNESS", json.dumps(report), flush=True)
