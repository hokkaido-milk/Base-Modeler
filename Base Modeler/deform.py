"""Continuous source-space deformation shared by EVERY region of the model.

Anatomical ownership is compiled across the source surfaces: coincident border
points receive identical offsets, including nails. Immutable coordinates prevent drift.
Local velocity fields integrate before whole-character height normalization. Regional
size controls use conservative intervals; length fields transport attached parts.
"""

import numpy as np
from .controls import CONTROLS
from functools import lru_cache
from . import native
from .pose import CENTER_X, smooth, arm_weights, compile_arm_fields, independent_arms
from .sculpt import corrected_reference
from .contact import bindings, fit_outer_surfaces

FLOOR = -0.009873936884105206
# Exact anatomical transports applied after the shared flow field.
_TRANSPORTED = ("height", "thigh_length", "leg_length", "arm_length")


def bell(x, center, radius):
    return 1.0 - smooth(0.0, radius, np.abs(x - center))


def _velocity_fields(rest):
    p = np.asarray(rest, dtype=np.float32)
    x, y, z = p[:, 0] - CENTER_X, p[:, 1], p[:, 2]
    ax = np.abs(x)
    side = np.sign(x)
    # The torso ends at the shoulder attachment. Complete arm ownership below
    # the joint prevents chest/waist/pelvis control fields leaking into limbs.
    arm = arm_weights(p)
    body = 1.0 - arm
    pelvis = body * bell(z, 0.99, 0.18)
    legs = body * (1.0 - smooth(0.92, 1.02, z))
    lc = np.interp(z, [0.08, 0.56, 0.97], [0.065, 0.070, 0.088])
    leg_side = side * (1.0 - smooth(0.78, 0.92, z)) + np.tanh(x / 0.055) * smooth(
        0.78, 0.92, z
    )
    lx = x - leg_side * lc
    ly = y - np.interp(z, [0.08, 0.32, 0.56, 0.97], [0.035, 0.035, -0.008, -0.005])
    ac = np.interp(z, [0.98, 1.18, 1.40], [0.27, 0.21, 0.16])
    arx = x - side * ac
    ary = y - 0.005
    front = 1.0 - smooth(-0.09, 0.03, y)
    rear = smooth(-0.055, 0.095, y)
    fields = {}

    def put(name, dx=0.0, dy=0.0, dz=0.0):
        a = np.empty_like(p)
        a[:, 0] = dx
        a[:, 1] = dy
        a[:, 2] = dz
        fields[name] = a

    head = smooth(1.47, 1.565, z)
    put("head_size", x * head, y * head, (z - 1.495) * head)
    shoulder = body * smooth(1.21, 1.40, z) * (1.0 - smooth(1.45, 1.51, z))
    put("shoulder_span", side * 0.16 * arm + x * shoulder)
    put("ribcage_width", x * body * bell(z, 1.32, 0.20))
    waist = body * bell(z, 1.14, 0.17)
    put("waist_size", x * waist, y * waist)
    # Carry leg centers without broadening the space within each foot.
    carry = body * (1.0 - smooth(0.87, 1.04, z)) * smooth(0.015, 0.05, ax)
    put("hip_size", x * pelvis + leg_side * lc * carry * (1.0 - pelvis), y * pelvis)
    put("hip_curve", side * 0.018 * pelvis * smooth(0.07, 0.14, ax), 0.0, 0.0)
    breast = (
        body
        * front
        * bell(z, 1.305, 0.125)
        * bell(ax, 0.070, 0.085)
        * smooth(0.004, 0.028, ax)
    )
    breast_radius = np.sqrt(((ax - 0.070) / 0.075) ** 2 + ((z - 1.305) / 0.095) ** 2)
    breast_volume = (
        body
        * front
        * (1 - smooth(0.55, 1.20, breast_radius))
        * smooth(0.004, 0.028, ax)
    )
    put(
        "breast_size",
        (x - side * 0.07) * breast_volume * 0.36,
        (y + 0.065) * 0.36 * breast_volume,
        (z - 1.305) * breast_volume * 0.30,
    )
    put("breast_gap", side * 0.018 * breast)
    # A negative amount rotates the projecting tip downward about its chest root.
    tilt = -np.deg2rad(12.0)
    put(
        "breast_firmness",
        0.0,
        (0.008 - tilt * (z - 1.325)) * breast,
        (0.015 + tilt * (y + 0.055)) * breast,
    )
    butt = (
        body
        * rear
        * bell(z, 0.965, 0.14)
        * smooth(0.004, 0.035, ax)
        * (1.0 - smooth(0.135, 0.18, ax))
    )
    put(
        "butt_size",
        (x - side * 0.08) * butt * 0.25,
        0.018 * butt,
        (z - 0.965) * butt * 0.12,
    )
    put("butt_gap", side * 0.008 * butt)
    put("butt_firmness", 0.0, 0.005 * butt, 0.014 * butt)
    thigh = legs * bell(z, 0.79, 0.255)
    put("thigh_size", lx * thigh, ly * thigh)
    put("thigh_taper", lx * thigh * (z - 0.69) * 1.4, ly * thigh * (z - 0.69) * 1.4)
    calf = legs * bell(z, 0.34, 0.27)
    ankle = legs * bell(z, 0.11, 0.10)
    put(
        "leg_size", lx * (0.23 * calf + 0.15 * ankle), ly * (0.23 * calf + 0.15 * ankle)
    )
    # Per degree lateral knee displacement; both feet and pelvis stay seated.
    knee = legs * bell(z, 0.56, 0.50)
    put("leg_alignment", side * 0.46 * np.pi / 180.0 * knee)
    foot = body * (1.0 - smooth(0.065, 0.13, z))
    put("foot_size", lx * foot, (y - 0.035) * foot, (z - FLOOR) * foot)
    arm_width = arm * smooth(0.94, 1.005, z)
    put("arm_size", arx * arm_width, ary * arm_width)
    hand = arm * (1.0 - smooth(0.935, 0.995, z))
    put("hand_size", (x - side * 0.27) * hand, (y - 0.005) * hand, (z - 0.98) * hand)
    # Transport the hand rigidly after the wrist; don't lengthen fingers twice.
    wrist_z = np.maximum(z, 0.98)
    wrist_x = np.where(z < 0.98, side * 0.27, x)
    put("arm_length", (wrist_x - side * 0.16) * arm, 0.0, (wrist_z - 1.40) * arm)

    def transport(a, b):
        return np.clip(z - a, 0.0, b - a) * body + (b - a) * arm

    put("thigh_length", dz=transport(0.56, 0.97))
    put("leg_length", dz=transport(0.10, 0.56))
    # Lengthen the torso above the pelvis; the arms follow their shoulders.
    put("torso_leg", dz=np.clip(z - 0.97, 0.0, 0.47) * body + 0.43 * arm)
    limb_dx = lx * legs + arx * arm
    limb_dy = ly * legs + ary * arm
    trunk = body * smooth(0.90, 1.03, z) * (1.0 - smooth(1.43, 1.51, z))
    put("build", x * trunk + limb_dx + side * 0.10 * arm, y * trunk + limb_dy)
    put("fullness", 0.16 * (x * trunk + limb_dx), 0.22 * (y * trunk + limb_dy))
    muscle_l = legs * (0.18 * bell(z, 0.78, 0.22) + 0.20 * bell(z, 0.37, 0.23))
    muscle_a = arm * (0.20 * bell(z, 1.28, 0.16) + 0.16 * bell(z, 1.08, 0.13))
    abs_m = front * body * bell(ax, 0.035, 0.075) * bell(z, 1.17, 0.19)
    back_m = rear * body * bell(z, 1.32, 0.20)
    put(
        "muscle",
        lx * muscle_l + arx * muscle_a,
        ly * muscle_l + ary * muscle_a - 0.006 * abs_m + 0.006 * back_m,
    )
    assert set(fields) == {c.id for c in CONTROLS if c.id != "height"}
    return fields


