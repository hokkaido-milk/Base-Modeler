"""Undoable model creation, reset and native-rig commands."""

from pathlib import Path
import bpy
from .controls import CONTROLS, GROUPS, BY_ID, defaults
from .deform import evaluate
from .topology import repair_tessellation
from .rig import rig_for, generate as generate_rig, remove as remove_rig
from .model import (
    model_for,
    meshes_for,
    cache_for,
    refresh_geometry,
    update_model,
    clear_cache,
    _ERRORS,
    _GUARD,
)
from .identity import assign_regions
from . import library


class BM_OT_create(bpy.types.Operator):
    bl_idname = "base_modeler.create"
    bl_label = "Create Base Model"
    bl_description = "Add an independent model from the bundled foundation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        before = library.snapshot()
        loaded = []
        collection = None
        selected = list(context.selected_objects)
        active = context.view_layer.objects.active
        try:
            path = Path(__file__).parent / "assets" / "foundation.blend"
            with bpy.data.libraries.load(str(path), link=False) as (source, target):
                target.objects = list(source.objects)
            loaded = [o for o in target.objects if o]
            root = next(o for o in loaded if o.get("base_modeler_model") == 1)
            collection = bpy.data.collections.new("Base Modeler")
            context.scene.collection.children.link(collection)
            for ob in loaded:
                collection.objects.link(ob)
            root.name = "Base Modeler"
            assign_regions(root)
            # Native duplicates own their mesh datablocks; models never share edits.
            for ob in meshes_for(root):
                ob.hide_set(False)
            repair_tessellation(meshes_for(root))
            cache_for(root)
            update_model(root.base_modeler, context, preserve_length_scale=False)
            if root.as_pointer() in _ERRORS:
                raise ValueError(_ERRORS[root.as_pointer()])
            bpy.ops.object.select_all(action="DESELECT")
            root.select_set(True)
            context.view_layer.objects.active = root
            self.report({"INFO"}, "Base Modeler: 27 body controls ready")
            return {"FINISHED"}
        except Exception as exc:
            library.rollback(before)
            clear_cache()
            for ob in selected:
                ob.select_set(True)
            context.view_layer.objects.active = active
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class BM_OT_reset(bpy.types.Operator):
    bl_idname = "base_modeler.reset"
    bl_label = "Reset Body Controls"
    bl_description = "Restore the supplied shape for this region or the whole body"
    bl_options = {"REGISTER", "UNDO"}
    group: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    field: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        root = model_for(context)
        return context.mode == "OBJECT" and root is not None and rig_for(root) is None

    def execute(self, context):
        root = model_for(context)
        key = root.as_pointer()
        if (
            self.group
            and self.group not in GROUPS
            or self.field
            and self.field not in BY_ID
        ):
            self.report({"ERROR"}, "Unknown body control or region.")
            return {"CANCELLED"}
        if self.group and self.field and BY_ID[self.field].group != self.group:
            self.report({"ERROR"}, "The control does not belong to that region.")
            return {"CANCELLED"}
        if not self.group and not self.field:
            try:
                refresh_geometry(cache_for(root))
            except (ValueError, RuntimeError, ReferenceError) as exc:
                _ERRORS[key] = str(exc)
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
        _GUARD.add(key)
        try:
            for c in CONTROLS:
                if (not self.group or c.group == self.group) and (
                    not self.field or c.id == self.field
                ):
                    setattr(root.base_modeler, c.id, c.default)
        finally:
            _GUARD.discard(key)
        update_model(
            root.base_modeler,
            context,
            preserve_length_scale=bool(
                self.field
                and self.field != "height"
                or self.group
                and self.group != "Global"
            ),
        )
        if key in _ERRORS:
            self.report({"ERROR"}, _ERRORS[key])
            return {"CANCELLED"}
        return {"FINISHED"}


class BM_OT_generate_rig(bpy.types.Operator):
    bl_idname = "base_modeler.generate_rig"
    bl_label = "Generate Simple Rig"
    bl_description = (
        "Fit and bind a basic human skeleton to this body, then enter Pose Mode"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        root = model_for(context)
        return context.mode == "OBJECT" and root is not None and rig_for(root) is None

    def execute(self, context):
        root = model_for(context)
        try:
            cache = cache_for(root)
            reference = evaluate(cache["rest"], cache["fields"], defaults())
            rig = generate_rig(context, root, cache, reference)
            self.report(
                {"INFO"},
                str(len(rig.data.bones))
                + " bones ready: select a bone, then G to move or R to rotate",
            )
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class BM_OT_pose_rig(bpy.types.Operator):
    bl_idname = "base_modeler.pose_rig"
    bl_label = "Pose Simple Rig"
    bl_description = (
        "Select the skeleton and enter Pose Mode; move or rotate its bones directly"
    )

    @classmethod
    def poll(cls, context):
        root = model_for(context)
        return (
            context.mode in ("OBJECT", "POSE")
            and root is not None
            and rig_for(root) is not None
        )

    def execute(self, context):
        rig = rig_for(model_for(context))
        if context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="POSE")
        return {"FINISHED"}


class BM_OT_remove_rig(bpy.types.Operator):
    bl_idname = "base_modeler.remove_rig"
    bl_label = "Remove Simple Rig"
    bl_description = (
        "Remove the skeleton and its pose, returning to the editable unposed body"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        root = model_for(context)
        return (
            context.mode in ("OBJECT", "POSE")
            and root is not None
            and rig_for(root) is not None
        )

    def execute(self, context):
        root = model_for(context)
        remove_rig(context, root)
        clear_cache()
        update_model(root.base_modeler, context)
        if root.as_pointer() in _ERRORS:
            self.report({"WARNING"}, _ERRORS[root.as_pointer()])
        return {"FINISHED"}
