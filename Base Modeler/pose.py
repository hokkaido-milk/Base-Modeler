"""Anatomical arm ownership and a rig-free T-pose conversion."""

import numpy as np
from pathlib import Path
from functools import lru_cache

CENTER_X = -0.00455
SHOULDER_X = 0.13
SHOULDER_Z = 1.43
WRIST_LENGTH = float(np.hypot(0.27 - SHOULDER_X, SHOULDER_Z - 0.98))
ANGLE = float(np.arctan2(SHOULDER_Z - 0.98, 0.27 - SHOULDER_X))


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _analytic_arm_weights(points):
    x = np.abs(points[:, 0] - CENTER_X)
    z = points[:, 2]
    edge = np.interp(
        z,
        [0.80, 1.0, 1.18, 1.28, 1.34, 1.40, 1.47],
        [0.19, 0.18, 0.135, 0.105, 0.085, 0.080, 0.10],
    )
    width = np.interp(
        z, [1.18, 1.28, 1.34, 1.40, 1.47], [0.022, 0.022, 0.027, 0.040, 0.055]
    )
    front_gate = smooth(-0.065, -0.045, points[:, 1])
    front_gate = 1.0 - smooth(1.18, 1.25, z) * (1.0 - front_gate)
    return (
        front_gate
        * smooth(edge, edge + width, x)
        * (1.0 - smooth(1.43, 1.50, z))
        * smooth(0.77, 0.83, z)
    ).astype(np.float32)


@lru_cache(maxsize=1)
def _partition():
    path = Path(__file__).parent / "assets" / "arm_partition.npz"
    if not path.exists():
        return ()
    with np.load(path) as data:
        arrays = tuple(data[key] for key in ("rest", "grid"))
    # Callers share these cached arrays; never let one of them edit in place.
    for array in arrays:
        array.flags.writeable = False
    return arrays


def arm_weights(points):
    # Closed muscle volumes have explicit ownership; the connected base skin
    # uses a harmonic attachment compiled along its topology.
    for value in _partition():
        if len(value) == len(points):
            return value
    return _analytic_arm_weights(points)


def t_pose(points, weights, *, dx=0.0, dz=0.0):
    """Rotate each complete arm; blend rotation only at the shoulder attachment."""
    result = np.array(points, dtype=np.float32, copy=True)
    side = np.sign(points[:, 0] - CENTER_X)
    px = CENTER_X + side * (SHOULDER_X + dx)
    pz = SHOULDER_Z + dz
    x = points[:, 0] - px
    z = points[:, 2] - pz
    c = np.cos(ANGLE)
    s = np.sin(ANGLE) * side
    # Blend displacement at the attachment. Blending the rotation angle fans
    # the armpit tissue outward into a bulge when the arm turns through 73°.
    result[:, 0] = points[:, 0] + weights * (px + c * x - s * z - points[:, 0])
    result[:, 2] = points[:, 2] + weights * (pz + s * x + c * z - points[:, 2])
    return result


def compile_arm_fields(rest):
    weights = arm_weights(rest)
    indices = np.flatnonzero(weights > 0.0)
    points = rest[indices]
    w = weights[indices]
    side = np.sign(points[:, 0] - CENTER_X)
    z = points[:, 2]
    center = points.copy()
    center[:, 0] = CENTER_X + side * np.interp(
        z, [0.98, 1.18, 1.40], [0.27, 0.21, 0.16]
    )
    center[:, 1] = 0.005
    return {
        "indices": indices,
        "weights": w,
        "side": side,
        "neutral": t_pose(points, w),
        "center_z": t_pose(center, w)[:, 2],
        "width_mask": smooth(0.94, 1.005, z),
        "muscle": 0.20 * (1.0 - smooth(0.0, 0.16, np.abs(z - 1.28)))
        + 0.16 * (1.0 - smooth(0.0, 0.13, np.abs(z - 1.08))),
        "hand_mask": 1.0 - smooth(0.935, 0.995, z),
        "wrist_x": CENTER_X + side * (SHOULDER_X + WRIST_LENGTH),
    }


def independent_arms(rest, body, fields, values):
    """Torso controls transport arms; only arm/global size controls resize them.

    Interior arm points have ownership 1, making torso isolation exact. A short
    shoulder attachment blends into the torso to retain the connected surface.
    Closed arm muscles and nails move with the arm, without a runtime rig.
    """
    indices = fields["indices"]
    weights = fields["weights"]
    side = fields["side"]
    span = SHOULDER_X * (values["shoulder_span"] - 1.0)
    lift = (
        0.46 * (values["leg_length"] - 1.0)
        + 0.41 * (values["thigh_length"] - 1.0)
        + 0.43 * (values["torso_leg"] - 1.0)
    )
    posed = t_pose(body[indices], weights, dx=span, dz=lift)
    arm = fields["neutral"].copy()
    # Cache the rest centerline and masks; callbacks touch only arm vertices.
    thickness = (
        values["arm_size"]
        * values["build"]
        * (1.0 + 0.16 * values["fullness"])
        * (1.0 + fields["muscle"] * values["muscle"])
    )
    radial_scale = 1.0 + (thickness - 1.0) * fields["width_mask"]
    arm[:, 1] = 0.005 + (arm[:, 1] - 0.005) * radial_scale
    arm[:, 2] = fields["center_z"] + (arm[:, 2] - fields["center_z"]) * radial_scale
    hand_scale = 1.0 + (values["hand_size"] - 1.0) * fields["hand_mask"]
    wrist_x = fields["wrist_x"]
    arm[:, 0] = wrist_x + (arm[:, 0] - wrist_x) * hand_scale
    arm[:, 1] = 0.005 + (arm[:, 1] - 0.005) * hand_scale
    arm[:, 2] = SHOULDER_Z + (arm[:, 2] - SHOULDER_Z) * hand_scale
    distance = side * (arm[:, 0] - CENTER_X) - SHOULDER_X
    arm[:, 0] += (
        side
        * np.minimum(np.maximum(distance, 0.0), WRIST_LENGTH)
        * (values["arm_length"] - 1.0)
    )
    arm[:, 0] += side * (span + 0.10 * (values["build"] - 1.0))
    arm[:, 2] += lift
    w = weights[:, None]
    result = body.copy()
    result[indices] = posed * (1.0 - w) + arm * w
    return result
