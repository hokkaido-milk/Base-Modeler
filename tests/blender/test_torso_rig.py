"""Rigid thorax, narrow neck, shoulder-girdle deltoids and hip skinning blend."""

import json
from pathlib import Path
import bpy
import numpy as np
import base_modeler as bm
from base_modeler.identity import region_name
from base_modeler.limits import rotation_limits
from base_modeler.rig import LINEAR_GROUP

ROOT = Path(__file__).resolve().parents[2]
# Thigh muscle tips bound wholly to the femur reach y = 0.07-0.085 m here.
TIP_LIMIT = 0.045
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
cache = bm.cache_for(root)
neutral = cache["last_result"].copy()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
slices = {region_name(ob): (ob, a, b) for ob, a, b in cache["slices"]}
x = neutral[:, 0] - bm.deform.CENTER_X
y, z = neutral[:, 1], neutral[:, 2]


def pose(**rotations):
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    for name, degrees in rotations.items():
        rig.pose.bones[name.replace("_L", ".L")].rotation_euler = np.radians(degrees)
    rig.update_tag()
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    q = np.empty_like(neutral)
    for ob, a, b in cache["slices"]:
        ev = ob.evaluated_get(graph)
        mesh = ev.to_mesh()
        mesh.vertices.foreach_get("co", q[a:b].ravel())
        ev.to_mesh_clear()
    assert np.isfinite(q).all()
    return q


def edges(name, mask=None):
    ob, a, b = slices[name]
    e = np.array([edge.vertices[:] for edge in ob.data.edges]) + a
    return e if mask is None else e[mask[e].all(1)]


def ratio(q, e):
    before = np.linalg.norm(neutral[e[:, 1]] - neutral[e[:, 0]], axis=1)
    after = np.linalg.norm(q[e[:, 1]] - q[e[:, 0]], axis=1)
    keep = before > 1e-5
    return after[keep] / before[keep]


report = {}
# Breasts ride rigidly on the thorax through the full chest bend.
radius = np.sqrt(((abs(x) - 0.07) / 0.08) ** 2 + ((z - 1.305) / 0.10) ** 2)
breast = (radius < 0.7) & (y < -0.08)
for angle in (40, -20):
    r = ratio(pose(chest=(angle, 0, 0)), edges("Body_Surface", breast))
    spread = float(np.max(abs(r - 1)))
    assert spread < 0.01, (angle, spread)
    report[f"breast_edge_change_chest_{angle}"] = spread
# A deep forward fold stays finite without crushing the abdominal shells.
q = pose(spine=(60, 0, 0), chest=(40, 0, 0))
for name, floor in (("Rectus_abdominis", 0.12), ("External_oblique", 0.45)):
    low = float(np.quantile(ratio(q, edges(name)), 0.01))
    assert low > floor, (name, low)
    report[f"{name}_p01_forward_fold"] = low
# The neck turns without dragging the deltoids, clavicles or breasts.
q = pose(neck=(0, 45, 0))
moved = np.linalg.norm(q - neutral, axis=1)
for name in ("Deltoid", "Pectoralis_major"):
    _, a, b = slices[name]
    assert moved[a:b].max() < 0.004, (name, moved[a:b].max())
assert moved[(z < 1.38)].max() < 1e-5
report["neck_turn_deltoid_max_m"] = float(moved[slice(*slices["Deltoid"][1:])].max())
# Lowered arms carry their deltoid cap instead of leaving shoulder pads.
_, a, b = slices["Deltoid"]
cap = np.arange(a, b)[(x[a:b] > 0.13) & (z[a:b] > 1.44)]
q = pose(upper_arm_L=(-80, 0, 0))
drop = float(np.median(neutral[cap, 2] - q[cap, 2]))
assert drop > 0.02, drop
assert float(np.quantile(ratio(q, edges("Deltoid")), 0.99)) < 2.0
report["lowered_arm_deltoid_cap_drop_m"] = drop
# Hip flexion: linear skinning removes the dual-quaternion buttock bulge,
# and the thigh muscle tips stay below the gluteal surface.
for ob, a, b in cache["slices"]:
    group = ob.vertex_groups.get(LINEAR_GROUP)
    zone = (z[a:b] > 0.62) & (z[a:b] < 1.18)
    if group is None:
        assert not zone.any() or region_name(ob) in ("Fingernails", "Toenails")
        continue
    assert ob.modifiers[-1].use_multi_modifier
    assert ob.modifiers[-1].vertex_group == LINEAR_GROUP
q = pose(thigh_L=(90, 0, 0))
for name, ceiling in (("Gluteus_maximus", 1.6), ("Medial_hamstring_group", 1.9)):
    high = float(np.quantile(ratio(q, edges(name)), 0.99))
    assert high < ceiling, (name, high)
    report[f"{name}_p99_hip_flexion"] = high
for name in ("Rectus_femoris", "Vastus_lateralis"):
    _, a, b = slices[name]
    tips = np.arange(a, b)[(z[a:b] > 1.0) & (x[a:b] > 0)]
    # Tips above the hip pivot must not swing back onto the buttock.
    back = float(q[tips, 1].max())
    assert back < TIP_LIMIT, (name, back)
    report[f"{name}_tip_max_y_hip_flexion"] = back
# Trunk limits allow a near-90-degree forward bend in the spine alone.
assert rotation_limits("spine")[0][1] + rotation_limits("chest")[0][1] >= 90
pose()
assert np.max(abs(pose() - neutral)) < 3e-6
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
assert all(LINEAR_GROUP not in ob.vertex_groups for ob, _, _ in cache["slices"])
report["passed"] = True
(ROOT / "artifacts/validation/torso_rig.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("TORSO RIG VALIDATION", json.dumps(report), flush=True)
