"""Optional native target controls layered over the existing weighted FK rig."""

from math import radians
import bpy
from .limits import rotation_limits
from . import widgets

CHANNELS = ("hand.L", "hand.R", "foot.L", "foot.R", "head")
TAG = "base_modeler_target_controls"
SOLVER_SCHEMA = 2
LIMBS = {
    "hand": ("upper_arm.", "forearm.", "hand."),
    "foot": ("thigh.", "shin.", "foot."),
}


def tune_solver(rig):
    """Keep dragged limbs continuous; changes no bones, weights or controls.

    A limb chain has redundant twist, and an endpoint orientation goal often
    conflicts with the wrist/ankle limits. Untuned, the solver hops between
    equally good twists and flips the knee or elbow as a ball moves.
    """
    for side in "LR":
        for kind, chain in LIMBS.items():
            upper, middle, end = (rig.pose.bones[prefix + side] for prefix in chain)
            # Prefer the existing twist; reach with the shoulder/hip and elbow.
            upper.ik_stiffness_y = middle.ik_stiffness_y = 0.9
            # The wrist/ankle orients the endpoint but should not do the reaching:
            # pinned against its limit it hands sudden corrections to the twists.
            end.ik_stiffness_x = end.ik_stiffness_z = 0.9
            if kind == "foot":
                # The knee is a hinge for the solver; its small FK play remains.
                middle.lock_ik_y = middle.lock_ik_z = True
            # Reach the ball first and orient as far as the joints allow.
            constraint = end.constraints.get("Target limb IK")
            if constraint:
                constraint.orient_weight = 0.1
    rig["base_modeler_target_solver"] = SOLVER_SCHEMA


def style_targets(rig):
    """Solid balls, larger for the head, replacing any earlier wire widgets."""
    size = rig.get("base_modeler_target_scale", 1.0)
    old = {rig.pose.bones["target_" + ch].custom_shape for ch in CHANNELS}
    shape = widgets.ball("Base Modeler Target Ball")
    for ch in CHANNELS:
        pb = rig.pose.bones["target_" + ch]
        radius = {"head": 0.05, "hand": 0.032}.get(ch[:4], 0.04) * size
        widgets.assign(pb, shape, (radius,) * 3)
        pb.bone.color.palette = (
            "THEME04"
            if ch.endswith(".L")
            else "THEME01" if ch.endswith(".R") else "THEME06"
        )
    for ob in old:
        if ob is not None and ob.users == 0 and any(map(ob.get, widgets.LEGACY_TAGS)):
            mesh = ob.data
            bpy.data.objects.remove(ob)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)


def upgrade(rig):
    """Bring targets saved by an earlier release to the current behaviour."""
    if rig.get("base_modeler_target_solver", 1) < SOLVER_SCHEMA:
        tune_solver(rig)
        style_targets(rig)


def _driver(constraint, rig, channel):
    f = constraint.driver_add("influence")
    d = f.driver
    d.type = "AVERAGE"
    var = d.variables.new()
    var.name = "enabled"
    var.type = "SINGLE_PROP"
    var.targets[0].id = rig
    var.targets[0].data_path = f'["target_{channel}"]'


