"""Artist-facing sidebar panels. UI code does not mutate model data."""

import textwrap
import bpy
from .controls import GROUPS, CONTROLS
from .model import model_for, _ERRORS
from .rig import rig_for, BINDING_SCHEMA, LIMITS_SCHEMA


class BM_PT_actions(bpy.types.Panel):
    bl_idname = "BM_PT_actions"
    bl_label = "Model Actions"
    bl_category = "Base Modeler"
    bl_options = {"HIDE_HEADER"}
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 0

    def draw(self, context):
        layout = self.layout.box()
        root = model_for(context)
        layout.operator("base_modeler.create", icon="ADD")
        if root is None:
            layout.label(text="Create or select a base model.")
            return
        rig = rig_for(root)
        if rig:
            layout.operator(
                "base_modeler.pose_rig", text="Pose Simple Rig", icon="POSE_HLT"
            )
            layout.operator(
                "base_modeler.remove_rig", text="Remove Simple Rig", icon="X"
            )
            layout.label(text="Remove rig to edit body proportions.")
            schema = rig.get("base_modeler_binding_schema", 1)
            if rig.get("base_modeler_target_controls"):
                layout.label(text="Balls: G to move, R to orient.")
                for ch, label in (
                    ("head", "Head"),
                    ("hand.L", "Left hand"),
                    ("hand.R", "Right hand"),
                    ("foot.L", "Left foot"),
                    ("foot.R", "Right foot"),
                ):
                    row = layout.row(align=True)
                    select = row.operator(
                        "base_modeler.select_target",
                        text=label,
                        icon="RESTRICT_SELECT_OFF",
                    )
                    select.channel = ch
                    active = bool(rig.get("target_" + ch))
                    toggle = row.operator(
                        "base_modeler.target_mode",
                        text=("Look" if ch == "head" else "IK") if active else "FK",
                        depress=active,
                    )
                    toggle.channel = ch
                layout.label(text="Head ball: move to aim the gaze.")
            else:
                layout.operator("base_modeler.target_controls", icon="SPHERE")
            if schema >= LIMITS_SCHEMA and not rig.get("base_modeler_target_controls"):
                layout.label(text="R: pose joints within limits.")
                layout.label(text="G: move root or core only.")
            if schema < BINDING_SCHEMA:
                layout.label(
                    text="Remove and regenerate to update binding.", icon="INFO"
                )
        else:
            row = layout.row()
            row.enabled = context.mode == "OBJECT"
            row.operator(
                "base_modeler.generate_rig",
                text="Generate Simple Rig",
                icon="ARMATURE_DATA",
            )


class BM_PT_body(bpy.types.Panel):
    bl_idname = "BM_PT_body"
    bl_label = "Controls"
    bl_category = "Base Modeler"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return model_for(context) is not None

    def draw(self, context):
        # A normal panel header retains Blender's standard panel backdrop.
        # Keep the headerless model actions in a separate box above this panel.
        layout = self.layout
        root = model_for(context)
        rig = rig_for(root)
        limit_note = root.get("base_modeler_height_limit", "")
        if limit_note:
            for line in textwrap.wrap(limit_note, 38):
                layout.label(text=line)
        error = _ERRORS.get(root.as_pointer())
        if error:
            box = layout.box()
            box.alert = True
            for line in textwrap.wrap(error, 38):
                box.label(text=line)
        col = layout.column()
        col.enabled = context.mode == "OBJECT" and rig is None
        if context.mode != "OBJECT" and rig is None:
            layout.label(text="Use Object Mode to edit the body.", icon="INFO")
        for group in GROUPS:
            header, body = col.panel("base_modeler_group_" + group, default_closed=True)
            header.label(text=group)
            reset = header.operator("base_modeler.reset", text="", icon="LOOP_BACK")
            reset.group = group
            reset.field = ""
            if body is not None:
                for c in CONTROLS:
                    if c.group != group:
                        continue
                    row = body.row(align=True)
                    row.prop(root.base_modeler, c.id, slider=True)
                    reset = row.operator(
                        "base_modeler.reset", text="", icon="LOOP_BACK"
                    )
                    reset.field = c.id
                    reset.group = ""
        reset = col.operator(
            "base_modeler.reset", text="Reset All Body Controls", icon="LOOP_BACK"
        )
        reset.group = ""
        reset.field = ""
