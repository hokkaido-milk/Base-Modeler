"""Render identical material coordinates at two heights with matched framing."""

import bpy
import sys
import numpy as np
import json
from pathlib import Path
from mathutils import Vector
import base_modeler as bm
from base_modeler.deform import CENTER_X, FLOOR


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.active_object
cache = bm.cache_for(root)
for ob in bm.meshes_for(root):
    assert not ob.data.has_custom_normals, ob.name
for ob in list(bpy.data.objects):
    if ob != root and ob not in root.children_recursive:
        bpy.data.objects.remove(ob, do_unlink=True)
body = next(o for o in bm.meshes_for(root) if o.name.startswith("Body_Surface"))
tree = body.data.materials[0].node_tree
assert any(n.type == "ATTRIBUTE" and n.attribute_name == bm.REST for n in tree.nodes)
assert not any(
    link.from_node.type == "NEW_GEOMETRY" and link.from_socket.name == "Position"
    for link in tree.links
)
# Unlit copies measure color placement independently of shadows and normals.
for mat in {m for ob in bm.meshes_for(root) for m in ob.data.materials if m}:
    tree = mat.node_tree
    bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    output = next((n for n in tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if not bsdf or not output:
        continue
    emission = tree.nodes.new("ShaderNodeEmission")
    color = bsdf.inputs["Base Color"]
    if color.is_linked:
        tree.links.new(color.links[0].from_socket, emission.inputs["Color"])
    else:
        emission.inputs["Color"].default_value = color.default_value
    tree.links.new(emission.outputs[0], output.inputs["Surface"])
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 8
scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"
data = bpy.data.cameras.new("Color stability")
camera = bpy.data.objects.new("Color stability", data)
scene.collection.objects.link(camera)
scene.camera = camera
data.type = "ORTHO"
OUT = R / "artifacts/validation"
images = []
# A stable shader must also preserve the original source pattern, not simply
# become a constant color. Compare Geometry.Position and the anchor on the
# original A-pose coordinates before testing height changes in the T-pose.
for ob, start, end in cache["slices"]:
    ob.data.vertices.foreach_set("co", cache["rest"][start:end].ravel())
    ob.data.update()
tree = body.data.materials[0].node_tree
anchor = next(
    n for n in tree.nodes if n.type == "ATTRIBUTE" and n.attribute_name == bm.REST
)
targets = [
    link.to_socket
    for link in tree.links
    if link.from_node == anchor and link.from_socket.name == "Vector"
]
geometry = next(n for n in tree.nodes if n.type == "NEW_GEOMETRY")
reference = []
scale = bm.defaults()["height"] / 100.0
center = Vector((CENTER_X, 0, FLOOR + scale / 2.0))
camera.location = center + Vector((0, -4 * scale, 0))
camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
data.ortho_scale = scale * 1.13
for label, output in (
    ("source_position", geometry.outputs["Position"]),
    ("source_anchor", anchor.outputs["Vector"]),
):
    for target in targets:
        tree.links.new(output, target)
    scene.render.filepath = str(OUT / f"color_{label}.png")
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(scene.render.filepath, check_existing=False)
    a = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(a)
    reference.append(a)
source_error = float(np.mean(abs(reference[0] - reference[1])))
assert source_error < 0.001, source_error
for height in (145.0, 200.0):
    root.base_modeler.height = height
    assert not bm._ERRORS
    scale = height / 100.0
    center = Vector((CENTER_X, 0, FLOOR + scale / 2.0))
    camera.location = center + Vector((0, -4 * scale, 0))
    camera.rotation_euler = (
        (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    )
    data.ortho_scale = scale * 1.13
    scene.render.filepath = str(OUT / f"color_height_{int(height)}.png")
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(scene.render.filepath, check_existing=False)
    a = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(a)
    images.append(a.reshape(-1, 4))
delta = abs(images[0] - images[1])
mean = float(delta.mean())
assert mean < 0.003, mean
report = {
    "custom_normals_removed": True,
    "material_uses_rest_coordinates": True,
    "source_pattern_render_mean_absolute_difference": source_error,
    "height_render_mean_absolute_difference": mean,
    "passed": True,
}
(OUT / "material_stability.json").write_text(json.dumps(report, indent=2) + "\n")
print("MATERIAL STABILITY", report, flush=True)
