import bpy
import sys
import json
import time
import numpy as np
from pathlib import Path
import base_modeler as bm
from base_modeler.controls import CONTROLS, defaults


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

OUT = R / "artifacts/validation"
OUT.mkdir(exist_ok=True)
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.active_object
data = bm.cache_for(root)
rest = data["rest"]
neutral = bm.evaluate(rest, data["fields"], defaults())
assert len(data["slices"]) == 29 and len(rest) == 271342
assert all(not o.modifiers and not o.data.shape_keys for o, _, _ in data["slices"])


def read():
    arr = []
    for ob, start, end in data["slices"]:
        a = np.empty((end - start) * 3, np.float32)
        ob.data.vertices.foreach_get("co", a)
        arr.append(a.reshape(-1, 3))
    return np.concatenate(arr)


def set_values(values):
    bm._GUARD.add(root.as_pointer())
    try:
        for c in CONTROLS:
            setattr(root.base_modeler, c.id, values[c.id])
    finally:
        bm._GUARD.discard(root.as_pointer())
    bm.update_model(root.base_modeler, bpy.context)
    assert root.as_pointer() not in bm._ERRORS, bm._ERRORS
    return read()


# Triangles, region border duplicate coordinates, and source area baseline.
tri = []
for ob, start, end in data["slices"]:
    ob.data.calc_loop_triangles()
    t = np.empty(len(ob.data.loop_triangles) * 3, np.int32)
    ob.data.loop_triangles.foreach_get("vertices", t)
    tri.append(t.reshape(-1, 3) + start)
tri = np.concatenate(tri)


def normals(a):
    t = a[tri]
    return np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])


n0 = normals(neutral)
area0 = np.linalg.norm(n0, axis=1)
# Ignore source sliver triangles below 1e-9 square meters, whose area is below
# stable precision after rotating float32 vertex coordinates.
valid = area0 > 1e-9
# Exact duplicate positions must stay exactly identical under every control.
_, inv = np.unique(rest, axis=0, return_inverse=True)
order = np.argsort(inv)
a, b = order[:-1], order[1:]
dup = inv[a] == inv[b]
a, b = a[dup], b[dup]
checks = []
times = []


def audit(label, q, values):
    assert np.isfinite(q).all()
    span = (q[:, 2].max() - q[:, 2].min()) * 100
    assert abs(span - values["height"]) < 0.0001, (label, span)
    assert np.max(np.abs(q[a] - q[b])) == 0, (label, "border split")
    n = normals(q)
    area = np.linalg.norm(n, axis=1)
    flipped = int(np.sum((np.einsum("ij,ij->i", n, n0) < 0) & valid))
    collapsed = int(np.sum((area < area0 * 0.01) & valid))
    changed = int(np.sum(np.linalg.norm(q - neutral, axis=1) > 1e-6))
    checks.append(
        {
            "case": label,
            "changed_vertices": changed,
            "normals_rotated_over_90_degrees": flipped,
            "collapsed_triangles": collapsed,
            "min_area_ratio": float(np.min(area[valid] / area0[valid])),
        }
    )

    assert collapsed == 0, (
        label,
        "collapsed",
        collapsed,
        neutral[tri[(area < area0 * 0.01) & valid]].mean(1).tolist(),
        area0[(area < area0 * 0.01) & valid].tolist(),
    )
    return flipped


base = defaults()
q = set_values(base)
assert np.max(abs(q - neutral)) < 3e-7
for c in CONTROLS:
    for amount in (c.minimum, c.default + (c.maximum - c.default) * 0.173, c.maximum):
        before = time.perf_counter()
        setattr(root.base_modeler, c.id, amount)
        q = read()
        times.append(time.perf_counter() - before)
        assert root.as_pointer() not in bm._ERRORS, bm._ERRORS
        vals = {item.id: getattr(root.base_modeler, item.id) for item in CONTROLS}
        expected = bm.evaluate(rest, data["fields"], vals)
        assert np.max(abs(expected - q)) < 1e-7, (
            c.id,
            amount,
            float(np.max(abs(expected - q))),
        )
        audit(c.id + ":" + str(amount), q, vals)
        assert checks[-1]["changed_vertices"] > 0
        setattr(root.base_modeler, c.id, c.default)
