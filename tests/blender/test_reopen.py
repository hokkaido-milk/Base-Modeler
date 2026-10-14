import bpy
import sys
import numpy as np
from pathlib import Path
import base_modeler as bm


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

bm.register()
root = next(o for o in bpy.data.objects if o.get("base_modeler_model") == 1)
bpy.context.view_layer.objects.active = root
bm.clear_cache()
root.base_modeler.waist_size = 0.91
assert not bm._ERRORS
cache = bm.cache_for(root)
assert len(cache["rest"]) == 271342
neutral = bm.evaluate(cache["rest"], cache["fields"], bm.defaults())
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
for ob, a, b in cache["slices"]:
    p = np.empty((b - a) * 3, np.float32)
    ob.data.vertices.foreach_get("co", p)
    assert np.max(abs(p.reshape(-1, 3) - neutral[a:b])) < 3e-7
icons = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items
assert "LOOP_BACK" in icons
# Every slider is backed by registered RNA, with an update callback.
for c in bm.CONTROLS:
    assert c.id in bm.BM_Settings.bl_rna.properties
bm.unregister()
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
assert not bm._ERRORS
print("REOPEN, RESET, RNA, ICONS, REGISTER/UNREGISTER PASSED")
