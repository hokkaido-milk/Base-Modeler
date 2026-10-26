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
    forget,
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
            root = next((o for o in loaded if o.get("base_modeler_model") == 1), None)
            if root is None:
                raise ValueError("The bundled foundation has no model root.")
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
            self.report({"INFO"}, f"Base Modeler: {len(CONTROLS)} body controls ready")
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
        group, field = self.group, self.field
        if (group and group not in GROUPS) or (field and field not in BY_ID):
            self.report({"ERROR"}, "Unknown body control or region.")
            return {"CANCELLED"}
        if group and field and BY_ID[field].group != group:
            self.report({"ERROR"}, "The control does not belong to that region.")
            return {"CANCELLED"}
        if not group and not field:
            try:
                refresh_geometry(cache_for(root))
            except (ValueError, RuntimeError, ReferenceError) as exc:
                _ERRORS[key] = str(exc)
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
        _GUARD.add(key)
        try:
            for c in CONTROLS:
                if (not group or c.group == group) and (not field or c.id == field):
                    setattr(root.base_modeler, c.id, c.default)
        finally:
            _GUARD.discard(key)
        # Local length resets keep the torso scale and update measured height;
        # resets that include Height restore the complete body.
        preserve = (field and field != "height") or (group and group != "Global")
        update_model(root.base_modeler, context, preserve_length_scale=bool(preserve))
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
                + " bones ready: R to pose within limits; G on root/core to move",
            )
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class BM_OT_pose_rig(bpy.types.Operator):
    bl_idname = "base_modeler.pose_rig"
    bl_label = "Pose Simple Rig"
    bl_description = "Enter Pose Mode: rotate joints; move the body with root or core"

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


class BM_OT_target_controls(bpy.types.Operator):
    bl_idname = "base_modeler.target_controls"
    bl_label = "Add Pose Targets"
    bl_description = (
        "Add movable hand and foot balls and a head gaze target to this rig"
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
        from .targets import install

        try:
            install(context, rig_for(model_for(context)))
        except (ValueError, RuntimeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        return {"FINISHED"}


class BM_OT_target_mode(bpy.types.Operator):
    bl_idname = "base_modeler.target_mode"
    bl_label = "Switch Target / FK"
    bl_description = (
        "Snap the target or joint controls to the current pose and switch modes"
    )
    bl_options = {"REGISTER", "UNDO"}
    channel: bpy.props.EnumProperty(
        items=[(n, n, "") for n in ("hand.L", "hand.R", "foot.L", "foot.R", "head")]
    )

    @classmethod
    def poll(cls, context):
        root = model_for(context)
        rig = rig_for(root) if root else None
        return (
            context.mode in ("OBJECT", "POSE")
            and rig is not None
            and bool(rig.get("base_modeler_target_controls"))
        )

    def execute(self, context):
        from .targets import set_mode

        rig = rig_for(model_for(context))
        set_mode(context, rig, self.channel, not rig["target_" + self.channel])
        return {"FINISHED"}


class BM_OT_select_target(bpy.types.Operator):
    bl_idname = "base_modeler.select_target"
    bl_label = "Select Pose Control"
    bl_description = "Select this target ball, or its joint when using FK"
    bl_options = {"UNDO"}
    channel: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return BM_OT_target_mode.poll(context)

    def execute(self, context):
        rig = rig_for(model_for(context))
        bpy.ops.base_modeler.pose_rig()
        name = ("target_" if rig.get("target_" + self.channel) else "") + self.channel
        for pb in rig.pose.bones:
            pb.select = False
        rig.data.bones[name].hide = False
        if hasattr(rig.pose.bones[name], "hide"):
            rig.pose.bones[name].hide = False
        rig.pose.bones[name].select = True
        rig.data.bones.active = rig.data.bones[name]
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
        forget(root)
        update_model(root.base_modeler, context)
        if root.as_pointer() in _ERRORS:
            self.report({"WARNING"}, _ERRORS[root.as_pointer()])
        return {"FINISHED"}
