"""Exercise native bone posing, shape fitting, cleanup and saved-file persistence."""

import bpy
import sys
import numpy as np
import time
import json
from pathlib import Path
import base_modeler as bm
from base_modeler.rig import rig_for


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

OUT = R / "artifacts/validation/rig"
OUT.mkdir(exist_ok=True)
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
c = bm.cache_for(root)
original_groups = {ob.name: set(ob.vertex_groups.keys()) for ob, _, _ in c["slices"]}


def evaluated():
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    out = []
    for ob, a, b in c["slices"]:
        eo = ob.evaluated_get(graph)
        mesh = eo.to_mesh()
        q = np.empty((b - a) * 3, np.float32)
        mesh.vertices.foreach_get("co", q)
        out.append(q.reshape(-1, 3))
        eo.to_mesh_clear()
    return np.concatenate(out)


neutral = evaluated()
start = time.perf_counter()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
elapsed = time.perf_counter() - start
rig = rig_for(root)
assert bpy.context.mode == "POSE" and bpy.context.object == rig
assert len(rig.data.bones) == 22 and all(not pb.constraints for pb in rig.pose.bones)
neutral_wrist_x = rig.data.bones["hand.L"].head_local.x
assert np.max(abs(evaluated() - neutral)) < 1e-6
assert not bpy.ops.base_modeler.generate_rig.poll()
for ob, a, b in c["slices"]:
    assert len(ob.modifiers) == 1 and ob.modifiers[0].object == rig
    owned = {g.index for g in ob.vertex_groups if g.name in rig.data.bones}
    totals = np.array(
        [sum(g.weight for g in v.groups if g.group in owned) for v in ob.data.vertices]
    )
    assert np.max(abs(totals - 1)) < 2e-7, (ob.name, np.max(abs(totals - 1)))
# Matching seam vertices must remain coincident when the neck/head move.
rest = c["rest"]
_, inverse = np.unique(rest, axis=0, return_inverse=True)
order = np.argsort(inverse)
a = order[:-1]
b = order[1:]
take = inverse[a] == inverse[b]
a = a[take]
b = b[take]
checks = []


def reset():
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    rig.update_tag()
    bpy.context.view_layer.update()


def pose(name, rotation=None, location=None):
    reset()
    pb = rig.pose.bones[name]
    if rotation is not None:
        pb.rotation_euler = rotation
    if location is not None:
        pb.location = location
    rig.update_tag()
    q = evaluated()
    assert np.isfinite(q).all()
    assert np.max(abs(q[a] - q[b])) < 2e-6, (name, "neck border split")
    return q


for name, rot, minimum in [
    ("forearm.L", (0.9, 0, 0), 0.08),
    ("upper_arm.R", (-0.7, 0, 0), 0.20),
    ("thigh.L", (0.65, 0, 0), 0.20),
    ("shin.R", (1.0, 0, 0), 0.15),
    ("foot.L", (0.45, 0, 0), 0.015),
    ("toe.R", (0.5, 0, 0), 0.008),
    ("head", (0, 0.4, 0), 0.02),
    ("chest", (0.3, 0, 0), 0.08),
]:
    q = pose(name, rotation=rot)
    distance = np.linalg.norm(q - neutral, axis=1)
    assert distance.max() > minimum, (name, distance.max())
    if name in ("forearm.L", "upper_arm.R", "thigh.L", "shin.R"):
        opposite = (neutral[:, 0] - bm.deform.CENTER_X) * (
            -1 if name.endswith(".L") else 1
        ) > 0.06
        assert distance[opposite].max() < 1e-5, (name, "opposite limb moved")
    checks.append({"bone": name, "maximum_displacement_m": float(distance.max())})
q = pose("root", location=(0.1, 0.05, 0.03))
movement = np.array(rig.pose.bones["root"].head - rig.data.bones["root"].head_local)
assert np.max(abs(q - neutral - movement)) < 1e-6
q = pose("hand.L", location=(0, 0.035, 0))
assert np.max(abs(q - neutral)) > 0.02
reset()
assert np.max(abs(evaluated() - neutral)) < 1e-6
rig.pose.bones["upper_arm.L"].rotation_euler.x = -0.65
rig.pose.bones["forearm.L"].rotation_euler.x = -0.70
rig.pose.bones["upper_arm.R"].rotation_euler.x = -0.50
rig.pose.bones["thigh.L"].rotation_euler.x = 0.25
posed = evaluated()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Posed_Rig.blend"))
# Removing an armature returns the exact modeled shape and restores sliders.
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
assert rig_for(root) is None and np.max(abs(evaluated() - neutral)) < 1e-6
assert all(
    not ob.modifiers and set(ob.vertex_groups.keys()) == original_groups[ob.name]
    for ob, _, _ in c["slices"]
)
root.base_modeler.height = 195
root.base_modeler.arm_length = 1.12
root.base_modeler.head_size = 1.1
root.base_modeler.hip_size = 1.12
assert not bm._ERRORS
custom = evaluated()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = rig_for(root)
assert np.max(abs(evaluated() - custom)) < 1e-6
assert rig.data.bones["head"].tail_local.z > 1.8
assert rig.data.bones["hand.L"].head_local.x > neutral_wrist_x + 0.05
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
assert np.max(abs(evaluated() - neutral)) < 1e-6
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = rig_for(root)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Native_Rig.blend"))
report = {
    "bones": len(rig.data.bones),
    "weighted_vertices": len(neutral),
    "generation_seconds": elapsed,
    "poses": checks,
    "direct_translation": True,
    "neutral_unchanged": True,
    "shape_fitting": True,
    "removal_restores_sliders": True,
    "neck_seam_closed": True,
    "passed": True,
}
(OUT / "validation.json").write_text(json.dumps(report, indent=2))
print("SIMPLE RIG VALIDATION", report, flush=True)
