"""Compiled local anatomy correction on the foundation's existing topology."""

from functools import lru_cache
from pathlib import Path
import numpy as np


@lru_cache(maxsize=1)
def _asset():
    with np.load(Path(__file__).parent / "assets" / "axilla_sculpt.npz") as data:
        return int(data["vertex_count"]), data["indices"], data["source_offset"]


@lru_cache(maxsize=1)
def _neck_asset():
    with np.load(Path(__file__).parent / "assets" / "neck_sculpt.npz") as data:
        return int(data["vertex_count"]), data["indices"], data["source_offset"]


def corrected_reference(rest):
    count, indices, offset = _asset()
    if len(rest) != count:
        raise ValueError("The shoulder sculpt does not match this foundation.")
    result = np.array(rest, dtype=np.float32, copy=True)
    result[indices] += offset
    count, indices, offset = _neck_asset()
    if len(rest) != count:
        raise ValueError("The neck sculpt does not match this foundation.")
    result[indices] += offset
    return result
