"""The breast front remains a broad rounded cap across the size control."""

import json
from pathlib import Path
import bpy
import numpy as np
import base_modeler as bm
from base_modeler.identity import region_name
from base_modeler.sculpt import round_breasts

ROOT = Path(__file__).resolve().parents[2]
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
cache = bm.cache_for(root)
_, start, end = next(s for s in cache["slices"] if region_name(s[0]) == "Body_Surface")
source = cache["rest"][start:end]
x = source[:, 0] - bm.deform.CENTER_X
rows = []
for size, minimum_ratio in ((0, 0.85), (1.25, 0.56), (2.5, 0.43)):
    result = bm.evaluate(
        cache["rest"], cache["fields"], dict(bm.defaults(), breast_size=size)
    )[start:end]
    for side, sign in (("L", 1), ("R", -1)):
        selected = (
            (x * sign > 0.015)
            & (x * sign < 0.14)
            & (source[:, 2] > 1.24)
            & (source[:, 2] < 1.40)
            & (source[:, 1] < -0.095)
        )
        points = result[selected]
        front = float(np.quantile(points[:, 1], 0.005))
        depth = -front - 0.065
        cap = points[points[:, 1] < front + depth * 0.1]
        width = float(np.ptp(cap[:, 0]))
        ratio = width / depth
        assert len(cap) > 20 and ratio > minimum_ratio, (size, side, ratio)
        rows.append(
            {
                "size": size,
                "side": side,
                "front_cap_width_m": width,
                "projection_m": depth,
                "cap_width_to_projection": ratio,
            }
        )
for side in ("L", "R"):
    cases = [row for row in rows if row["side"] == side]
    assert all(
        b["front_cap_width_m"] > a["front_cap_width_m"]
        for a, b in zip(cases, cases[1:])
    )
    assert all(b["projection_m"] > a["projection_m"] for a, b in zip(cases, cases[1:]))
# The reference correction changes the existing breast vertices, leaving
# the head, limbs, waist and back at their original source coordinates.
p = cache["rest"]
rounded = round_breasts(p)
chest = (
    (abs(p[:, 0] - bm.deform.CENTER_X) < 0.16)
    & (p[:, 2] > 1.20)
    & (p[:, 2] < 1.42)
    & (p[:, 1] < -0.065)
)
assert np.array_equal(p[~chest], rounded[~chest])
assert np.count_nonzero(np.linalg.norm(rounded - p, axis=1) > 1e-6) > 100
report = {"cases": rows, "unrelated_regions_unchanged": True, "passed": True}
(ROOT / "artifacts/validation/breast_shape.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("BREAST SHAPE VALIDATION", json.dumps(report), flush=True)
