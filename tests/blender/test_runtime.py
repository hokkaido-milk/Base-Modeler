"""Failure rollback, stable identities and accelerated/reference equivalence."""

import bpy
import json
import time
import numpy as np
from pathlib import Path
import base_modeler as bm
from base_modeler import model, operators, library, native
from base_modeler.identity import region_name


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "validation"
OUT.mkdir(parents=True, exist_ok=True)
bm.register()
assert bpy.ops.base_modeler.create() == {"FINISHED"}
root = bpy.context.object
cache = bm.cache_for(root)
neutral = cache["last_result"].copy()
settings = root.base_modeler
# Failed evaluations restore both the controls and all mesh coordinates.
evaluate = model.evaluate
try:

    def fail(*args, **kwargs):
        raise ValueError("Injected evaluator failure")

    model.evaluate = fail
    settings.waist_size = 0.91
    assert settings.waist_size == 1.0 and root.as_pointer() in bm._ERRORS
    assert np.array_equal(cache["last_result"], neutral)
finally:
    model.evaluate = evaluate
settings.waist_size = 1.0
assert not bm._ERRORS
# Invalid topology must not silently accept a new binding or changed settings.
skin = next(ob for ob in bm.meshes_for(root) if region_name(ob) == "Body_Surface")
counts = list(skin["base_modeler_topology"])
skin["base_modeler_topology"] = [0, 0, 0]
bm.clear_cache()
settings.build = 1.1
assert settings.build == 1.0 and root.as_pointer() in bm._ERRORS
skin["base_modeler_topology"] = counts
settings.build = 1.0
assert not bm._ERRORS
# Renaming display objects and mesh datablocks cannot reorder deformation bindings.
for i, ob in enumerate(bm.meshes_for(root)):
    ob.name = f"Custom part {100-i}"
    ob.data.name = f"Custom mesh {100-i}"
bm.clear_cache()
settings.breast_size = 2.5
settings.breast_firmness = -1.5
cache = bm.cache_for(root)
values = {c.id: getattr(settings, c.id) for c in bm.CONTROLS}
expected = bm.evaluate(cache["rest"], cache["fields"], values)
assert np.array_equal(cache["last_result"], expected)
assert bpy.ops.base_modeler.generate_rig() == {"FINISHED"}
rig = bm.rig_for(root)
bpy.ops.object.mode_set(mode="OBJECT")
# Programmatic edits while rigged must restore their previous applied values.
settings.waist_size = 0.9
assert settings.waist_size == 1.0 and root.as_pointer() in bm._ERRORS
rig["base_modeler_group_names"] = "malformed"
assert bpy.ops.base_modeler.remove_rig() == {"FINISHED"}
assert not bm._ERRORS and bm.rig_for(root) is None
assert all(not ob.vertex_groups for ob in bm.meshes_for(root))
# Failed creation removes appended IDs but preserves existing and orphan user data.
user_material = bpy.data.materials.new("Retain my unused material")
before = library.snapshot()
active = bpy.context.object
update = operators.update_model
try:

    def fail_create(*args, **kwargs):
        raise ValueError("Injected creation failure")

    operators.update_model = fail_create
    try:
        result = bpy.ops.base_modeler.create()
        assert result == {"CANCELLED"}
    except RuntimeError as exc:
        assert "Injected creation failure" in str(exc)
finally:
    operators.update_model = update
assert library.snapshot() == before
assert user_material.name in bpy.data.materials and bpy.context.object == active
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
# A whole-body reset must also restore manually moved mesh vertices when the
# sliders were already neutral; cached upload comparisons must not skip them.
part = bm.meshes_for(root)[0]
original_point = part.data.vertices[0].co.copy()
part.data.vertices[0].co.x += 0.01
part.data.update()
assert bpy.ops.base_modeler.reset() == {"FINISHED"}
assert (part.data.vertices[0].co - original_point).length < 1e-7
# Height edits reuse raw shape coordinates and exactly match full reevaluation.
settings.waist_size = 0.91
cache = bm.cache_for(root)
raw = cache["last_raw_result"]
height_times = []
for height in (120.0, 155.0, 200.0, bm.defaults()["height"]):
    start = time.perf_counter()
    settings.height = height
    height_times.append((time.perf_counter() - start) * 1000.0)
    assert cache["last_raw_result"] is raw
    values = {c.id: getattr(settings, c.id) for c in bm.CONTROLS}
    expected = bm.evaluate(cache["rest"], cache["fields"], values)
    assert np.array_equal(cache["last_result"], expected)
# NumPy fallback and native kernels agree at new breast and mixed endpoints.
parity = []
cases = [dict(bm.defaults(), breast_size=2.5, breast_firmness=-1.5)]
rng = np.random.default_rng(93)
cases += [
    {c.id: float(rng.uniform(c.minimum, c.maximum)) for c in bm.CONTROLS}
    for _ in range(16)
]
for values in cases:
    fast = bm.evaluate(cache["rest"], cache["fields"], values)
    slow = bm.evaluate(cache["rest"], cache["fields"], values, use_native=False)
    error = float(np.max(abs(fast - slow)))
    assert error < 2e-6
    parity.append(error)
if native.LIBRARY is not None:
    try:
        native.integrate(
            np.zeros((1, 3)), np.zeros((1, 3)), np.zeros((1, 3)), (2, 2, 2)
        )
        raise AssertionError("Malformed native arrays were accepted")
    except ValueError:
        pass
# Interrupted registration must not leave half-registered classes or handlers.
bm.unregister()
register_class = bpy.utils.register_class
try:

    def fail_register(cls):
        if cls is bm.BM_OT_reset:
            raise RuntimeError("Injected registration failure")
        return register_class(cls)

    bpy.utils.register_class = fail_register
    try:
        bm.register()
        raise AssertionError("Registration should have failed")
    except RuntimeError as exc:
        assert "Injected registration failure" in str(exc)
finally:
    bpy.utils.register_class = register_class
assert not hasattr(bpy.types.Object, "base_modeler")
assert all(not cls.is_registered for cls in bm._CLASSES)
assert bm.clear_cache not in bpy.app.handlers.undo_post
assert bm.upgrade_loaded_models not in bpy.app.handlers.load_post
bm.register()
bm.unregister()
bm.unregister()
bm.register()
report = {
    "registration_rollback": True,
    "reset_restores_manual_vertex_edits": True,
    "failed_update_rollback": True,
    "failed_creation_rollback": True,
    "user_data_preserved": True,
    "renamed_regions_and_rig": True,
    "rigged_settings_rollback": True,
    "height_median_ms": float(np.median(height_times)),
    "parity_cases": len(parity),
    "max_parity_error_m": max(parity),
    "passed": True,
}
(OUT / "runtime.json").write_text(json.dumps(report, indent=2) + "\n")
print("RUNTIME VALIDATION", json.dumps(report), flush=True)
