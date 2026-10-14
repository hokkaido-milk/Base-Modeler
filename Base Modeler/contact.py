"""Cached skin correspondences keep exposed muscle faces above the skin."""

from pathlib import Path
from functools import lru_cache
import numpy as np


@lru_cache(maxsize=1)
def bindings():
    with np.load(Path(__file__).parent / "assets" / "surface_contacts.npz") as d:
        return {
            k: d[k]
            for k in (
                "indices",
                "triangles",
                "barycentric",
                "normal_coefficients",
                "clearance",
                "support",
                "local_indices",
                "neighbors_a",
                "neighbors_b",
                "degree",
            )
        }


def fit_outer_surfaces(points, contact, *, iterations=6):
    if contact is None or not len(contact["indices"]):
        return points
    t = points[contact["triangles"]]
    u = t[:, 1] - t[:, 0]
    v = t[:, 2] - t[:, 0]
    n = np.cross(u, v)
    n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-20)
    c = contact["normal_coefficients"]
    n = u * c[:, 0, None] + v * c[:, 1, None] + n * c[:, 2, None]
    n /= np.maximum(np.linalg.norm(n, axis=1)[:, None], 1e-20)
    anchor = np.einsum("ij,ijk->ik", contact["barycentric"], t)
    ids = contact["indices"]
    signed = np.einsum("ij,ij->i", points[ids] - anchor, n)
    required = contact["clearance"] - signed
    if required.max() <= 2e-7:
        return points
    support = contact["support"]
    local = contact["local_indices"]
    a = contact["neighbors_a"]
    b = contact["neighbors_b"]
    degree = contact["degree"]
    delta = np.zeros((len(support), 3), np.float32)
    delta[local] = n * np.maximum(required, 0.0)[:, None]
    # Spread a contact correction through the muscle's own topology. Raising
    # isolated vertices creates dimples and can pinch a thin closed rim.
    for _ in range(iterations):
        mean = np.stack(
            [
                np.bincount(a, weights=delta[b, k], minlength=len(support))
                for k in range(3)
            ],
            axis=1,
        )
        mean /= degree[:, None]
        delta = (0.5 * (delta + mean)).astype(np.float32)
        remaining = required - np.einsum("ij,ij->i", delta[local], n)
        delta[local] += n * np.maximum(remaining, 0.0)[:, None]
    result = points.copy()
    result[support] += delta
    return result
