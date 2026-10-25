"""The saved rig poses without loading Base Modeler or Rigify."""

import bpy
import numpy as np
import json
from pathlib import Path


R = Path(__file__).resolve().parents[2]
assert not hasattr(bpy.types.Object, "base_modeler")
assert not any(
    "rigify" in a or "base_modeler" in a for a in bpy.context.preferences.addons.keys()
)
rig = next(ob for ob in bpy.data.objects if ob.get("base_modeler_simple_rig"))
meshes = [ob for ob in rig.parent.children_recursive if ob.type == "MESH"]


def evaluated():
    rig.update_tag()
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = []
    for ob in meshes:
        ev = ob.evaluated_get(graph)
        m = ev.to_mesh()
        a = np.empty(len(m.vertices) * 3, np.float32)
        m.vertices.foreach_get("co", a)
        result.append(a)
        ev.to_mesh_clear()
    return np.concatenate(result)


before = evaluated()
for name, minimum in (
    ("core", 0.03),
    ("forearm.L", 0.03),
    ("finger_index.02.L", 0.001),
    ("toe_big.01.R", 0.001),
):
    saved = rig.pose.bones[name].rotation_euler.copy()
    rig.pose.bones[name].rotation_euler.x += 0.4
    after = evaluated()
    assert np.max(abs(after - before)) > minimum, name
    rig.pose.bones[name].rotation_euler = saved
    assert np.max(abs(evaluated() - before)) < 1e-6
assert len(meshes) == 29 and len(rig.data.bones) == 83
report = {
    "native_saved_rig_poses": True,
    "native_fingers_and_toes_pose": True,
    "no_base_modeler_or_rigify_required": True,
    "reset_no_drift": True,
    "passed": True,
}
(R / "artifacts/validation/rig/reopen_validation.json").write_text(
    json.dumps(report, indent=2)
)
print("RIG REOPEN VALIDATION", report, flush=True)