def install(context, rig):
    """Add controls once, without rebinding or replacing the user's mesh."""
    if rig.get(TAG):
        return
    if any("target_" + ch in rig.data.bones for ch in CHANNELS):
        raise ValueError("A target bone name is already in use on this rig.")
    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    context.view_layer.objects.active = rig
    # Capture the current pose before entering Edit Mode.
    matrices = {ch: rig.pose.bones[ch].matrix.copy() for ch in CHANNELS}
    positions = {ch: rig.pose.bones[ch].tail.copy() for ch in CHANNELS}
    size = (
        rig.data.bones["head"].head_local - rig.data.bones["foot.L"].head_local
    ).length / 1.5
    rig["base_modeler_target_scale"] = size
    bpy.ops.object.mode_set(mode="EDIT")
    collection = rig.data.collections.new("Pose Targets")
    for ch in CHANNELS:
        b = rig.data.edit_bones.new("target_" + ch)
        b.matrix = matrices[ch]
        b.length = 0.06 * size
        b.head = (
            matrices[ch].translation + matrices[ch].col[2].xyz * 0.45 * size
            if ch == "head"
            else positions[ch]
        )
        b.tail = b.head + matrices[ch].col[1].xyz * 0.06 * size
        b.parent = rig.data.edit_bones["root"]
        b.use_deform = False
        collection.assign(b)
    bpy.ops.object.mode_set(mode="OBJECT")
    style_targets(rig)
    for ch in CHANNELS:
        rig["target_" + ch] = False
        pb = rig.pose.bones["target_" + ch]
        pb.lock_scale = (True,) * 3
        pb.rotation_mode = "XYZ"
        pb.lock_rotation = (ch == "head",) * 3
        if ch == "head":
            c = rig.pose.bones["head"].constraints.new("DAMPED_TRACK")
            c.name = "Target gaze"
            c.target = rig
            c.subtarget = "target_head"
            c.track_axis = "TRACK_Z"
            rig.pose.bones["head"].constraints.move(
                len(rig.pose.bones["head"].constraints) - 1, 0
            )
        else:
            arm = ch.startswith("hand")
            chain = (
                ("upper_arm.", "forearm.", "hand.")
                if arm
                else ("thigh.", "shin.", "foot.")
            )
            for prefix in chain:
                joint = rig.pose.bones[prefix + ch[-1]]
                bounds = rotation_limits(joint.name)
                joint.ik_stretch = 0
                for axis, (lo, hi) in zip("xyz", bounds):
                    setattr(joint, "use_ik_limit_" + axis, True)
                    setattr(joint, "ik_min_" + axis, radians(lo))
                    setattr(joint, "ik_max_" + axis, radians(hi))
                    setattr(joint, "lock_ik_" + axis, lo == hi)
            c = rig.pose.bones[ch].constraints.new("IK")
            c.name = "Target limb IK"
            c.target = rig
            c.subtarget = "target_" + ch
            c.chain_count = 3
            c.use_tail = True
            c.use_stretch = False
            c.iterations = 512
            c.use_rotation = True
            c.weight = 1.0
            c.orient_weight = 1.0
        _driver(c, rig, ch)
    tune_solver(rig)
    rig[TAG] = 1
    for ch in CHANNELS:
        set_mode(context, rig, ch, True)
    bpy.ops.object.mode_set(mode="POSE")
    for pb in rig.pose.bones:
        pb.select = False
    rig.pose.bones["target_hand.L"].select = True
    rig.data.bones.active = rig.data.bones["target_hand.L"]


def set_mode(context, rig, channel, enabled):
    """Snap on entry so switching modes preserves the current end-effector goal."""
    context.view_layer.update()
    ch = channel
    if ch not in CHANNELS:
        raise ValueError("Unknown pose target.")
    part = rig.pose.bones[ch]
    matrix = part.matrix.copy()
    if enabled:
        control = rig.pose.bones["target_" + ch]
        if ch == "head":
            matrix.translation = part.head + matrix.col[2].xyz * 0.45 * rig.get(
                "base_modeler_target_scale", 1.0
            )
        else:
            matrix.translation = part.tail
        control.matrix = matrix
    else:
        chain = (
            [ch]
            if ch == "head"
            else [
                prefix + ch[-1]
                for prefix in (
                    ("upper_arm.", "forearm.", "hand.")
                    if ch.startswith("hand")
                    else ("thigh.", "shin.", "foot.")
                )
            ]
        )
        saved = {name: rig.pose.bones[name].matrix.copy() for name in chain}
    if enabled and ch.startswith("foot"):
        knee = rig.pose.bones["shin." + ch[-1]]
        if abs(knee.rotation_euler.x) < 0.08:
            # Bias the nearly straight chain toward knee flexion.
            knee.rotation_euler.x = -0.35
    rig["target_" + ch] = bool(enabled)
    rig.update_tag()
    context.view_layer.update()
    if not enabled:
        for name in chain:
            rig.pose.bones[name].matrix = saved[name]
            context.view_layer.update()
    # Show the controls appropriate to the chosen posing method.
    controlled = (
        [ch]
        if ch == "head"
        else [
            prefix + ch[-1]
            for prefix in (
                ("upper_arm.", "forearm.", "hand.")
                if ch.startswith("hand")
                else ("thigh.", "shin.", "foot.")
            )
        ]
    )
    for name in controlled:
        rig.data.bones[name].hide = enabled
        if hasattr(rig.pose.bones[name], "hide"):
            rig.pose.bones[name].hide = enabled
    rig.data.bones["target_" + ch].hide = not enabled
    if hasattr(rig.pose.bones["target_" + ch], "hide"):
        rig.pose.bones["target_" + ch].hide = not enabled
    rig.update_tag()
    context.view_layer.update()
