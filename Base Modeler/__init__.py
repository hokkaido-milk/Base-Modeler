"""Base Modeler Blender extension entry point."""

import bpy
from .constants import VERSION, REST, SHAPE_SCHEMA
from .controls import CONTROLS, GROUPS, defaults
from .deform import compile_fields, evaluate, apply_height
from .topology import repair_tessellation
from .rig import rig_for
from .model import (
    BM_Settings,
    model_for,
    meshes_for,
    cache_for,
    update_model,
    clear_cache,
    upgrade_loaded_models,
    _CACHE,
    _ERRORS,
    _GUARD,
)
from .operators import (
    BM_OT_create,
    BM_OT_reset,
    BM_OT_generate_rig,
    BM_OT_pose_rig,
    BM_OT_remove_rig,
)
from .ui import BM_PT_actions, BM_PT_body

__all__ = [
    "REST",
    "SHAPE_SCHEMA",
    "CONTROLS",
    "GROUPS",
    "defaults",
    "compile_fields",
    "evaluate",
    "apply_height",
    "repair_tessellation",
    "rig_for",
    "model_for",
    "meshes_for",
    "cache_for",
    "update_model",
    "clear_cache",
    "upgrade_loaded_models",
    "BM_Settings",
    "_CACHE",
    "_ERRORS",
    "_GUARD",
    "register",
    "unregister",
]

bl_info = {
    "name": "Base Modeler",
    "author": "Base Modeler contributors",
    "version": VERSION,
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > Base Modeler",
    "description": "Shape an adult anime body and generate a native FK rig",
    "category": "Mesh",
}

_CLASSES = (
    BM_Settings,
    BM_OT_create,
    BM_OT_reset,
    BM_OT_generate_rig,
    BM_OT_pose_rig,
    BM_OT_remove_rig,
    BM_PT_actions,
    BM_PT_body,
)


def _handlers():
    """Application handlers owned by the extension, shared by (un)registration."""
    return (
        (bpy.app.handlers.undo_post, clear_cache),
        (bpy.app.handlers.redo_post, clear_cache),
        (bpy.app.handlers.load_post, upgrade_loaded_models),
    )


def register():
    registered = []
    added_hooks = []
    pointer_created = False
    timer_created = False
    try:
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.Object.base_modeler = bpy.props.PointerProperty(type=BM_Settings)
        pointer_created = True
        for hooks, handler in _handlers():
            if handler not in hooks:
                hooks.append(handler)
                added_hooks.append((hooks, handler))
        # Blender restricts bpy.data during addon_utils.enable(). Repair loaded
        # models only after that registration guard is released.
        if hasattr(bpy.data, "objects"):
            upgrade_loaded_models()
        elif not bpy.app.timers.is_registered(upgrade_loaded_models):
            bpy.app.timers.register(upgrade_loaded_models, first_interval=0.1)
            timer_created = True
    except Exception:
        if timer_created:
            bpy.app.timers.unregister(upgrade_loaded_models)
        for hooks, handler in added_hooks:
            hooks.remove(handler)
        if pointer_created:
            del bpy.types.Object.base_modeler
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
        clear_cache()
        raise


def unregister():
    if bpy.app.timers.is_registered(upgrade_loaded_models):
        bpy.app.timers.unregister(upgrade_loaded_models)
    for hooks, handler in _handlers():
        if handler in hooks:
            hooks.remove(handler)
    clear_cache()
    if hasattr(bpy.types.Object, "base_modeler"):
        del bpy.types.Object.base_modeler
    for cls in reversed(_CLASSES):
        if cls.is_registered:
            bpy.utils.unregister_class(cls)
