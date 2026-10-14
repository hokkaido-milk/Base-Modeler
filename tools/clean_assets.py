"""Repack the current foundation and retain only runtime-required asset data.

Run Blender with the foundation opened and load_plugin.py before this script.
"""

import hashlib
import json
import sys
from pathlib import Path
import bpy
import numpy as np
import base_modeler as bm
from base_modeler.identity import region_name

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "Base Modeler"
sys.path.insert(0, str(ROOT / "tools"))
from scene_cleanup import clean_scene  # noqa: E402

bm.register()
root = next(ob for ob in bpy.data.objects if ob.get("base_modeler_model"))
for ob in (root, *bm.meshes_for(root)):
    if ob.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(ob)
clean_scene(root)
bpy.context.view_layer.objects.active = root
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
path = PACKAGE / "assets/foundation.blend"
bpy.data.libraries.write(
    str(path),
    {root, *bm.meshes_for(root)},
    path_remap="NONE",
    fake_user=False,
    compress=True,
)
metadata = {
    "name": "Base Modeler foundation",
    "default_pose": "T",
    "meshes": 29,
    "vertices": sum(len(ob.data.vertices) for ob in bm.meshes_for(root)),
    "regions": [region_name(ob) for ob in bm.meshes_for(root)],
    "asset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
}
(PACKAGE / "assets/foundation.json").write_text(json.dumps(metadata, indent=2) + "\n")
required = {
    "arm_partition.npz": ("rest", "grid"),
    "axilla_sculpt.npz": ("vertex_count", "indices", "source_offset"),
    "neck_sculpt.npz": ("vertex_count", "indices", "source_offset"),
    "surface_contacts.npz": (
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
    ),
}
for name, keys in required.items():
    path = PACKAGE / "assets" / name
    with np.load(path) as data:
        arrays = {key: data[key] for key in keys}
    np.savez_compressed(path, **arrays)
print("Cleaned Base Modeler foundation and runtime data", flush=True)