# A stationary smooth velocity field is integrated as a flow. This prevents
# additive contraction controls from folding the mesh when combined. The grid
# covers the complete source and extreme transported limbs, not its topology.
GRID_MIN = np.array([-0.50, -0.25, -0.25], dtype=np.float32)
GRID_MAX = np.array([0.50, 0.25, 2.25], dtype=np.float32)
GRID_SHAPE = (65, 33, 129)


@lru_cache(maxsize=1)
def _shared_fields():
    axes = [
        np.linspace(a, b, n, dtype=np.float32)
        for a, b, n in zip(GRID_MIN, GRID_MAX, GRID_SHAPE)
    ]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3)
    return {"points": points, "velocities": _velocity_fields(points)}


def compile_fields(rest, *, use_sculpt=True):
    # The velocity grid depends on the supplied foundation, not on each copy.
    reference = corrected_reference(rest) if use_sculpt else rest
    return {
        **_shared_fields(),
        "reference": reference,
        "arm_weights": arm_weights(reference),
        "arms": compile_arm_fields(reference),
        "contacts": bindings() if use_sculpt else None,
    }


def sample(grid, points):
    coords = (points - GRID_MIN) * (
        (np.array(GRID_SHAPE, dtype=np.float32) - 1) / (GRID_MAX - GRID_MIN)
    )
    coords = np.clip(coords, 0, np.array(GRID_SHAPE) - 1.00001)
    i = coords.astype(np.int32)
    t = (coords - i).astype(np.float32)
    nx, ny, nz = GRID_SHAPE
    index = (i[:, 0] * ny + i[:, 1]) * nz + i[:, 2]
    tx, ty, tz = t.T
    # Interpolate along Z first, then Y and X. Identical source points receive
    # identical results, independent of object/material identity.
    a = grid[index] * (1 - tz[:, None]) + grid[index + 1] * tz[:, None]
    b = grid[index + nz] * (1 - tz[:, None]) + grid[index + nz + 1] * tz[:, None]
    c = (
        grid[index + ny * nz] * (1 - tz[:, None])
        + grid[index + ny * nz + 1] * tz[:, None]
    )
    d = (
        grid[index + (ny + 1) * nz] * (1 - tz[:, None])
        + grid[index + (ny + 1) * nz + 1] * tz[:, None]
    )
    low = a * (1 - ty[:, None]) + b * ty[:, None]
    high = c * (1 - ty[:, None]) + d * ty[:, None]
    return low * (1 - tx[:, None]) + high * tx[:, None]


