"""A native, directly poseable FK skeleton with fitted skin weights."""

import json
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .pose import CENTER_X, smooth
from .identity import region_name

TAG = "base_modeler_simple_rig"


def rig_for(root):
    return next(
        (ob for ob in root.children if ob.type == "ARMATURE" and ob.get(TAG)), None
    )


def skeleton():
    """Joint positions in the foundation's neutral T-pose, in meters."""
    bones = []

    def add(name, head, tail, parent=None, deform=True):
        bones.append(
            (
                name,
                np.array(head, np.float32),
                np.array(tail, np.float32),
                parent,
                deform,
            )
        )

    def center(y, z):
        return (CENTER_X, y, z)

    add("root", center(0, 0), center(0, 0.16), deform=False)
    add("pelvis", center(0.015, 0.89), center(0.005, 1.07), "root")
    add("spine", center(0.005, 1.07), center(0.005, 1.28), "pelvis")
    add("chest", center(0.005, 1.28), center(0.005, 1.445), "spine")
    add("neck", center(0.005, 1.445), center(0.008, 1.565), "chest")
    add("head", center(0.008, 1.565), center(0.008, 1.735), "neck")
    for side, sign in (("L", 1), ("R", -1)):

        def p(x, y, z):
            return (CENTER_X + sign * x, y, z)

        add("shoulder." + side, p(0.035, 0.005, 1.43), p(0.13, 0.005, 1.43), "chest")
        add(
            "upper_arm." + side,
            p(0.13, 0.005, 1.43),
            p(0.39, 0.005, 1.43),
            "shoulder." + side,
        )
        add(
            "forearm." + side,
            p(0.39, 0.005, 1.43),
            p(0.601, 0.005, 1.43),
            "upper_arm." + side,
        )
        add(
            "hand." + side,
            p(0.601, 0.005, 1.43),
            p(0.68, 0.005, 1.43),
            "forearm." + side,
        )
        add("thigh." + side, p(0.085, 0.015, 0.89), p(0.085, -0.005, 0.48), "pelvis")
        add(
            "shin." + side,
            p(0.085, -0.005, 0.48),
            p(0.085, 0.015, 0.09),
            "thigh." + side,
        )
        add(
            "foot." + side,
            p(0.085, 0.015, 0.09),
            p(0.085, -0.105, 0.025),
            "shin." + side,
        )
        add(
            "toe." + side,
            p(0.085, -0.105, 0.025),
            p(0.085, -0.175, 0.025),
            "foot." + side,
        )
    return bones


def fit_skeleton(reference, current, skin_indices):
    """Carry joint centers through nearby skin displacements, keeping chains joined."""
    source = reference[skin_indices]
    delta = current[skin_indices] - source
    memo = {}

    def fit(point):
        key = tuple(point)
        if key not in memo:
            d = np.linalg.norm(source - point, axis=1)
            take = np.argpartition(d, min(95, len(d) - 1))[:96]
            weights = np.exp(-(((d[take] - d[take].min()) / 0.025) ** 2))
            memo[key] = (
                point + np.sum(delta[take] * weights[:, None], axis=0) / weights.sum()
            )
        return memo[key]

    return [
        (name, fit(head), fit(tail), parent, deform)
        for name, head, tail, parent, deform in skeleton()
    ]


