"""Compile conservative anatomy corrections without changing source vertex bindings.

Run in Blender with tools/load_plugin.py. Output is applied after the historical
foundation corrections, before controls, arm posing, contacts and rig fitting.
"""

from pathlib import Path
import json
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree
import base_modeler as bm
from base_modeler import deform, sculpt
from base_modeler.identity import region_name
from base_modeler.pose import CENTER_X, smooth

ROOT = Path(__file__).resolve().parents[1]
# Never bake this pass into itself when rebuilding the asset.
deform.corrected_reference = sculpt.foundation_reference
bm.register()
bpy.ops.base_modeler.create()
cache = bm.cache_for(bpy.context.object)
p = cache["fields"]["reference"]
q = p.copy()
skin, start, end = next(
    s for s in cache["slices"] if region_name(s[0]) == "Body_Surface"
)
skin.data.calc_loop_triangles()
bvh = BVHTree.FromPolygons(
    p[start:end], [t.vertices[:] for t in skin.data.loop_triangles], all_triangles=True
)
report = {}


def components(count, edges):
    neighbors = [[] for _ in range(count)]
    for a, b in edges:
        neighbors[a].append(b)
        neighbors[b].append(a)
    seen = set()
    for i in range(count):
        if i in seen:
            continue
        pending = [i]
        seen.add(i)
        ids = []
        while pending:
            j = pending.pop()
            ids.append(j)
            for k in neighbors[j]:
                if k not in seen:
                    seen.add(k)
                    pending.append(k)
        yield np.array(ids)


# Reduce excessive superficial relief, not the volume of the underlying body.
# Pectoralis/latissimus retain their separately compiled contact clearances.
relief = {
    "Rectus_abdominis": 0.32,
    "External_oblique": 0.22,
    "Deltoid": 0.22,
    "Infraspinatus_region": 0.28,
    "Teres_major_region": 0.22,
    "Trapezius": 0.18,
    "Sternocleidomastoid": 0.15,
    "Biceps_brachii": 0.12,
    "Triceps_brachii": 0.12,
    "Vastus_lateralis": 0.10,
    "Rectus_femoris": 0.12,
    "Tibialis_anterior": 0.16,
}
for ob, a, b in cache["slices"]:
    name = region_name(ob)
    if name not in relief:
        continue
    local = p[a:b].copy()
    edges = np.array([e.vertices[:] for e in ob.data.edges])
    if name == "Rectus_abdominis":
        for ids in components(b - a, edges):
            v = local[ids].copy()
            lo, hi = v.min(0), v.max(0)
            if lo[2] > 1.13:
                # Closer paired bands; shallow narrow tendinous divisions.
                center = (lo + hi) / 2
                v[:, 0] = CENTER_X + (v[:, 0] - CENTER_X) * 0.94
                v[:, 2] = center[2] + (v[:, 2] - center[2]) * 1.12
                local[ids] = v
            else:
                # Taper the suprapubic part; replace the shield's convex
                # midline by a shallow linea-alba furrow, keeping its fascia.
                x = v[:, 0] - CENTER_X
                taper = 0.78 + 0.22 * smooth(1.025, 1.115, v[:, 2])
                v[:, 0] = CENTER_X + x * taper
                groove = np.exp(-((x / 0.009) ** 2)) * smooth(0.99, 1.035, v[:, 2])
                v[:, 1] += 0.002 * groove
                local[ids] = v
    # Retain the original attachment distance under the abdominal tangential
    # edits by transporting the shell with the supporting skin contour.
    if name == "Rectus_abdominis":
        for i in range(len(local)):
            hits = []
            for v in (p[a + i], local[i]):
                co, _, _, _ = bvh.ray_cast(
                    (float(v[0]), -0.3, float(v[2])), (0, 1, 0), 0.6
                )
                hits.append(co)
            if all(h is not None for h in hits):
                local[i, 1] += hits[1].y - hits[0].y
    # A smooth, bounded displacement towards the support softens plate-like
    # relief while retaining closed thickness and the existing muscle borders.
    offset = np.zeros_like(local)
    for i, v in enumerate(local):
        co, normal, _, _ = bvh.find_nearest(v)
        n = np.asarray(normal)
        distance = float((v - np.asarray(co)) @ n)
        amount = relief[name] * max(distance, 0.0)
        offset[i] = -n * min(amount, 0.003)
    src = np.concatenate((edges[:, 0], edges[:, 1]))
    dst = np.concatenate((edges[:, 1], edges[:, 0]))
    degree = np.maximum(np.bincount(src, minlength=len(local)), 1)
    for _ in range(8):
        average = (
            np.stack(
                [
                    np.bincount(src, weights=offset[dst, k], minlength=len(local))
                    for k in range(3)
                ],
                axis=1,
            )
            / degree[:, None]
        )
        offset = 0.5 * (offset + average)
    local += offset
    # Small Taubin fairing removes surface chatter without shrinking the mass.
    # Avoid smoothing the anatomical borders across separate muscle objects.
    for _ in range(4):
        for amount in (0.28, -0.29):
            average = (
                np.stack(
                    [
                        np.bincount(src, weights=local[dst, k], minlength=len(local))
                        for k in range(3)
                    ],
                    axis=1,
                )
                / degree[:, None]
            )
            local += amount * (average - local)
    q[a:b] = local
    report[name] = {
        "vertices": b - a,
        "maximum_offset_mm": float(np.linalg.norm(local - p[a:b], axis=1).max() * 1000),
    }
ids = np.flatnonzero(np.linalg.norm(q - p, axis=1) > 1e-9)
np.savez_compressed(
    ROOT / "Base Modeler/assets/anatomy_sculpt.npz",
    vertex_count=len(p),
    indices=ids.astype(np.int32),
    source_offset=(q - p)[ids].astype(np.float32),
)
out = ROOT / "artifacts/female_review"
out.mkdir(parents=True, exist_ok=True)
(out / "sculpt.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2), flush=True)