for label, vals in [
    ("all_min", {c.id: c.minimum for c in CONTROLS}),
    ("all_max", {c.id: c.maximum for c in CONTROLS}),
]:
    q = set_values(vals)
    audit(label, q, vals)
for gap in (-1.0, 1.0):
    for ribcage in (0.85, 1.15):
        vals = dict(
            base,
            breast_size=2.5,
            breast_firmness=-1.5,
            breast_gap=gap,
            ribcage_width=ribcage,
        )
        q = set_values(vals)
        audit(
            "breast_max_sag_min_gap_" + str(gap) + "_ribcage_" + str(ribcage), q, vals
        )
rng = np.random.default_rng(17)
for i in range(64):
    vals = {c.id: float(rng.uniform(c.minimum, c.maximum)) for c in CONTROLS}
    q = set_values(vals)
    audit("mixed_" + str(i), q, vals)
# Repeat a value after other edits, then reset. No accumulation/drift.
vals = dict(base, hip_size=1.12, arm_length=1.09, foot_size=0.91, head_size=1.07)
q1 = set_values(vals)
set_values({c.id: c.minimum for c in CONTROLS})
q2 = set_values(vals)
assert np.array_equal(q1, q2)
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
assert np.max(abs(read() - neutral)) < 3e-7
# A separate model owns separate geometry and cannot be changed by these sliders.
assert bpy.ops.base_modeler.create() == {"FINISHED"}
other = bpy.context.active_object
assert not (
    {o.data.as_pointer() for o in bm.meshes_for(root)}
    & {o.data.as_pointer() for o in bm.meshes_for(other)}
)
other.base_modeler.waist_size = 1.1
assert np.max(abs(read() - neutral)) < 3e-7
for ob in [*other.children_recursive, other]:
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.context.view_layer.objects.active = root
root.select_set(True)
# Region reset leaves unrelated sliders intact.
root.base_modeler.head_size = 1.07
root.base_modeler.waist_size = 0.9
assert bpy.ops.base_modeler.reset(group="Waist") == {"FINISHED"}
assert abs(root.base_modeler.head_size - 1.07) < 1e-6
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
# Guard destructive topology edits; original geometry can be recovered for test.
ob = data["slices"][0][0]
saved = list(ob["base_modeler_topology"])
ob["base_modeler_topology"] = [0, 0, 0]
bm.clear_cache()
root.base_modeler.build = 1.02
assert root.as_pointer() in bm._ERRORS
ob["base_modeler_topology"] = saved
root.base_modeler.build = 1.0
assert not bm._ERRORS
# Sample saved as an editable body-only file for user review.
for ob in bpy.context.selected_objects:
    ob.select_set(False)
for ob in bm.meshes_for(root):
    ob.select_set(True)
bpy.context.view_layer.objects.active = bm.meshes_for(root)[0]
scene = bpy.context.scene
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        area.spaces.active.show_region_ui = True
        area.spaces.active.region_3d.view_distance = 2.7
        from mathutils import Quaternion, Vector

        area.spaces.active.region_3d.view_rotation = Quaternion((1, 0, 0), np.pi / 2)
        area.spaces.active.region_3d.view_location = Vector((-0.00455, 0, 0.89))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Editable.blend"))
report = {
    "controls": len(CONTROLS),
    "meshes": 29,
    "vertices": len(rest),
    "exact_border_pairs": len(a),
    "cases": checks,
    "callback_median_ms": float(np.median(times) * 1000),
    "callback_max_ms": float(np.max(times) * 1000),
    "t_pose_neutral_max_error": float(np.max(abs(read() - neutral))),
    "passed": True,
}
(OUT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
print("VALIDATION", json.dumps({k: v for k, v in report.items() if k != "cases"}))
print(
    "NORMAL ROTATIONS",
    [
        (c["case"], c["normals_rotated_over_90_degrees"])
        for c in checks
        if c["normals_rotated_over_90_degrees"]
    ],
)
