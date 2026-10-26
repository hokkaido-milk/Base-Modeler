"""Each phalanx bends its own digit, retaining rigid nails and closed seams."""

import json
from pathlib import Path
import bpy
import numpy as np

# Native constraint matrix round-trips introduce up to ~1.5 micrometres
# of float32 rest-pose error; bound absolute mesh checks to 3 micrometres.
import base_modeler as bm
from base_modeler.digits import chains
from base_modeler.identity import region_name

ROOT = Path(__file__).resolve().parents[2]
bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.object
cache = bm.cache_for(root)
neutral = cache["last_result"].copy()
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
assert len(rig.data.bones) == 83
assert rig.data.display_type == "OCTAHEDRAL"
assert len(rig.data.collections) == 6
assert not rig.data.collections["Deformation"].is_visible


def evaluated():
    rig.update_tag()
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = np.empty_like(neutral)
    for ob, a, b in cache["slices"]:
        ev = ob.evaluated_get(graph)
        mesh = ev.to_mesh()
        mesh.vertices.foreach_get("co", result[a:b].ravel())
        ev.to_mesh_clear()
    return result


def reset():
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()


skin, start, end = next(
    s for s in cache["slices"] if region_name(s[0]) == "Body_Surface"
)
skin.data.calc_loop_triangles()
tri = np.array([t.vertices[:] for t in skin.data.loop_triangles]) + start
p = neutral[tri]
baseline = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
valid = baseline > 2e-9
_, inverse = np.unique(cache["rest"], axis=0, return_inverse=True)
order = np.argsort(inverse)
a, b = order[:-1], order[1:]
seam = inverse[a] == inverse[b]
a, b = a[seam], b[seam]
nail_ids = {}
for ob, start, end in cache["slices"]:
    if region_name(ob) not in ("Fingernails", "Toenails"):
        continue
    for vertex in ob.data.vertices:
        assert len(vertex.groups) == 1
        group = vertex.groups[0]
        assert abs(group.weight - 1) < 1e-7
        name = ob.vertex_groups[group.group].name
        nail_ids.setdefault(name, []).append(start + vertex.index)
assert len(nail_ids) == 20 and all(len(ids) == 513 for ids in nail_ids.values())

checks = []
for side in ("L", "R"):
    for kind, digit, _, names in chains(side):
        for i, name in enumerate(names):
            bone = rig.data.bones[name]
            parent = (
                ("hand." if kind == "finger" else "toe.") + side
                if i == 0
                else names[i - 1]
            )
            assert bone.parent.name == parent
            if i:
                assert (bone.head_local - bone.parent.tail_local).length < 1e-7
            reset()
            rig.pose.bones[name].rotation_euler.x = np.radians(55)
            result = evaluated()
            assert np.isfinite(result).all()
            own = np.array(nail_ids[names[-1]])
            assert np.linalg.norm(result[own] - neutral[own], axis=1).max() > 0.0005, (
                name,
                "did not bend",
            )
            for terminal, ids in nail_ids.items():
                if terminal != names[-1]:
                    assert np.max(abs(result[ids] - neutral[ids])) < 3e-6, (
                        name,
                        "neighbour nail moved",
                        terminal,
                    )
            distal = rig.pose.bones[names[-1]]
            transform = np.array(distal.matrix @ distal.bone.matrix_local.inverted())
            expected = neutral[own] @ transform[:3, :3].T + transform[:3, 3]
            assert np.max(abs(result[own] - expected)) < 2e-6, (name, "nail not rigid")
            assert np.max(abs(result[a] - result[b])) < 2e-6, (name, "seam split")
            p = result[tri]
            area = np.linalg.norm(
                np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1
            )
            ratio = area[valid] / baseline[valid]
            compressed_area = float(baseline[valid][ratio < 0.01].sum() * 0.5)
            assert ratio.min() > 0.0001, (name, "degenerate face", float(ratio.min()))
            assert compressed_area < 1e-5, (
                name,
                "widespread crease compression",
                compressed_area,
            )
            checks.append(
                {
                    "bone": name,
                    "minimum_face_area_ratio": float(ratio.min()),
                    "compressed_source_area_m2": compressed_area,
                }
            )
reset()
for side in ("L", "R"):
    for kind, digit, _, names in chains(side):
        angles = (
            (35, 50, 25)
            if kind == "toe"
            else (45, 65, 35) if digit == "thumb" else (65, 85, 45)
        )
        for name, angle in zip(names, angles):
            rig.pose.bones[name].rotation_euler.x = np.radians(angle)
result = evaluated()
p = result[tri]
area = np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)
ratio = area[valid] / baseline[valid]
compressed = valid.copy()
compressed[valid] = ratio < 0.01
# A tight curl necessarily folds the inside crease. Bound its affected area
# and reject degenerate faces instead of treating every compressed crease as
# a failure. Each individual joint has the same area budget above.
compressed_area = float(baseline[compressed].sum() * 0.5)
assert ratio.min() > 0.0001, ("combined curl degenerate face", float(ratio.min()))
assert compressed_area < 1e-5, ("combined curl widespread pinching", compressed_area)
assert np.max(abs(result[a] - result[b])) < 2e-6
reset()
assert np.max(abs(evaluated() - neutral)) < 3e-6
report = {
    "individual_joint_bends": len(checks),
    "checks": checks,
    "rigid_nails": 20,
    "neighbour_digits_isolated": True,
    "combined_curl_minimum_area_ratio": float(ratio.min()),
    "combined_curl_compressed_faces": int(compressed.sum()),
    "combined_curl_compressed_source_area_m2": compressed_area,
    "seams_and_reset": True,
    "passed": True,
}
(ROOT / "artifacts/validation/digits.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("DIGIT VALIDATION", json.dumps(report), flush=True)
