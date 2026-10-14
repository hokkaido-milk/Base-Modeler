"""Regression checks for reset scope, regional length isolation and expanded ranges."""

import bpy
import sys
import json
import numpy as np
from pathlib import Path
import base_modeler as bm
from base_modeler.controls import BY_ID, defaults, GROUPS


R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R))

OUT = R / "artifacts/validation"
OUT.mkdir(exist_ok=True)
bm.register()
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
bpy.ops.base_modeler.create()
root = bpy.context.object
c = bm.cache_for(root)


def values():
    return {x.id: getattr(root.base_modeler, x.id) for x in bm.CONTROLS}


def set_values(v):
    bm._GUARD.add(root.as_pointer())
    try:
        for key, value in v.items():
            setattr(root.base_modeler, key, value)
    finally:
        bm._GUARD.discard(root.as_pointer())
    bm.update_model(root.base_modeler, bpy.context)
    assert not bm._ERRORS, bm._ERRORS
    return c["last_result"].copy()


neutral = set_values(defaults())
# Every reset is invoked after stale operator properties from another region.
# SKIP_SAVE prevents those unspecified properties reappearing on UI invocation.
last = bpy.context.window_manager.operator_properties_last("base_modeler.reset")
reset_cases = []
for control in bm.CONTROLS:
    set_values(
        dict(
            defaults(),
            waist_size=0.91,
            head_size=1.05,
            **(
                {control.id: control.maximum}
                if control.id not in ("waist_size", "head_size")
                else {}
            ),
        )
    )
    if control.id in ("waist_size", "head_size"):
        setattr(root.base_modeler, control.id, control.maximum)
    before = values()
    last.group = "Butt"
    last.field = "butt_gap"
    assert bpy.ops.base_modeler.reset("INVOKE_DEFAULT", field=control.id) == {
        "FINISHED"
    }
    after = values()
    assert abs(after[control.id] - control.default) < 1e-5, (control.id, after)
    for key in before:
        if key not in (control.id, "height"):
            assert after[key] == before[key], (control.id, "changed unrelated", key)
    reset_cases.append("field:" + control.id)
for group in GROUPS:
    custom = {x.id: x.default + 0.25 * (x.maximum - x.default) for x in bm.CONTROLS}
    set_values(custom)
    before = values()
    last.group = "Butt"
    last.field = "butt_gap"
    assert bpy.ops.base_modeler.reset("INVOKE_DEFAULT", group=group) == {"FINISHED"}
    after = values()
    for control in bm.CONTROLS:
        if control.group == group:
            assert abs(after[control.id] - control.default) < 1e-5, (
                group,
                control.id,
                after[control.id],
            )
        elif control.id != "height":
            assert after[control.id] == before[control.id], (
                group,
                "changed unrelated",
                control.id,
            )
    reset_cases.append("group:" + group)
last.group = "Butt"
last.field = "butt_gap"
assert bpy.ops.base_modeler.reset("INVOKE_DEFAULT") == {"FINISHED"}
assert max(abs(values()[x.id] - x.default) for x in bm.CONTROLS) < 1e-5
assert np.max(abs(c["last_result"] - neutral)) < 1e-6
# Chest shape is preserved under real property callbacks, including custom torsos.
chest = np.flatnonzero(
    (neutral[:, 2] > 1.17)
    & (neutral[:, 2] < 1.4)
    & (abs(neutral[:, 0] - bm.deform.CENTER_X) < 0.13)
)
hips = np.flatnonzero((neutral[:, 2] > 0.7) & (neutral[:, 2] < 1.12))
isolation = []
for custom in (
    {},
    dict(
        height=155.0,
        breast_size=1.3,
        butt_size=1.4,
        hip_size=1.2,
        waist_size=0.91,
        ribcage_width=1.09,
        arm_size=1.1,
    ),
):
    for key in ("thigh_length", "leg_length"):
        for amount in (0.85, 1.15):
            before = set_values(dict(defaults(), **custom))
            height = root.base_modeler.height
            setattr(root.base_modeler, key, amount)
            q = c["last_result"].copy()
            assert not bm._ERRORS
            delta = q[chest] - before[chest]
            residual = float(np.max(np.ptp(delta, axis=0)))
            assert residual < 2e-6, (custom, key, amount, residual)
            assert abs(root.base_modeler.height - height) > 0.1
            assert abs(float(np.ptp(q[:, 2])) * 100 - root.base_modeler.height) < 0.0001
            isolation.append(
                {
                    "control": key,
                    "value": amount,
                    "custom": bool(custom),
                    "chest_residual_m": residual,
                    "height_cm": root.base_modeler.height,
                }
            )
            assert bpy.ops.base_modeler.reset(field=key) == {"FINISHED"}
            assert np.max(abs(c["last_result"] - before)) < 2e-6, (
                key,
                "reset did not restore torso scale",
            )
    for lengths in (
        {},
        dict(thigh_length=1.15, leg_length=1.15),
        dict(thigh_length=0.85, leg_length=0.85),
    ):
        before = set_values(dict(defaults(), **custom, **lengths))
        for amount in (0.85, 1.15):
            root.base_modeler.arm_length = amount
            q = c["last_result"].copy()
            error = float(np.max(abs(q[hips] - before[hips])))
            assert error < 1e-7, (
                custom,
                lengths,
                amount,
                "arm length leaked to hips",
                error,
            )
            isolation.append(
                {
                    "control": "arm_length",
                    "value": amount,
                    "custom": bool(custom),
                    "lengths": lengths,
                    "hip_max_error_m": error,
                }
            )
# Height boundaries constrain the length edit rather than resizing the chest.
for height, amount in [(120.0, 0.85), (200.0, 1.15)]:
    before = set_values(dict(defaults(), height=height))
    root.base_modeler.leg_length = amount
    assert abs(root.base_modeler.height - height) < 1e-4
    assert np.max(abs(c["last_result"][chest] - before[chest])) < 2e-6
    assert root.get("base_modeler_height_limit")
# Verify advertised and RNA limits agree, with actual mesh generation at each.
limits = {
    "height": (120.0, 200.0),
    "breast_size": (-1.0, 2.5),
    "breast_firmness": (-1.5, 1.0),
    "hip_size": (0.85, 1.3),
    "butt_size": (-1.0, 2.0),
    "thigh_size": (0.85, 1.3),
}
for key, (lo, hi) in limits.items():
    prop = root.base_modeler.bl_rna.properties[key]
    assert abs(prop.hard_min - lo) < 1e-6 and abs(prop.hard_max - hi) < 1e-6
    assert BY_ID[key].minimum == lo and BY_ID[key].maximum == hi
    for amount in (lo, hi):
        assert np.isfinite(set_values(dict(defaults(), **{key: amount}))).all()
set_values(defaults())
report = {
    "field_resets": 27,
    "group_resets": len(GROUPS),
    "stale_operator_scope_ignored": True,
    "reset_all": True,
    "isolation": isolation,
    "ranges": limits,
    "height_boundaries_keep_torso_size": True,
    "passed": True,
}
(OUT / "regression.json").write_text(json.dumps(report, indent=2) + "\n")
print("CONTROL FIXES PASSED", json.dumps(report), flush=True)