def evaluate(rest, fields, values, *, use_native=True, normalize_height=True):
    p = np.asarray(fields.get("reference", rest), dtype=np.float32)
    velocity = np.zeros_like(fields["points"])
    active = False
    for c in CONTROLS:
        value = float(values[c.id])
        if not np.isfinite(value) or not c.minimum - 1e-6 <= value <= c.maximum + 1e-6:
            raise ValueError("Invalid value for " + c.label)
        value = min(c.maximum, max(c.minimum, value))
        # Limb lengths are exact anatomical transports, applied after the
        # shared flow. Sampling arm length on a moving grid leaks into hips.
        if c.id not in _TRANSPORTED:
            amount = value - c.default
            if amount:
                velocity += fields["velocities"][c.id] * amount
                active = True
    if active and use_native and native.LIBRARY is not None:
        q = native.integrate(velocity, fields["points"], p, GRID_SHAPE)
    elif active:
        # Scaling and squaring approximates exp(v): compose 32 small, smooth
        # maps instead of adding large offsets directly to source vertices.
        displacement = velocity / 32.0
        for _ in range(5):
            displacement += sample(displacement, fields["points"] + displacement)
        q = p + sample(displacement, p)
    else:
        q = p.copy()
    # Fixed source ownership keeps the chest a rigid passenger of leg edits,
    # including when other shape fields are active.
    body = 1.0 - fields["arm_weights"]
    z = p[:, 2]
    q[:, 2] += (np.clip(z - 0.56, 0.0, 0.41) * body + 0.41 * fields["arm_weights"]) * (
        values["thigh_length"] - 1.0
    )
    q[:, 2] += (np.clip(z - 0.10, 0.0, 0.46) * body + 0.46 * fields["arm_weights"]) * (
        values["leg_length"] - 1.0
    )
    q = independent_arms(p, q, fields["arms"], values)
    q = fit_outer_surfaces(q, fields.get("contacts"))
    if not normalize_height:
        if not np.isfinite(q).all():
            raise ValueError("Non-finite mesh coordinates")
        return q
    return apply_height(q, values["height"])


def apply_height(points, height):
    q = points.copy()
    lo = float(q[:, 2].min())
    span = float(q[:, 2].max()) - lo
    scale = height / (100.0 * span)
    q[:, 0] = CENTER_X + (q[:, 0] - CENTER_X) * scale
    q[:, 1] *= scale
    q[:, 2] = FLOOR + (q[:, 2] - lo) * scale
    if not np.isfinite(q).all():
        raise ValueError("Non-finite mesh coordinates")
    return q