def skin_weights(points, arm_ownership, names):
    """Continuous anatomical partitions; every row is a convex combination."""
    count = len(points)
    w = np.zeros((count, len(names)), np.float32)
    lookup = {n: i for i, n in enumerate(names)}
    x = points[:, 0] - CENTER_X
    y = points[:, 1]
    z = points[:, 2]
    ax = abs(x)
    # Interpolate the torso through the spine, then give the complete face and
    # cranium to the head. The matching neck boundary receives identical weights.
    levels = np.array([0.98, 1.12, 1.31, 1.465, 1.565])
    torso = ("pelvis", "spine", "chest", "neck", "head")
    for i, name in enumerate(torso):
        low = np.ones(count) if i == 0 else smooth(levels[i - 1], levels[i], z)
        high = (
            np.ones(count)
            if i == len(torso) - 1
            else 1 - smooth(levels[i], levels[i + 1], z)
        )
        w[:, lookup[name]] = low * high
    # The medial crotch blends into the pelvis only near the hip. Applying
    # this width gate down the entire leg pins inner knees, ankles and toes
    # to the pelvis and tears their silhouette when the thigh rotates.
    medial_offset = 0.08 * (1 - smooth(0.015, 0.065, ax))
    legs = 1 - smooth(0.82 - medial_offset, 0.98 - medial_offset, z)
    arms = arm_ownership * smooth(1.25, 1.36, z)
    w *= ((1 - arms) * (1 - legs))[:, None]
    for side, sign in (("L", 1), ("R", -1)):
        side_mask = (x * sign >= 0).astype(np.float32)
        # A short clavicle transition seats the shoulder on the chest. Each
        # limb then blends locally around its actual elbow/wrist or knee/ankle.
        clavicle = 1 - smooth(0.12, 0.19, ax)
        fore = smooth(0.35, 0.43, ax)
        hand = smooth(0.565, 0.625, ax)
        a = arms * side_mask
        for name, value in (
            ("shoulder", clavicle),
            ("upper_arm", (1 - clavicle) * (1 - fore)),
            ("forearm", fore * (1 - hand)),
            ("hand", hand),
        ):
            w[:, lookup[name + "." + side]] += a * value
        lower = 1 - smooth(0.43, 0.54, z)
        foot = 1 - smooth(0.065, 0.135, z)
        toe = 1 - smooth(-0.155, -0.09, y)
        # A narrow bilateral transition keeps the crotch continuous under
        # unilateral hip motion and shares exact centerline points equally.
        leg_side = smooth(-0.012, 0.012, x * sign)
        a = legs * leg_side * (1 - arms)
        for name, value in (
            ("thigh", 1 - lower),
            ("shin", lower * (1 - foot)),
            ("foot", foot * (1 - toe)),
            ("toe", foot * toe),
        ):
            w[:, lookup[name + "." + side]] += a * value
    w /= np.maximum(w.sum(1)[:, None], 1e-20)
    return w


def bind_weights(cache, reference, names):
    """Transfer the skin's binding to muscle layers so close surfaces move together."""
    skin, start, end = next(
        s for s in cache["slices"] if region_name(s[0]) == "Body_Surface"
    )
    skin.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in skin.data.loop_triangles])
    surface = reference[start:end]
    weights = skin_weights(reference, cache["fields"]["arm_weights"], names)
    bvh = BVHTree.FromPolygons(surface, tri, all_triangles=True)
    for ob, a, b in cache["slices"]:
        if ob == skin or region_name(ob) == "Head":
            continue
        for i in range(a, b):
            co, _, face, _ = bvh.find_nearest(reference[i])
            ids = tri[face]
            pa, pb, pc = surface[ids]
            u = pb - pa
            v = pc - pa
            r = np.asarray(co) - pa
            uu = u @ u
            uv = u @ v
            vv = v @ v
            den = uu * vv - uv * uv
            if den < 1e-20:
                bc = np.array([1.0, 0.0, 0.0])
            else:
                s = (r @ u * vv - r @ v * uv) / den
                t = (r @ v * uu - r @ u * uv) / den
                bc = np.maximum([1 - s - t, s, t], 0.0)
                bc /= bc.sum()
            weights[i] = bc @ weights[start + ids]
    # The vasti originate on the femur, not the pelvis. Proximal caps must
    # follow the thigh; transferring the skin's hip blend folds these closed
    # volumes into themselves during sitting. Retain their distal knee blend.
    for ob, a, b in cache["slices"]:
        if region_name(ob) not in ("Vastus_lateralis", "Vastus_medialis"):
            continue
        for side, sign in (("L", 1), ("R", -1)):
            ids = np.arange(a, b)[(reference[a:b, 0] - CENTER_X) * sign >= 0]
            pelvis = names.index("pelvis")
            thigh = names.index("thigh." + side)
            weights[ids, thigh] += weights[ids, pelvis]
            weights[ids, pelvis] = 0.0
    # Nearest skin correspondences can switch abruptly across a closed muscle
    # wall. Fair that transferred field along its own edges before binding;
    # this reduces sharp weight steps without a live modifier or pose handler.
    for ob, a, b in cache["slices"]:
        if region_name(ob) not in ("Gluteus_maximus", "Medial_hamstring_group"):
            continue
        edge = np.array([e.vertices[:] for e in ob.data.edges], dtype=np.int32)
        if not len(edge):
            continue
        src = np.concatenate((edge[:, 0], edge[:, 1]))
        dst = np.concatenate((edge[:, 1], edge[:, 0]))
        degree = np.bincount(src, minlength=b - a).astype(np.float32)
        field = weights[a:b].copy()
        for _ in range(12):
            totals = np.zeros_like(field)
            np.add.at(totals, src, field[dst])
            field = 0.5 * field + 0.5 * totals / np.maximum(degree[:, None], 1.0)
        weights[a:b] = field
    # Quantize once to upload equal weights in batches, with an exact residual
    # assigned to the largest influence. This keeps generation fast without
    # installing a live solver or handlers for posing.
    ticks = np.rint(weights * 1000).astype(np.int32)
    ticks[np.arange(len(ticks)), np.argmax(ticks, axis=1)] += 1000 - ticks.sum(1)
    return ticks


