"""Model lookup, immutable evaluation caches and transactional slider updates."""

import bpy
import numpy as np
from bpy.app.handlers import persistent
from .controls import CONTROLS
from .deform import compile_fields, evaluate, apply_height
from .surface import prepare_surfaces, match_skin_tone
from .topology import repair_tessellation
from .rig import rig_for, upgrade_rig_display
from .identity import REGIONS, meshes_for, region_name, assign_regions
from .constants import REST, SHAPE_SCHEMA

_CACHE = {}
_ERRORS = {}
_GUARD = set()


def model_for(context):
    ob = context.active_object
    while ob:
        if ob.get("base_modeler_model") == 1:
            return ob
        ob = ob.parent
    return None


def cache_for(root):
    objects = meshes_for(root)
    found = tuple(region_name(ob) for ob in objects)
    if found != REGIONS:
        problem = "missing" if set(REGIONS) - set(found) else "duplicated or unknown"
        raise ValueError(f"A model region is {problem}. Create a new base model.")
    signature = tuple(
        (
            o.as_pointer(),
            o.data.as_pointer(),
            len(o.data.vertices),
            len(o.data.edges),
            len(o.data.polygons),
        )
        for o in objects
    )
    key = root.as_pointer()
    if key in _CACHE and _CACHE[key]["signature"] == signature:
        return _CACHE[key]
    arrays = []
    slices = []
    start = 0
    for ob in objects:
        mesh = ob.data
        expected = ob.get("base_modeler_topology")
        if list(expected or []) != [
            len(mesh.vertices),
            len(mesh.edges),
            len(mesh.polygons),
        ]:
            raise ValueError(
                "Topology changed. Create a new base model to use the sliders."
            )
        attr = mesh.attributes.get(REST)
        if not attr or attr.domain != "POINT" or attr.data_type != "FLOAT_VECTOR":
            raise ValueError("Rest coordinates are missing. Create a new base model.")
        a = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        attr.data.foreach_get("vector", a)
        a = a.reshape(-1, 3)
        if not np.isfinite(a).all():
            raise ValueError("Rest coordinates contain non-finite values.")
        arrays.append(a)
        slices.append((ob, start, start + len(a)))
        start += len(a)
    if not arrays:
        raise ValueError("Model meshes are missing. Create a new base model.")
    if root.get("base_modeler_shape_schema", 0) < 3:
        prepare_surfaces(objects)
    rest = np.concatenate(arrays)
    current = np.empty_like(rest)
    for ob, start, end in slices:
        ob.data.vertices.foreach_get("co", current[start:end].ravel())
    saved_values = root.get("base_modeler_evaluated_values", {})
    last_values = {
        c.id: float(saved_values.get(c.id, getattr(root.base_modeler, c.id)))
        for c in CONTROLS
    }
    # Drop caches for deleted models; each owns large evaluation arrays.
    live = {ob.as_pointer() for ob in bpy.data.objects if ob.get("base_modeler_model")}
    for stale in set(_CACHE) - live:
        _CACHE.pop(stale, None)
        _ERRORS.pop(stale, None)
    data = {
        "last_raw_span": root.get("base_modeler_raw_span"),
        "last_raw_result": None,
        "last_values": last_values,
        "signature": signature,
        "rest": rest,
        "fields": compile_fields(rest),
        "slices": slices,
        "last_result": current,
    }
    _CACHE[key] = data
    return data


def refresh_geometry(data):
    """Resynchronize cached uploads after manual edits before a whole-body reset."""
    current = np.empty_like(data["last_result"])
    for ob, start, end in data["slices"]:
        ob.data.vertices.foreach_get("co", current[start:end].ravel())
    data["last_result"] = current


