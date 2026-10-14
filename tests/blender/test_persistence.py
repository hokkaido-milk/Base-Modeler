"""Length/height transactions survive native undo, cache reconstruction and reopening."""

import bpy
import sys
import numpy as np
import json
from pathlib import Path
import base_modeler as bm


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

OUT = R / "artifacts/validation"
bm.register()
if "--reopen" not in sys.argv:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.base_modeler.create()
    root = bpy.context.object
    root.base_modeler.height = 153.0
    root.base_modeler.breast_size = 1.4
    root.base_modeler.hip_size = 1.2
    c = bm.cache_for(root)
    neutral = c["last_result"].copy()
    name = root.name
    bpy.context.preferences.edit.use_global_undo = True
    bpy.ops.ed.undo_push(message="Before leg length")
    root.base_modeler.leg_length = 1.12
    q = c["last_result"].copy()
    height = root.base_modeler.height
    assert height > 153.0
    bpy.ops.ed.undo_push(message="After leg length")
    assert bpy.ops.ed.undo() == {"FINISHED"}
    root = bpy.data.objects[name]
    assert (
        abs(root.base_modeler.height - 153.0) < 1e-5
        and abs(root.base_modeler.leg_length - 1.0) < 1e-6
    )
    assert np.max(abs(bm.cache_for(root)["last_result"] - neutral)) < 1e-6
    assert bpy.ops.ed.redo() == {"FINISHED"}
    root = bpy.data.objects[name]
    assert abs(root.base_modeler.height - height) < 1e-5
    assert np.array_equal(bm.cache_for(root)["last_result"], q)
    bpy.context.view_layer.objects.active = root
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Length_Persistence.blend"))
    print("LENGTH UNDO/REDO PASSED", flush=True)
else:
    root = next(o for o in bpy.data.objects if o.get("base_modeler_model"))
    bpy.context.view_layer.objects.active = root
    c = bm.cache_for(root)
    before = c["last_result"].copy()
    height = root.base_modeler.height
    chest = np.flatnonzero(
        (c["rest"][:, 2] > 1.17)
        & (c["rest"][:, 2] < 1.4)
        & (abs(c["rest"][:, 0] - bm.deform.CENTER_X) < 0.13)
    )
    bm.clear_cache()
    root.base_modeler.thigh_length = 1.1
    c = bm.cache_for(root)
    delta = c["last_result"][chest] - before[chest]
    error = float(np.max(np.ptp(delta, axis=0)))
    assert error < 2e-6, error
    assert root.base_modeler.height > height and not bm._ERRORS
    assert bpy.ops.base_modeler.reset(field="thigh_length") == {"FINISHED"}
    assert np.max(abs(c["last_result"] - before)) < 2e-6
    report = {
        "undo_redo_height_and_length_together": True,
        "saved_file_cache_reconstruction": True,
        "chest_residual_m": error,
        "passed": True,
    }
    (OUT / "persistence.json").write_text(json.dumps(report, indent=2) + "\n")
    print("LENGTH PERSISTENCE", report, flush=True)
