"""Practical muscle strain gates and progressive native forearm twist weights."""

import json
from pathlib import Path
import bpy
import numpy as np
import base_modeler as bm
from base_modeler.identity import region_name

bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.object
cache = bm.cache_for(root)
neutral = cache["last_result"].copy()
bpy.ops.base_modeler.generate_rig()
rig = bm.rig_for(root)
geometry = {}
for ob, a, b in cache["slices"]:
    edges = np.array([e.vertices[:] for e in ob.data.edges]) + a
    ob.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in ob.data.loop_triangles]) + a
    v = neutral[tri]
    area = np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)
    length = np.linalg.norm(neutral[edges[:, 1]] - neutral[edges[:, 0]], axis=1)
    geometry[region_name(ob)] = (edges, tri, area, length)
rows = []
cases = [
    (
        "elbow",
        {"forearm.L": (100, 0, 0)},
        {"Triceps_brachii": 1.50, "Forearm_flexor_group": 1.58},
    ),
    (
        "twist",
        {"forearm.L": (90, 80, 0)},
        {"Triceps_brachii": 1.46, "Forearm_flexor_group": 1.51},
    ),
    (
        "shoulder",
        {"upper_arm.L": (-80, 0, 0), "forearm.L": (70, 0, 0)},
        {"Deltoid": 2.22, "Biceps_brachii": 1.56},
    ),
    (
        "seated",
        {
            "thigh.L": (90, 0, 0),
            "thigh.R": (90, 0, 0),
            "shin.L": (-90, 0, 0),
            "shin.R": (-90, 0, 0),
        },
        {"Gluteus_maximus": 1.80, "Medial_hamstring_group": 2.20},
    ),
]
for label, pose, thresholds in cases:
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    for name, rotation in pose.items():
        rig.pose.bones[name].rotation_euler = np.radians(rotation)
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
    for name, (edges, tri, area, length) in geometry.items():
        v = q[tri]
        current = np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)
        collapsed = int(np.count_nonzero((area > 2e-9) & (current < area * 0.01)))
        assert collapsed == 0, (label, name, collapsed)
        if name not in thresholds:
            continue
        ratios = (
            np.linalg.norm(q[edges[:, 1]] - q[edges[:, 0]], axis=1)[length > 1e-5]
            / length[length > 1e-5]
        )
        p99 = float(np.quantile(ratios, 0.99))
        assert p99 < thresholds[name], (label, name, p99)
        rows.append(
            dict(
                pose=label,
                region=name,
                stretch_p99=p99,
                compression_p01=float(np.quantile(ratios, 0.01)),
            )
        )
# The skin and attached muscle volumes must actually use the twist helper.
for side, sign in (("L", 1), ("R", -1)):
    skin, a, b = next(s for s in cache["slices"] if region_name(s[0]) == "Body_Surface")
    fore = skin.vertex_groups["forearm." + side].index
    helper = skin.vertex_groups["forearm_twist." + side].index
    source = neutral[a:b]
    shares = []
    for v in skin.data.vertices:
        weights = {g.group: g.weight for g in v.groups}
        f, h = weights.get(fore, 0), weights.get(helper, 0)
        if f + h > 0.99 and (source[v.index, 0] - bm.deform.CENTER_X) * sign > 0:
            shares.append((abs(source[v.index, 0] - bm.deform.CENTER_X), h / (f + h)))
    shares = np.array(shares)
    near = shares[(shares[:, 0] > 0.44) & (shares[:, 0] < 0.46), 1]
    far = shares[(shares[:, 0] > 0.52) & (shares[:, 0] < 0.54), 1]
    assert len(near) > 10 and len(far) > 10
    assert np.median(near) > 0.6 and np.median(far) < 0.15, (
        side,
        np.median(near),
        np.median(far),
    )
report = dict(
    cases=rows, zero_collapsed_faces=True, progressive_twist_weights=True, passed=True
)
(
    Path(__file__).resolve().parents[2] / "artifacts/validation/weight_quality.json"
).write_text(json.dumps(report, indent=2) + "\n")
print("WEIGHT QUALITY", json.dumps(report), flush=True)
