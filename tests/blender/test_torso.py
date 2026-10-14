import bpy
import sys
import json
import numpy as np
from pathlib import Path
import base_modeler as bm
from base_modeler.pose import CENTER_X, SHOULDER_X, SHOULDER_Z
from base_modeler.controls import defaults


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

bm.register()
bpy.ops.base_modeler.create()
root = bpy.context.active_object
cache = bm.cache_for(root)
rest = cache["rest"]
fields = cache["fields"]
base = defaults()
neutral = bm.evaluate(rest, fields, base)
side = np.sign(rest[:, 0] - CENTER_X)
# Full arm ownership outside the shoulder attachment, including upper/lower
# arms, wrists and hands. Compare exact vectors, not just a silhouette bound.
arm = fields["arm_weights"] == 1.0
assert arm.sum() > 20000
# Upper-arm muscles must rotate as complete volumes, rather than curling
# through a partial shoulder blend. Check their edge lengths against the sculpted reference.
rigid = []
for ob, start, end in cache["slices"]:
    if ob.name not in ("Biceps_brachii", "Triceps_brachii", "Deltoid"):
        continue
    assert np.min(fields["arm_weights"][start:end]) > 0.99999, ob.name
    e = np.empty(len(ob.data.edges) * 2, np.int32)
    ob.data.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2) + start
    reference = fields["reference"]
    a = np.linalg.norm(reference[e[:, 1]] - reference[e[:, 0]], axis=1)
    b = np.linalg.norm(neutral[e[:, 1]] - neutral[e[:, 0]], axis=1)
    valid = a > 1e-5
    error = float(np.max(abs(b[valid] / a[valid] - 1.0)))
    assert error < 0.003, (ob.name, error)
    rigid.append({"mesh": ob.name, "maximum_edge_length_ratio_error": error})
checks = []
for control in (
    "shoulder_span",
    "ribcage_width",
    "waist_size",
    "hip_size",
    "hip_curve",
):
    c = next(c for c in bm.CONTROLS if c.id == control)
    for value in (c.minimum, c.maximum):
        vals = dict(base)
        vals[control] = value
        q = bm.evaluate(rest, fields, vals)
        expected = np.zeros_like(q[arm])
        if control == "shoulder_span":
            expected[:, 0] = side[arm] * SHOULDER_X * (value - 1.0)
        error = float(np.max(abs(q[arm] - neutral[arm] - expected)))
        assert error < 2e-6, (control, value, error)
        checks.append(
            {"control": control, "value": value, "maximum_arm_transport_error_m": error}
        )
# Independence still holds when arm size/length are already customized.
custom = dict(base, arm_size=1.12, arm_length=1.08, hand_size=0.92)
custom_neutral = bm.evaluate(rest, fields, custom)
for value in (0.85, 1.15):
    vals = dict(
        custom,
        shoulder_span=value,
        ribcage_width=value,
        waist_size=value,
        hip_size=value,
    )
    q = bm.evaluate(rest, fields, vals)
    expected = np.zeros_like(q[arm])
    expected[:, 0] = side[arm] * SHOULDER_X * (value - 1.0)
    error = float(np.max(abs(q[arm] - custom_neutral[arm] - expected)))
    assert error < 2e-6, error
    checks.append(
        {
            "control": "combined_on_custom_arms",
            "value": value,
            "maximum_arm_transport_error_m": error,
        }
    )
# Neutral shoulder-to-wrist axes must be horizontal in the resulting T-pose.
wrists = arm & (abs(rest[:, 2] - 0.98) < 0.005)
assert wrists.sum() > 10
wrist_height = float(np.median(neutral[wrists, 2]))
assert abs(wrist_height - SHOULDER_Z) < 0.025, wrist_height
# Track the same front-facing source triangles around each projecting breast tip.
tri = []
for ob, start, end in cache["slices"]:
    if not ob.name.startswith("Body_Surface"):
        continue
    ob.data.calc_loop_triangles()
    a = np.empty(len(ob.data.loop_triangles) * 3, np.int32)
    ob.data.loop_triangles.foreach_get("vertices", a)
    tri = a.reshape(-1, 3) + start
centers = rest[tri].mean(1)
mask = (
    (abs(abs(centers[:, 0] - CENTER_X) - 0.07) < 0.025)
    & (centers[:, 1] < -0.112)
    & (abs(centers[:, 2] - 1.305) < 0.035)
)
selected = tri[mask]
assert len(selected) > 20, len(selected)


def tip_direction(q):
    t = q[selected]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    n = n.sum(0)
    if n[1] > 0:
        n = -n
    return float(np.degrees(np.arctan2(n[2], -n[1])))


sag = bm.evaluate(rest, fields, dict(base, breast_firmness=-1.5))
firm = bm.evaluate(rest, fields, dict(base, breast_firmness=1.0))
angles = {
    "neutral": tip_direction(neutral),
    "sag": tip_direction(sag),
    "firm": tip_direction(firm),
}
print("TIP ANGLES", angles, flush=True)
assert angles["sag"] < angles["neutral"] - 2.0, angles
assert angles["firm"] > angles["neutral"] + 2.0, angles
# The fast path must retain the same corrected geometry as the reference.
for vals in (
    dict(base, breast_size=2.5, breast_firmness=-1.5),
    dict(custom, shoulder_span=1.15, ribcage_width=0.85, hip_size=1.15),
):
    fast = bm.evaluate(rest, fields, vals)
    slow = bm.evaluate(rest, fields, vals, use_native=False)
    assert np.max(abs(fast - slow)) < 2e-6
report = {
    "arm_points_checked": int(arm.sum()),
    "rigid_upper_arms": rigid,
    "cases": checks,
    "wrist_height": wrist_height,
    "breast_tip_pitch_degrees": angles,
    "passed": True,
}
(R / "artifacts/validation/torso_isolation.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("TORSO ISOLATION PASSED", json.dumps(report), flush=True)
