"""Generate a clean native rig preview from the editable example."""

from pathlib import Path
import bpy
from mathutils import Vector
import base_modeler as bm

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT / "examples/Base Modeler.blend"))
bm.register()
root = next(ob for ob in bpy.data.objects if ob.get("base_modeler_model"))
bpy.context.view_layer.objects.active = root
root.select_set(True)
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
for bone in rig.pose.bones:
    bone.select = False
rig.pose.bones["hand.L"].select = True
rig.data.bones.active = rig.data.bones["hand.L"]
for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type != "VIEW_3D":
                continue
            space.region_3d.view_location = Vector((0.61, -0.035, 1.424))
            space.region_3d.view_rotation = Vector((0, -0.7, -1)).to_track_quat(
                "-Z", "Y"
            )
            space.region_3d.view_distance = 0.48
            space.shading.type = "MATERIAL"
            space.shading.use_scene_lights = False
            space.shading.use_scene_world = False
bpy.context.preferences.filepaths.save_version = 0
path = ROOT / "artifacts/rig_refinement/Base Modeler Rig.blend"
path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=False)
print("REFINED RIG PREVIEW", path, flush=True)