def generate(context, root, cache, reference):
    if rig_for(root):
        raise ValueError("This model already has a simple rig.")
    names = [b[0] for b in skeleton() if b[4]]
    for ob, _, _ in cache["slices"]:
        if any(ob.vertex_groups.get(name) for name in names):
            raise ValueError(
                "An existing vertex group uses a rig bone name: " + ob.name
            )
        if any(m.type == "ARMATURE" for m in ob.modifiers):
            raise ValueError("This model already has an armature modifier.")
    current = np.empty_like(reference)
    for ob, a, b in cache["slices"]:
        ob.data.vertices.foreach_get("co", current[a:b].ravel())
    skin_indices = np.concatenate(
        [
            np.arange(a, b)
            for ob, a, b in cache["slices"]
            if region_name(ob) in ("Body_Surface", "Head")
        ]
    )
    bones = fit_skeleton(reference, current, skin_indices)
    weights = bind_weights(cache, reference, names)
    data = bpy.data.armatures.new("Base Modeler Simple Rig")
    rig = bpy.data.objects.new("Base Modeler Simple Rig", data)
    root.users_collection[0].objects.link(rig)
    rig.parent = root
    rig[TAG] = 1
    rig["base_modeler_binding_schema"] = 2
    rig["base_modeler_group_names"] = json.dumps(names)
    rig.show_in_front = True
    data.display_type = "OCTAHEDRAL"
    data.pose_position = "POSE"
    try:
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        for name, head, tail, parent, deform in bones:
            bone = data.edit_bones.new(name)
            bone.head = head
            bone.tail = tail
            bone.use_deform = deform
            if parent:
                bone.parent = data.edit_bones[parent]
            # Disconnected parenting allows both G and R in Pose Mode. Child
            # joints still coincide at rest and inherit their parent's motion.
            bone.use_connect = False
            axis = (
                Vector((0, 0, 1))
                if name.startswith(
                    ("shoulder", "upper_arm", "forearm", "hand", "foot", "toe")
                )
                else Vector((0, -1, 0))
            )
            bone.align_roll(axis)
        bpy.ops.object.mode_set(mode="OBJECT")
        for pb in rig.pose.bones:
            pb.rotation_mode = "XYZ"
            pb.bone.color.palette = (
                "THEME04"
                if pb.name.endswith(".L")
                else "THEME01" if pb.name.endswith(".R") else "THEME03"
            )
        for ob, a, b in cache["slices"]:
            for j, name in enumerate(names):
                column = weights[a:b, j]
                positive = column > 0
                if not positive.any():
                    continue
                group = ob.vertex_groups.new(name=name)
                for value in np.unique(column[positive]):
                    group.add(
                        np.flatnonzero(column == value).tolist(),
                        float(value) / 1000.0,
                        "REPLACE",
                    )
            modifier = ob.modifiers.new("Base Modeler Simple Rig", "ARMATURE")
            modifier.object = rig
            modifier.use_deform_preserve_volume = True
        bpy.ops.object.mode_set(mode="POSE")
        return rig
    except Exception:
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        remove(context, root)
        raise


def remove(context, root):
    rig = rig_for(root)
    if rig is None:
        return
    try:
        names = json.loads(rig["base_modeler_group_names"])
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise ValueError("Invalid bone names")
    except (KeyError, ValueError, TypeError):
        names = [bone.name for bone in rig.data.bones if bone.use_deform]
    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for ob in root.children_recursive:
        if ob.type != "MESH":
            continue
        for modifier in list(ob.modifiers):
            if modifier.type == "ARMATURE" and modifier.object == rig:
                ob.modifiers.remove(modifier)
        for name in names:
            group = ob.vertex_groups.get(name)
            if group:
                ob.vertex_groups.remove(group)
    data = rig.data
    bpy.data.objects.remove(rig, do_unlink=True)
    if data.users == 0:
        bpy.data.armatures.remove(data)
    root.select_set(True)
    context.view_layer.objects.active = root
