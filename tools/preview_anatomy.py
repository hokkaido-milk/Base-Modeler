"""Render anatomy review views and save a freshly weighted native rig."""

import bpy
import numpy as np
from pathlib import Path
from mathutils import Vector
import base_modeler as bm

bm.register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.base_modeler.create()
root = bpy.context.object
cache = bm.cache_for(root)
out = Path(__file__).resolve().parents[1] / "artifacts/female_review"
out.mkdir(parents=True, exist_ok=True)
tag = "after"
np.savez(out / (tag + ".npz"), points=cache["last_result"])
bpy.ops.base_modeler.generate_rig()
rig = bm.rig_for(root)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
s = scene.display.shading
s.light = "STUDIO"
s.color_type = "SINGLE"
s.single_color = (0.64, 0.64, 0.64)
s.show_shadows = True
s.show_cavity = True
s.cavity_type = "BOTH"
s.background_type = "WORLD"
scene.world.color = (0.15, 0.15, 0.15)
scene.render.resolution_x = 1000
scene.render.resolution_y = 1100
scene.render.resolution_percentage = 100
cam = bpy.data.objects.new("Review Camera", bpy.data.cameras.new("Review Camera"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = "ORTHO"
for label, target, offset, scale in [
    ("front", (0, 0, 0.85), (0, -4, 0), 1.85),
    ("back", (0, 0, 0.85), (0, 4, 0), 1.85),
    ("torso", (0, 0, 1.18), (0.35, -4, 0.1), 0.8),
    ("legs", (0, 0, 0.55), (0.4, -4, 0.1), 1.15),
    ("rear", (0, 0, 1.13), (0.5, 4, 0.1), 0.85),
    ("side", (0, 0, 0.85), (4, 0, 0), 1.85),
]:
    cam.location = Vector(target) + Vector(offset)
    cam.rotation_euler = (
        (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    )
    cam.data.ortho_scale = scale
    scene.render.filepath = str(out / f"{tag}_{label}.png")
    bpy.ops.render.render(write_still=True)
for label, pose in [
    (
        "seated",
        {
            "thigh.L": (1.57, 0, 0),
            "thigh.R": (1.57, 0, 0),
            "shin.L": (-1.57, 0, 0),
            "shin.R": (-1.57, 0, 0),
        },
    ),
    ("bend", {"spine": (0.5, 0, 0.15), "chest": (0, 0.2, 0)}),
]:
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    for name, rotation in pose.items():
        rig.pose.bones[name].rotation_euler = rotation
    rig.update_tag()
    bpy.context.view_layer.update()
    target = Vector((0, 0, 0.85))
    cam.location = target + Vector((2, -4, 0.4))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = 1.9
    scene.render.filepath = str(out / f"{tag}_{label}.png")
    bpy.ops.render.render(write_still=True)
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
    pb.select = False
rig.pose.bones["core"].select = True
rig.data.bones.active = rig.data.bones["core"]
rig.update_tag()
bpy.context.view_layer.update()
for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.region_3d.view_location = Vector((-0.00455, 0, 0.94))
                space.region_3d.view_rotation = Vector((-0.15, 1, -0.07)).to_track_quat(
                    "-Z", "Y"
                )
                space.region_3d.view_distance = 3.1
                space.shading.type = "SOLID"
                space.shading.color_type = "SINGLE"
                space.shading.single_color = (0.64, 0.64, 0.64)
                space.shading.show_cavity = True
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(
    filepath=str(out / "Female Anatomy - Rigged.blend"), compress=True
)
