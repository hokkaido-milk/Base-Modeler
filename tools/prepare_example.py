"""Generate the clean, editable example from the shipping foundation."""

import sys
from pathlib import Path
import bpy
from mathutils import Quaternion, Vector
import base_modeler as bm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from scene_cleanup import clean_scene  # noqa: E402

bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
clean_scene(root)
scene = bpy.context.scene
scene.name = "Base Modeler"
scene.render.engine = "BLENDER_EEVEE"
scene.frame_set(1)
for screen in bpy.data.screens:
    for area in screen.areas:
        for space in area.spaces:
            if space.type != "VIEW_3D":
                continue
            space.show_region_ui = True
            space.shading.type = "MATERIAL"
            space.shading.use_scene_lights = False
            space.shading.use_scene_world = False
            space.region_3d.view_distance = 2.7
            space.region_3d.view_rotation = Quaternion((1, 0, 0), 1.5707963267948966)
            space.region_3d.view_location = Vector((-0.00455, 0, 0.89))
root.select_set(True)
bpy.context.view_layer.objects.active = root
clean_scene(root)
bpy.context.preferences.filepaths.save_version = 0
path = ROOT / "examples/Base Modeler.blend"
path.parent.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True, relative_remap=False)
print("CLEAN EDITABLE EXAMPLE", path, flush=True)
