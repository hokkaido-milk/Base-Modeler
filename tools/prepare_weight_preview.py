"""Save the limited, freshly weighted drawing-reference rig in a clean scene."""

from pathlib import Path
import bpy
from mathutils import Vector
import base_modeler as bm

ROOT = Path(__file__).resolve().parents[1]
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
for pb in rig.pose.bones:
    pb.select = False
rig.pose.bones["core"].select = True
rig.data.bones.active = rig.data.bones["core"]
for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type != "VIEW_3D":
                continue
            space.show_region_ui = True
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
path = ROOT / "artifacts/weight_refinement/Female Anatomy - Limited Rig.blend"
path.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=False)
print("LIMITED RIG PREVIEW", path, flush=True)
