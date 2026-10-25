"""Check the actual installed extension, including disable/enable and native rigging."""

import bpy
import importlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
name = "bl_ext.user_default.base_modeler"
assert name in bpy.context.preferences.addons
bm = importlib.import_module(name)
profile = Path(os.environ["BLENDER_USER_CONFIG"]).parent
assert Path(bm.__file__).resolve().is_relative_to(profile.resolve())
root = next(ob for ob in bpy.data.objects if ob.get("base_modeler_model"))
assert bpy.ops.preferences.addon_disable(module=name) == {"FINISHED"}
assert not hasattr(bpy.types.Object, "base_modeler")
assert bpy.ops.preferences.addon_enable(module=name) == {"FINISHED"}
bm = importlib.import_module(name)
bm.upgrade_loaded_models()
root.select_set(True)
bpy.context.view_layer.objects.active = root
root.base_modeler.breast_size = 2.5
root.base_modeler.breast_firmness = -1.5
assert root.base_modeler.breast_firmness == -1.5 and not bm._ERRORS
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
assert rig and len(rig.data.bones) == 83
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
assert not bm._ERRORS and bm.rig_for(root) is None
report = {
    "version": ".".join(map(str, bm.VERSION)),
    "enabled_from_saved_preferences": True,
    "disable_enable": True,
    "installed_controls_and_rig": True,
    "installed_path": bm.__file__,
    "passed": True,
}
(ROOT / "artifacts/validation/installed.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("INSTALLED VALIDATION", json.dumps(report), flush=True)
