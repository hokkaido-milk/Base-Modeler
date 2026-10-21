"""Rig axes must lie inside the actual palms and feet across body proportions."""

import bpy
import json
import numpy as np
from pathlib import Path
from mathutils.bvhtree import BVHTree
import base_modeler as bm
from base_modeler.identity import region_name
from base_modeler.rig import fit_skeleton

ROOT = Path(__file__).resolve().parents[2]
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
cache = bm.cache_for(root)
skin, start, end = next(
    s for s in cache["slices"] if region_name(s[0]) == "Body_Surface"
)
skin.data.calc_loop_triangles()
triangles = np.array([t.vertices[:] for t in skin.data.loop_triangles])
indices = np.concatenate(
    [
        np.arange(a, b)
        for ob, a, b in cache["slices"]
        if region_name(ob) in ("Body_Surface", "Head")
    ]
)
reference = cache["last_result"].copy()


def inside(bvh, point):
    # Some source faces have reversed winding, so nearest-face signed distance
    # is not an inside test. Use ray parity in three non-axis-aligned directions.
    votes = []
    for direction in ((0.071, 1.0, 0.113), (0.137, 0.193, 1.0), (1.0, 0.173, 0.097)):
        direction = np.array(direction)
        direction /= np.linalg.norm(direction)
        origin = np.array(point, dtype=float)
        hits = 0
        for _ in range(64):
            co, _, _, _ = bvh.ray_cast(origin, direction, 5.0)
            if co is None:
                break
            hits += 1
            origin = np.array(co) + direction * 2e-6
        votes.append(hits % 2 == 1)
    return sum(votes) >= 2


cases = [("neutral", {})]
for key in (
    "height",
    "torso_leg",
    "build",
    "fullness",
    "muscle",
    "arm_length",
    "hand_size",
    "arm_size",
    "shoulder_span",
    "leg_length",
    "thigh_length",
    "foot_size",
    "hip_size",
    "leg_alignment",
):
    control = next(c for c in bm.CONTROLS if c.id == key)
    for value in (control.minimum, control.maximum):
        cases.append((key + ":" + str(value), {key: value}))
cases += [
    (
        "small_limbs",
        dict(
            height=120.0,
            arm_length=0.85,
            hand_size=0.9,
            arm_size=0.85,
            foot_size=0.85,
            leg_length=0.85,
            thigh_length=0.85,
        ),
    ),
    (
        "large_limbs",
        dict(
            height=200.0,
            arm_length=1.15,
            hand_size=1.1,
            arm_size=1.15,
            foot_size=1.15,
            leg_length=1.15,
            thigh_length=1.15,
        ),
    ),
]
rows = []
for label, changes in cases:
    values = dict(bm.defaults(), **changes)
    current = bm.evaluate(cache["rest"], cache["fields"], values)
    bones = fit_skeleton(reference, current, indices, triangles)
    lookup = {name: (head, tail) for name, head, tail, _, _ in bones}
    bvh = BVHTree.FromPolygons(current[start:end], triangles, all_triangles=True)
    minimum = float("inf")
    tested = 0
    for side in ("L", "R"):
        for name in ("forearm", "hand", "shin", "foot", "toe") + tuple(
            n.rsplit(".", 1)[0]
            for n in lookup
            if n.startswith(("finger_", "toe_")) and n.endswith(".L")
        ):
            head, tail = lookup[name + "." + side]
            for t in np.linspace(0, 1, 41 if name == "forearm" else 13):
                point = head * (1 - t) + tail * t
                assert inside(bvh, point), (label, name, side, t, point.tolist())
                _, _, _, distance = bvh.find_nearest(point)
                minimum = min(minimum, float(distance))
                tested += 1
        for parent, child in (
            ("upper_arm", "forearm"),
            ("forearm", "hand"),
            ("thigh", "shin"),
            ("shin", "foot"),
            ("foot", "toe"),
        ):
            assert np.array_equal(
                lookup[parent + "." + side][1], lookup[child + "." + side][0]
            )
    if label == "neutral":
        assert abs(lookup["shin.L"][0][2] - 0.56) < 1e-6
        assert abs(lookup["hand.L"][0][0] - bm.deform.CENTER_X - 0.55) < 1e-6
        assert lookup["hand.L"][1][1] < -0.035
    rows.append(
        {
            "case": label,
            "axis_points_inside_skin": tested,
            "minimum_clearance_m": minimum,
        }
    )
report = {"cases": rows, "joint_chains_coincident": True, "passed": True}
(ROOT / "artifacts/validation/joint_fit.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("JOINT FIT VALIDATION", json.dumps(report), flush=True)
