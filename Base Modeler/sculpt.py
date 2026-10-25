"""Compiled local anatomy correction on the foundation's existing topology."""

from functools import lru_cache
from pathlib import Path
import numpy as np
from .pose import CENTER_X, smooth, arm_weights


def round_breasts(points):
    """Broaden the breast dome and soften its projecting apex on the same mesh."""
    x = points[:, 0] - CENTER_X
    side = np.sign(x)
    offset_x = x - side * 0.070
    offset_z = points[:, 2] - 1.309
    radius = np.sqrt((offset_x / 0.060) ** 2 + (offset_z / 0.070) ** 2)
    weight = (
        (1 - arm_weights(points))
        * np.exp(-((radius / 0.85) ** 4))
        * (1 - smooth(0.95, 1.45, radius))
        * (1 - smooth(-0.110, -0.065, points[:, 1]))
        * smooth(0.005, 0.025, abs(x))
    )
    result = points.copy()
    result[:, 0] += 0.16 * offset_x * weight
    result[:, 1] += 0.0035 * weight
    result[:, 2] += 0.10 * offset_z * weight
    return result


def refine_neck_chin(points):
    """Shorten the neck 12 mm and round the chin without moving facial features."""
    result = points.copy()
    x = points[:, 0] - CENTER_X
    y, z = points[:, 1], points[:, 2]
    chin = (
        (1 - smooth(0.025, 0.065, abs(x)))
        * (1 - smooth(1.545, 1.590, z))
        * smooth(1.495, 1.525, z)
        * (1 - smooth(-0.065, -0.035, y))
    )
    result[:, 0] += x * 0.20 * chin
    result[:, 1] += 0.002 * chin
    result[:, 2] += 0.006 * chin
    result[:, 2] -= 0.012 * smooth(1.445, 1.535, z)
    return result


def round_buttocks(points):
    """Relax the rear shell toward a rounded volume with a smooth attachment."""
    result = points.copy()
    x = points[:, 0] - CENTER_X
    ax, side = abs(x), np.sign(x)
    delta = np.column_stack((ax - 0.083, points[:, 1] - 0.025, points[:, 2] - 0.980))
    radii = np.array((0.083, 0.085, 0.110), dtype=np.float32)
    radius = np.linalg.norm(delta / radii, axis=1)
    weight = (
        (1 - arm_weights(points))
        * smooth(0.010, 0.045, points[:, 1])
        * smooth(0.005, 0.030, ax)
        * smooth(0.40, 0.70, radius)
        * (1 - smooth(1.35, 1.80, radius))
        * smooth(0.85, 0.90, points[:, 2])
    )
    offset = delta * ((1 / np.maximum(radius, 0.4) - 1) * 0.70 * weight)[:, None]
    offset[:, 0] *= side
    result += offset
    return result


@lru_cache(maxsize=None)
def _offsets(asset):
    with np.load(Path(__file__).parent / "assets" / asset) as data:
        return int(data["vertex_count"]), data["indices"], data["source_offset"]


def _apply_offsets(result, asset, label):
    """Add a compiled per-vertex sculpt, rejecting a foundation it was not made for."""
    count, indices, offset = _offsets(asset)
    if len(result) != count:
        raise ValueError(f"The {label} sculpt does not match this foundation.")
    result[indices] += offset
    return result


def foundation_reference(rest):
    result = np.array(rest, dtype=np.float32, copy=True)
    _apply_offsets(result, "axilla_sculpt.npz", "shoulder")
    _apply_offsets(result, "neck_sculpt.npz", "neck")
    return refine_neck_chin(round_buttocks(round_breasts(result)))


def corrected_reference(rest):
    return _apply_offsets(foundation_reference(rest), "anatomy_sculpt.npz", "anatomy")
