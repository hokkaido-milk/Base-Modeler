"""Verify installed startup and show the editable example in lit shading."""

import bpy
import importlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
name = "bl_ext.user_default.base_modeler"
assert name in bpy.context.preferences.addons
bm = importlib.import_module(name)
root = next(ob for ob in bpy.data.objects if ob.get("base_modeler_model"))
if bpy.context.object and bpy.context.object.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.select_all(action="DESELECT")
root.select_set(True)
bpy.context.view_layer.objects.active = root
bpy.context.scene.render.engine = "BLENDER_EEVEE"
for area in bpy.context.screen.areas:
    if area.type != "VIEW_3D":
        continue
    space = area.spaces.active
    space.show_region_ui = True
    space.shading.type = "MATERIAL"
    space.shading.use_scene_lights = False
    space.shading.use_scene_world = False
    for region in area.regions:
        if region.type == "UI" and hasattr(region, "active_panel_category"):
            try:
                region.active_panel_category = "Base Modeler"
            except (AttributeError, RuntimeError):
                pass
report = {
    "pid": os.getpid(),
    "name": "Base Modeler",
    "version": ".".join(map(str, bm.VERSION)),
    "installed_path": bm.__file__,
    "file": bpy.data.filepath,
    "mode": bpy.context.mode,
    "enabled_from_saved_preferences": True,
}
(ROOT / "artifacts/validation/session.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("BASE MODELER READY", json.dumps(report), flush=True)