def update_model(settings, context, *, preserve_length_scale=False):
    root = settings.id_data
    key = root.as_pointer()
    if not root.get("base_modeler_model") or key in _GUARD:
        return
    data = None
    uploaded = []
    saved_values = root.get("base_modeler_evaluated_values", {})
    rollback = {c.id: float(saved_values.get(c.id, c.default)) for c in CONTROLS}
    try:
        if rig_for(root):
            raise ValueError("Remove the simple rig before changing body proportions.")
        if any(o.mode != "OBJECT" for o in meshes_for(root)):
            raise ValueError("Return to Object Mode to change the body.")
        data = cache_for(root)
        values = {c.id: getattr(settings, c.id) for c in CONTROLS}
        previous_values = data["last_values"]
        rollback = previous_values.copy()
        lengths = ("thigh_length", "leg_length")
        changed = [
            name for name in lengths if abs(values[name] - previous_values[name]) > 1e-7
        ]
        keep_scale = (
            preserve_length_scale
            and changed
            and abs(values["height"] - previous_values["height"]) < 1e-5
        )
        # Explicit height edits only renormalize the last evaluated shape.
        # Preserve the raw coordinates to avoid an expensive flow integration
        # or accumulating rounding error on successive height edits.
        raw = data["last_raw_result"]
        if raw is None or any(
            values[c.id] != previous_values[c.id] for c in CONTROLS if c.id != "height"
        ):
            raw = evaluate(data["rest"], data["fields"], values, normalize_height=False)
        limit_note = ""
        if keep_scale:
            old_span = data["last_raw_span"]
            if old_span is None:
                old_raw = evaluate(
                    data["rest"],
                    data["fields"],
                    previous_values,
                    normalize_height=False,
                )
                old_span = float(np.ptp(old_raw[:, 2]))
            scale = previous_values["height"] / (100.0 * old_span)
            target_height = 100.0 * float(np.ptp(raw[:, 2])) * scale
            height_control = next(c for c in CONTROLS if c.id == "height")
            if not height_control.minimum <= target_height <= height_control.maximum:
                # Stop only the requested length edit at the height boundary;
                # globally shrinking the chest would reintroduce the bug.
                boundary = float(
                    np.clip(
                        target_height, height_control.minimum, height_control.maximum
                    )
                )
                fraction = float(
                    np.clip(
                        (boundary - previous_values["height"])
                        / (target_height - previous_values["height"]),
                        0.0,
                        1.0,
                    )
                )
                # Head and floor lie outside the leg blend, so overall span
                # is affine in these exact transports. One solve suffices.
                for name in changed:
                    values[name] = previous_values[name] + fraction * (
                        values[name] - previous_values[name]
                    )
                raw = evaluate(
                    data["rest"], data["fields"], values, normalize_height=False
                )
                target_height = 100.0 * float(np.ptp(raw[:, 2])) * scale
                limit_note = "Height limit reached; adjust Height before changing leg lengths further."
            _GUARD.add(key)
            try:
                for name in changed:
                    setattr(settings, name, values[name])
                    values[name] = getattr(settings, name)
                settings.height = target_height
                values["height"] = settings.height
            finally:
                _GUARD.discard(key)
        result = apply_height(raw, values["height"])
        # Compute/validate first; upload all regions only after evaluation succeeds.
        previous = data["last_result"]
        for ob, start, end in data["slices"]:
            # Leave unaffected regions out of Blender's normal/GPU rebuilds.
            if np.array_equal(previous[start:end], result[start:end]):
                continue
            uploaded.append((ob, start, end))
            ob.data.vertices.foreach_set("co", result[start:end].ravel())
            ob.data.update()
        data["last_result"] = result
        data["last_raw_result"] = raw
        data["last_raw_span"] = float(np.ptp(raw[:, 2]))
        root["base_modeler_raw_span"] = data["last_raw_span"]
        data["last_values"] = values.copy()
        root["base_modeler_evaluated_values"] = values
        root["base_modeler_height_limit"] = limit_note
        root["base_modeler_shape_schema"] = SHAPE_SCHEMA
        _ERRORS.pop(key, None)
    except (ValueError, ReferenceError, RuntimeError) as exc:
        # A failed callback must leave the visible shape and its controls in
        # the same state. Restore only this model, never unrelated scene data.
        if data is not None:
            for ob, start, end in uploaded:
                ob.data.vertices.foreach_set(
                    "co", data["last_result"][start:end].ravel()
                )
                ob.data.update()
        _GUARD.add(key)
        try:
            for name, value in rollback.items():
                setattr(settings, name, value)
        finally:
            _GUARD.discard(key)
        _ERRORS[key] = str(exc)


def control_updated(settings, context):
    update_model(settings, context, preserve_length_scale=True)


class BM_Settings(bpy.types.PropertyGroup):
    pass


BM_Settings.__annotations__ = {
    c.id: bpy.props.FloatProperty(
        name=c.label,
        description=c.description,
        min=c.minimum,
        max=c.maximum,
        default=c.default,
        precision=2 if c.id == "height" else 3,
        step=10 if c.id == "height" else 1,
        update=control_updated,
    )
    for c in CONTROLS
}


def forget(root):
    """Drop one model's evaluation cache and error, leaving other models intact."""
    key = root.as_pointer()
    _CACHE.pop(key, None)
    _ERRORS.pop(key, None)


@persistent
def clear_cache(*args):
    _CACHE.clear()
    _ERRORS.clear()
    _GUARD.clear()


@persistent
def upgrade_loaded_models(*args):
    clear_cache()
    for root in list(bpy.data.objects):
        if root.get("base_modeler_model") == 1:
            try:
                assign_regions(root)
                repair_tessellation(meshes_for(root))
                rig = rig_for(root)
                if rig is not None:
                    upgrade_rig_display(rig)
                if root.get("base_modeler_shape_schema", 0) < SHAPE_SCHEMA:
                    if root.get("base_modeler_shape_schema", 0) < 10:
                        match_skin_tone(meshes_for(root))
                    if rig_for(root) is None:
                        update_model(
                            root.base_modeler, bpy.context, preserve_length_scale=False
                        )
            except (ValueError, RuntimeError, ReferenceError) as exc:
                _ERRORS[root.as_pointer()] = str(exc)
