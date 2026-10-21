"""The forearm axis and slender displayed shaft remain inside posed skin."""

import json
from pathlib import Path
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree
import base_modeler as bm
from base_modeler.identity import region_name

ROOT = Path(__file__).resolve().parents[2]
bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.object
skin = next(o for o in bm.meshes_for(root) if region_name(o) == "Body_Surface")


def inside(bvh, point):
    votes = 0
    for ray in ((0.071, 1, 0.113), (0.137, 0.193, 1), (1, 0.173, 0.097)):
        direction = np.array(ray)
        direction /= np.linalg.norm(direction)
        origin = np.array(point)
        hits = 0
        for _ in range(64):
            co, _, _, _ = bvh.ray_cast(origin, direction, 5)
            if co is None:
                break
            hits += 1
            origin = np.array(co) + direction * 2e-6
        votes += hits % 2
    return votes >= 2


cache = bm.cache_for(root)
_, start, end = next(s for s in cache["slices"] if s[0] == skin)
reference = cache["last_result"][start:end].copy()

rows = []
for label, settings in (
    ("neutral", {}),
    (
        "thin_short",
        dict(
            height=120,
            arm_size=0.85,
            build=0.85,
            fullness=-1,
            arm_length=0.85,
            hand_size=0.85,
        ),
    ),
    (
        "thin_long",
        dict(height=200, arm_size=0.85, build=0.85, arm_length=1.15, hand_size=0.85),
    ),
):
    bpy.ops.base_modeler.reset()
    for key, value in settings.items():
        setattr(root.base_modeler, key, value)
    assert not bm._ERRORS
    bpy.ops.base_modeler.generate_rig()
    neutral = np.empty((len(skin.data.vertices), 3), np.float32)
    skin.data.vertices.foreach_get("co", neutral.ravel())
    rig = bm.rig_for(root)
    assert rig.data.display_type == "BBONE"
    for side in ("L", "R"):
        for control in ("forearm.", "hand.", "upper_arm."):
            for axis in range(3):
                for angle in (-90, 0, 90):
                    for pb in rig.pose.bones:
                        pb.matrix_basis.identity()
                    rig.pose.bones[control + side].rotation_euler[axis] = np.radians(
                        angle
                    )
                    rig.update_tag()
                    bpy.context.view_layer.update()
                    ev = skin.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    mesh = ev.to_mesh()
                    q = np.empty((len(mesh.vertices), 3), np.float32)
                    mesh.vertices.foreach_get("co", q.ravel())
                    mesh.calc_loop_triangles()
                    tri = np.array([t.vertices[:] for t in mesh.loop_triangles])
                    # Test the arm's own enclosing skin. Other body surfaces can overlap
                    # a lowered arm during a deliberately extreme FK pose, which
                    # makes whole-body odd/even parity ambiguous.
                    arm = (reference[:, 0] - bm.deform.CENTER_X) * (
                        1 if side == "L" else -1
                    ) > 0.32
                    bvh = BVHTree.FromPolygons(
                        q, tri[arm[tri].all(1)], all_triangles=True
                    )
                    pb = rig.pose.bones["forearm." + side]
                    matrix = np.array(pb.matrix)
                    length = pb.bone.length
                    for t in np.linspace(0, 1, 41):
                        center = matrix[:3, 3] + matrix[:3, 1] * length * t
                        assert inside(bvh, center), (
                            label,
                            control,
                            side,
                            axis,
                            angle,
                            t,
                            "axis",
                        )
                    for t in np.linspace(0.05, 0.95, 13):
                        for x in (-pb.bone.bbone_x, pb.bone.bbone_x):
                            for z in (-pb.bone.bbone_z, pb.bone.bbone_z):
                                point = (
                                    matrix[:3, :3] @ np.array((x, length * t, z))
                                    + matrix[:3, 3]
                                )
                                assert inside(bvh, point), (
                                    label,
                                    control,
                                    side,
                                    axis,
                                    angle,
                                    t,
                                    "display",
                                )
                    rows.append(
                        {
                            "shape": label,
                            "side": side,
                            "control": control[:-1],
                            "axis": axis,
                            "angle": angle,
                        }
                    )
                    ev.to_mesh_clear()
    bpy.ops.base_modeler.remove_rig()
report = {
    "posed_cases": len(rows),
    "shape_cases": 3,
    "axis_and_display_inside_skin": True,
    "passed": True,
}
(ROOT / "artifacts/validation/forearm_pose.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("FOREARM VALIDATION", json.dumps(report), flush=True)
