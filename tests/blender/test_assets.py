"""Audit every shipped Blender data block and its portable dependencies."""

import bpy
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(os.environ.get("BASE_MODELER_PACKAGE", ROOT / "Base Modeler"))
asset = PACKAGE / "assets/foundation.blend"
metadata = json.loads((PACKAGE / "assets/foundation.json").read_text())
assert hashlib.sha256(asset.read_bytes()).hexdigest() == metadata["asset_sha256"]
bpy.ops.wm.open_mainfile(filepath=str(asset))
roots = [ob for ob in bpy.data.objects if ob.get("base_modeler_model")]
assert len(roots) == 1
root = roots[0]
meshes = [ob for ob in root.children_recursive if ob.type == "MESH"]
assert len(bpy.data.objects) == 30 and len(meshes) == 29
assert sum(len(ob.data.vertices) for ob in meshes) == 271342
assert not bpy.data.cameras and not bpy.data.lights and not bpy.data.armatures
assert not bpy.data.texts and not bpy.data.actions and not bpy.data.node_groups
allowed = {
    "base_modeler_model",
    "base_modeler_shape_schema",
    "base_modeler_topology",
    "base_modeler_tessellation_schema",
    "base_modeler_region",
    "base_modeler_raw_span",
    "base_modeler_evaluated_values",
    "base_modeler_height_limit",
    "base_modeler",
}
assert all(set(ob.keys()) <= allowed for ob in bpy.data.objects)
assert sorted(ob["base_modeler_region"] for ob in meshes) == metadata["regions"]
assert all(
    not ob.vertex_groups and not ob.modifiers and not ob.data.shape_keys
    for ob in meshes
)
assert all(not ob.data.has_custom_normals for ob in meshes)
assert all(material.users > 0 for material in bpy.data.materials)
assert len(bpy.data.images) == 1
assert all(i.packed_file and i.filepath == "//Face_Albedo.png" for i in bpy.data.images)
# Inspect the clean editable environment independently of the library.
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "examples/Base Modeler.blend"))
assert len(bpy.data.objects) == 30 and len(bpy.data.meshes) == 29
assert len(bpy.data.materials) == 31
assert len([image for image in bpy.data.images if image.source == "FILE"]) == 1
assert all(image.source in {"FILE", "VIEWER"} for image in bpy.data.images)
assert not bpy.data.cameras and not bpy.data.lights and not bpy.data.armatures
assert (
    not bpy.data.actions
    and not bpy.data.texts
    and not bpy.data.node_groups
    and not bpy.data.worlds
)
assert len(bpy.data.collections) == 1
assert all(m.users > 0 for m in bpy.data.materials)
assert bpy.context.scene.render.engine == "BLENDER_EEVEE"
assert all(
    space.shading.type == "MATERIAL"
    for screen in bpy.data.screens
    for area in screen.areas
    for space in area.spaces
    if space.type == "VIEW_3D"
)
report = {
    "mesh_objects": 29,
    "vertices": 271342,
    "materials": 31,
    "packed_images": 1,
    "unused_scene_data_removed": True,
    "portable_texture": True,
    "metadata_clean": True,
    "passed": True,
}
(ROOT / "artifacts/validation/assets.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("ASSET VALIDATION", json.dumps(report), flush=True)
