"""Optional native target controls layered over the existing weighted FK rig."""

from math import cos, sin, tau, radians
import bpy
from .limits import rotation_limits

CHANNELS = ("hand.L", "hand.R", "foot.L", "foot.R", "head")
TAG = "base_modeler_target_controls"


def _shape(name):
    vertices, edges = [], []
    for axis in range(3):
        start = len(vertices)
        for i in range(32):
            p = [0.0, 0.0, 0.0]
            p[(axis + 1) % 3] = cos(tau * i / 32)
            p[(axis + 2) % 3] = sin(tau * i / 32)
            vertices.append(p)
            edges.append((start + i, start + (i + 1) % 32))
    start = len(vertices)
    vertices.extend(((0, 0, 0), (0, 1.6, 0), (0.2, 1.3, 0), (-0.2, 1.3, 0)))
    edges.extend(((start, start + 1), (start + 1, start + 2), (start + 1, start + 3)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, edges, [])
    ob = bpy.data.objects.new(name, mesh)
    ob[TAG] = True
    return ob


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
    ball = _shape("Base Modeler Target Ball")
    for ch in CHANNELS:
        rig["target_" + ch] = False
        pb = rig.pose.bones["target_" + ch]
        pb.custom_shape = ball
        pb.use_custom_shape_bone_size = False
        pb.custom_shape_scale_xyz = (0.035 * size,) * 3
        pb.lock_scale = (True,) * 3
        pb.rotation_mode = "XYZ"
        pb.lock_rotation = (ch == "head",) * 3
        pb.bone.color.palette = (
            "THEME04"
            if ch.endswith(".L")
            else "THEME01" if ch.endswith(".R") else "THEME03"
        )
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


def cleanup(rig):
    """Release only custom-shape data owned by this optional control layer."""
    shapes = {
        pb.custom_shape
        for pb in rig.pose.bones
        if pb.custom_shape and pb.custom_shape.get(TAG)
    }
    for pb in rig.pose.bones:
        if pb.custom_shape in shapes:
            pb.custom_shape = None
    for ob in shapes:
        if ob.users == 0:
            mesh = ob.data
            bpy.data.objects.remove(ob)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
