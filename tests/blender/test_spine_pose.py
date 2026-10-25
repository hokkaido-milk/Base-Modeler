"""Lumbar bends preserve gluteal origins and distribute abdominal strain."""

import json
from pathlib import Path
import bpy
import numpy as np

# Native constraint matrix round-trips introduce up to ~1.5 micrometres
# of float32 rest-pose error; bound absolute mesh checks to 3 micrometres.
import base_modeler as bm
from base_modeler.identity import region_name

ROOT = Path(__file__).resolve().parents[2]
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
rows = []
for label, settings in (
    ("neutral", {}),
    ("fuller_hips", dict(hip_size=1.3, butt_size=2.0)),
):
    for name, value in settings.items():
        setattr(root.base_modeler, name, value)
    cache = bm.cache_for(root)
    neutral = cache["last_result"].copy()
    assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
    rig = bm.rig_for(root)
    for angle in (-20, -10, 20, 35):
        rig.pose.bones["spine"].rotation_euler.x = np.radians(angle)
        rig.update_tag()
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for ob, a, b in cache["slices"]:
            name = region_name(ob)
            if name not in (
                "Body_Surface",
                "Rectus_abdominis",
                "External_oblique",
                "Gluteus_maximus",
                "Gluteus_medius",
            ):
                continue
            ev = ob.evaluated_get(graph)
            mesh = ev.to_mesh()
            q = np.empty((b - a, 3), np.float32)
            mesh.vertices.foreach_get("co", q.ravel())
            ev.to_mesh_clear()
            p = neutral[a:b]
            movement = float(np.linalg.norm(q - p, axis=1).max())
            if name.startswith("Gluteus"):
                assert movement < 2e-6, (label, angle, name, movement)
            edges = np.array([e.vertices[:] for e in ob.data.edges])
            if name == "Body_Surface":
                z = p[edges, 2].mean(1)
                edges = edges[(z > 0.97) & (z < 1.22)]
            original = np.linalg.norm(p[edges[:, 1]] - p[edges[:, 0]], axis=1)
            posed = np.linalg.norm(q[edges[:, 1]] - q[edges[:, 0]], axis=1)
            ratio = posed[original > 1e-5] / original[original > 1e-5]
            p99, p01 = map(float, np.quantile(ratio, (0.99, 0.01)))
            if label == "neutral":
                if name == "Rectus_abdominis":
                    assert ratio.max() < 1.67 and p01 > 0.40, (
                        angle,
                        name,
                        ratio.max(),
                        p01,
                    )
                elif name == "External_oblique":
                    assert ratio.max() < 1.38 and p01 > 0.70, (
                        angle,
                        name,
                        ratio.max(),
                        p01,
                    )
                elif name == "Body_Surface":
                    assert p99 < 1.60 and p01 > 0.44, (angle, name, p99, p01)
            rows.append(
                dict(
                    shape=label,
                    angle=angle,
                    region=name,
                    maximum_displacement_m=movement,
                    stretch_p99=p99,
                    compression_p01=p01,
                )
            )
    rig.pose.bones["spine"].matrix_basis.identity()
    rig.update_tag()
    assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
    assert np.max(abs(bm.cache_for(root)["last_result"] - neutral)) < 3e-6
report = {"cases": rows, "reset_no_drift": True, "passed": True}
(ROOT / "artifacts/validation/spine_pose.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("SPINE POSE VALIDATION", json.dumps(report), flush=True)
