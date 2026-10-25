"""A native, directly poseable FK skeleton with fitted skin weights."""

import json
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .pose import CENTER_X, smooth
from .identity import region_name
from .fitting import SkinSections
from .digits import chains, bind_digits, bind_nails, joint_blend
from .limits import install_limits

TAG = "base_modeler_simple_rig"
BINDING_SCHEMA = 7
# The first binding schema with native joint limits and root/core-only moves.
LIMITS_SCHEMA = 7
WEIGHT_STEPS = 32768


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
    add("core", center(0.015, 0.97), center(0.005, 1.12), "root", deform=False)
    add("pelvis", center(0.015, 0.97), center(0.005, 1.12), "root")
    add("spine", center(0.005, 1.12), center(0.005, 1.28), "core")
    add("chest", center(0.005, 1.28), center(0.005, 1.445), "spine")
    add("neck", center(0.005, 1.445), center(0.008, 1.563), "chest")
    add("head", center(0.008, 1.563), center(0.008, 1.733), "neck")
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
            p(0.55, -0.017, 1.436),
            "upper_arm." + side,
        )
        add(
            "hand." + side,
            p(0.55, -0.017, 1.436),
            p(0.65, -0.05, 1.42),
            "forearm." + side,
        )
        add(
            "forearm_twist." + side,
            p(0.39, 0.005, 1.43),
            p(0.55, -0.017, 1.436),
            "forearm." + side,
        )
        add("thigh." + side, p(0.085, 0.015, 0.97), p(0.07, -0.01, 0.56), "pelvis")
        add(
            "shin." + side,
            p(0.07, -0.01, 0.56),
            p(0.06, 0.03, 0.09),
            "thigh." + side,
        )
        add(
            "foot." + side,
            p(0.06, 0.03, 0.09),
            p(0.069, -0.08, 0.012),
            "shin." + side,
        )
        add(
            "toe." + side,
            p(0.069, -0.08, 0.012),
            p(0.06, -0.12, 0.004),
            "foot." + side,
        )
        for kind, _, joints, names in chains(side):
            parent = ("hand." if kind == "finger" else "toe.") + side
            for i, name in enumerate(names):
                add(name, joints[i], joints[i + 1], parent)
                parent = name
    return bones


def fit_skeleton(reference, current, skin_indices, skin_triangles=None):
    """Carry joint centers through nearby skin displacements, keeping chains joined."""
    source = reference[skin_indices]
    delta = current[skin_indices] - source
    memo = {}

    sections = (
        SkinSections(source, current[skin_indices], skin_triangles)
        if skin_triangles is not None
        else None
    )
    stations = {
        round(CENTER_X + sign * x, 6) for sign in (-1, 1) for x in (0.39, 0.55, 0.65)
    }

    def fit(point, limb=False, digit=None):
        key = tuple(point)
        if key not in memo:
            if sections is not None and limb:
                x, y, z = point
                if digit is not None:
                    axis = 0 if digit == "finger" else 1
                    memo[key] = sections.center(
                        axis,
                        point[axis],
                        point,
                        fixed_axis=1 - axis,
                        depth_fraction=0.5,
                    )
                elif round(float(x), 6) in stations:
                    memo[key] = sections.center(0, x, point)
                elif abs(float(z) - 0.56) < 1e-6 or abs(float(z) - 0.09) < 1e-6:
                    memo[key] = sections.center(2, z, point)
                elif abs(float(y) + 0.08) < 1e-6 or abs(float(y) + 0.12) < 1e-6:
                    memo[key] = sections.center(
                        1,
                        y,
                        point,
                        fixed_axis=0 if abs(float(y) + 0.08) < 1e-6 else None,
                    )
                if key in memo:
                    return memo[key]
            d = np.linalg.norm(source - point, axis=1)
            take = np.argpartition(d, min(95, len(d) - 1))[:96]
            weights = np.exp(-(((d[take] - d[take].min()) / 0.025) ** 2))
            memo[key] = (
                point + np.sum(delta[take] * weights[:, None], axis=0) / weights.sum()
            )
        return memo[key]

    fitted = []
    for name, head, tail, parent, deform in skeleton():
        digit = (
            "finger"
            if name.startswith("finger_")
            else "toe" if name.startswith("toe_") else None
        )
        fitted.append(
            (
                name,
                fit(head, "." in name, digit),
                fit(tail, "." in name, digit),
                parent,
                deform,
            )
        )
    return fitted


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
    # The iliac crest and sacrum belong to the pelvis. Begin the lumbar
    # blend above them, spreading abdominal motion through the waist rather
    # than dragging the gluteal origins up with the lower spine.
    rear = smooth(-0.025, 0.045, y)
    levels = (1.035 + 0.045 * rear, 1.235, 1.34, 1.465, 1.565)
    torso = ("pelvis", "spine", "chest", "neck", "head")
    for i, name in enumerate(torso):
        low = np.ones(count) if i == 0 else smooth(levels[i - 1], levels[i], z)
        high = (
            np.ones(count)
            if i == len(torso) - 1
            else 1 - smooth(levels[i], levels[i + 1], z)
        )
        w[:, lookup[name]] = low * high
    face = (1 - smooth(-0.060, -0.020, y)) * smooth(1.495, 1.520, z)
    head = np.maximum(smooth(1.515, 1.565, z), face)
    # Retain the chest/neck transition, replacing only the neck/head split.
    neck_head = w[:, lookup["neck"]] + w[:, lookup["head"]]
    w[:, lookup["head"]] = neck_head * head
    w[:, lookup["neck"]] = neck_head - w[:, lookup["head"]]
    # The medial crotch blends into the pelvis only near the hip. Applying
    # this width gate down the entire leg pins inner knees, ankles and toes
    # to the pelvis and tears their silhouette when the thigh rotates.
    medial_offset = 0.08 * (1 - smooth(0.015, 0.065, ax))
    front_hip = 1 - smooth(-0.035, 0.045, y)
    # The gluteal/hamstring soft tissue spans a longer posterior attachment
    # than the anterior hip crease. Spread that bend over 22 cm instead of
    # concentrating seated-pose strain in a short band under the buttock.
    legs = 1 - smooth(
        0.80 + 0.075 * front_hip - medial_offset,
        1.02 + 0.025 * front_hip - medial_offset,
        z,
    )
    arms = arm_ownership * smooth(1.25, 1.36, z)
    w *= ((1 - arms) * (1 - legs))[:, None]
    for side, sign in (("L", 1), ("R", -1)):
        side_mask = (x * sign >= 0).astype(np.float32)
        # A short clavicle transition seats the shoulder on the chest. Each
        # limb then blends locally around its actual elbow/wrist or knee/ankle.
        clavicle = 1 - smooth(0.12, 0.19, ax)
        fore = joint_blend(0.35, 0.43, ax)
        hand = smooth(0.53, 0.575, ax)
        a = arms * side_mask
        for name, value in (
            ("shoulder", clavicle),
            ("upper_arm", (1 - clavicle) * (1 - fore)),
            ("forearm", fore * (1 - hand)),
            ("hand", hand),
        ):
            w[:, lookup[name + "." + side]] += a * value
        lower = 1 - joint_blend(0.51, 0.61, z)
        foot = 1 - smooth(0.065, 0.135, z)
        toe = 1 - smooth(-0.095, -0.065, y)
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


def _barycentric(points, corners):
    """Clamped barycentric coordinates of points projected onto their triangles."""
    pa = corners[:, 0]
    u = corners[:, 1] - pa
    v = corners[:, 2] - pa
    r = points - pa
    uu = np.einsum("ij,ij->i", u, u)
    uv = np.einsum("ij,ij->i", u, v)
    vv = np.einsum("ij,ij->i", v, v)
    ru = np.einsum("ij,ij->i", r, u)
    rv = np.einsum("ij,ij->i", r, v)
    den = uu * vv - uv * uv
    degenerate = den < 1e-20
    safe = np.where(degenerate, 1.0, den)
    s = (ru * vv - rv * uv) / safe
    t = (rv * uu - ru * uv) / safe
    bc = np.maximum(np.column_stack((1 - s - t, s, t)), 0.0)
    bc /= np.maximum(bc.sum(1)[:, None], 1e-20)
    bc[degenerate] = (1.0, 0.0, 0.0)
    return bc


def bind_weights(cache, reference, names, bones):
    """Transfer the skin's binding to muscle layers so close surfaces move together."""
    skin, start, end = next(
        s for s in cache["slices"] if region_name(s[0]) == "Body_Surface"
    )
    skin.data.calc_loop_triangles()
    tri = np.array([t.vertices[:] for t in skin.data.loop_triangles])
    surface = reference[start:end]
    weights = skin_weights(reference, cache["fields"]["arm_weights"], names)
    edges = np.array([e.vertices[:] for e in skin.data.edges], dtype=np.int32)
    weights[start:end] = bind_digits(surface, edges, bones, names, weights[start:end])
    # Keep elbow flexion in both influences but distribute axial rotation along
    # the forearm. The hidden helper cancels 75% of its parent's local Y twist.
    # Transfer these skin weights to the muscle shells below, never paint each
    # overlaid surface independently at a potentially different joint station.
    ax = abs(reference[:, 0] - CENTER_X)
    proximal_twist = 1 - smooth(0.40, 0.55, ax)
    for side in ("L", "R"):
        fore = names.index("forearm." + side)
        helper = names.index("forearm_twist." + side)
        weights[:, helper] = weights[:, fore] * proximal_twist
        weights[:, fore] -= weights[:, helper]
    bvh = BVHTree.FromPolygons(surface, tri, all_triangles=True)
    for ob, a, b in cache["slices"]:
        # The broad abdominal sheets need a coherent lumbar field through
        # their thickness. Nearest skin samples can jump along their raised
        # rims and create local stretching even when the skin blend is smooth.
        if (
            ob == skin
            or region_name(ob)
            in (
                "Head",
                "Rectus_abdominis",
                "External_oblique",
            )
            or a == b
        ):
            continue
        nearest = [bvh.find_nearest(point) for point in reference[a:b]]
        ids = tri[[hit[2] for hit in nearest]]
        hits = np.array([tuple(hit[0]) for hit in nearest], dtype=np.float64)
        bc = _barycentric(hits, surface[ids])
        weights[a:b] = np.einsum("ij,ijk->ik", bc, weights[start + ids])
    # Gluteal muscles originate on the pelvis/sacrum, not the lumbar spine.
    # Keep their hip/thigh blend, but remove torso influence transferred from
    # nearby lower-back skin at their thin upper rims.
    for ob, a, b in cache["slices"]:
        if region_name(ob) in ("Gluteus_maximus", "Gluteus_medius"):
            pelvis = names.index("pelvis")
            for name in ("spine", "chest", "neck", "head"):
                column = names.index(name)
                weights[a:b, pelvis] += weights[a:b, column]
                weights[a:b, column] = 0.0
    # Nails are rigid plates: bind each connected nail to its distal phalanx,
    # rather than interpolating across an interphalangeal weight transition.
    for ob, a, b in cache["slices"]:
        kind = {"Fingernails": "finger", "Toenails": "toe"}.get(region_name(ob))
        if kind:
            edges = np.array([e.vertices[:] for e in ob.data.edges], dtype=np.int32)
            bind_nails(reference[a:b], edges, bones, names, weights[a:b], kind)
    # The vasti originate on the femur, not the pelvis. Proximal caps must
    # follow the thigh; transferring the skin's hip blend folds these closed
    # volumes into themselves during sitting. Retain their distal knee blend.
    for ob, a, b in cache["slices"]:
        if region_name(ob) not in (
            "Vastus_lateralis",
            "Vastus_medialis",
            "Rectus_femoris",
        ):
            continue
        for side, sign in (("L", 1), ("R", -1)):
            ids = np.arange(a, b)[(reference[a:b, 0] - CENTER_X) * sign >= 0]
            pelvis = names.index("pelvis")
            thigh = names.index("thigh." + side)
            # The rectus retains a small proximal pelvic attachment. Its
            # thick cap must travel mostly with the femur to avoid a folded
            # lip when lifting the knee, while the vasti attach to the femur.
            retained = (
                0.15 * smooth(0.93, 1.02, reference[ids, 2])
                if region_name(ob) == "Rectus_femoris"
                else 0.0
            )
            proximal = weights[ids, pelvis].copy()
            if region_name(ob) == "Rectus_femoris":
                spine = names.index("spine")
                proximal += weights[ids, spine]
                weights[ids, spine] = 0.0
            weights[ids, thigh] += proximal * (1 - retained)
            weights[ids, pelvis] = proximal * retained
    # Nearest skin correspondences can switch abruptly across a closed muscle
    # wall. Fair that transferred field along its own edges before binding;
    # this reduces sharp weight steps without a live modifier or pose handler.
    for ob, a, b in cache["slices"]:
        if region_name(ob) not in (
            "Gluteus_maximus",
            "Medial_hamstring_group",
            "Deltoid",
            "Biceps_brachii",
            "Triceps_brachii",
            "Pectoralis_major",
            "Latissimus_dorsi",
            "Forearm_flexor_group",
            "Forearm_extensor_group",
            "Brachioradialis",
        ):
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
    # Binary fractions sum exactly in Blender's float storage. The finer
    # resolution avoids visible weight stair-steps on dense finger topology.
    ticks = np.rint(weights * WEIGHT_STEPS).astype(np.int32)
    ticks[np.arange(len(ticks)), np.argmax(ticks, axis=1)] += WEIGHT_STEPS - ticks.sum(
        1
    )
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
    skin = next(ob for ob, a, b in cache["slices"] if region_name(ob) == "Body_Surface")
    skin.data.calc_loop_triangles()
    triangles = np.array(
        [triangle.vertices[:] for triangle in skin.data.loop_triangles]
    )
    bones = fit_skeleton(reference, current, skin_indices, triangles)
    neutral_bones = (
        bones
        if np.array_equal(reference, current)
        else fit_skeleton(reference, reference, skin_indices, triangles)
    )
    weights = bind_weights(cache, reference, names, neutral_bones)
    skin_start, skin_end = next((a, b) for ob, a, b in cache["slices"] if ob == skin)
    fitted_surface = BVHTree.FromPolygons(
        current[skin_start:skin_end], triangles, all_triangles=True
    )
    data = bpy.data.armatures.new("Base Modeler Simple Rig")
    rig = None
    try:
        rig = bpy.data.objects.new("Base Modeler Simple Rig", data)
        collection = (
            root.users_collection[0]
            if root.users_collection
            else context.scene.collection
        )
        collection.objects.link(rig)
        rig.parent = root
        rig[TAG] = 1
        rig["base_modeler_binding_schema"] = BINDING_SCHEMA
        rig["base_modeler_group_names"] = json.dumps(names)
        rig.show_in_front = True
        # A long octahedron is much wider than a narrow wrist even when its axis
        # is correctly fitted. Slender boxes show the actual shaft without hiding
        # bones or changing the deformation skeleton.
        data.display_type = "BBONE"
        data.pose_position = "POSE"
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        collections = {
            name: data.collections.new(name)
            for name in (
                "Body",
                "Left Hand",
                "Right Hand",
                "Left Foot",
                "Right Foot",
                "Deformation",
            )
        }
        collections["Deformation"].is_visible = False
        for name, head, tail, parent, deform in bones:
            bone = data.edit_bones.new(name)
            bone.head = head
            bone.tail = tail
            bone.use_deform = deform
            digit = name.startswith(("finger_", "toe_"))
            width = min(
                float(np.linalg.norm(tail - head)) * 0.055, 0.0013 if digit else 0.003
            )
            if "." in name:
                clearance = min(
                    fitted_surface.find_nearest(head * (1 - t) + tail * t)[3]
                    for t in np.linspace(0, 1, 25)
                )
                width = min(width, float(clearance) * 0.22)
            bone.bbone_x = width
            bone.bbone_z = width
            bone.bbone_segments = 1
            category = (
                (
                    ("Left " if name.endswith(".L") else "Right ")
                    + ("Hand" if name.startswith("finger_") else "Foot")
                )
                if digit
                else "Body"
            )
            collections[category].assign(bone)
            if name.startswith("forearm_twist."):
                collections[category].unassign(bone)
                collections["Deformation"].assign(bone)
            if parent:
                bone.parent = data.edit_bones[parent]
            # Keep the existing rest offsets; local translation constraints
            # prevent joints separating while root/core can carry the body.
            bone.use_connect = False
            axis = (
                Vector((0, 0, -1))
                if digit
                else (
                    Vector((0, 0, 1))
                    if name.startswith(
                        (
                            "shoulder",
                            "upper_arm",
                            "forearm",
                            "hand",
                            "finger_",
                            "foot",
                            "toe",
                        )
                    )
                    else Vector((0, -1, 0))
                )
            )
            bone.align_roll(axis)
            if name.startswith(("forearm.", "forearm_twist.")):
                bone.align_roll(Vector((0, -1, 0)))
        bpy.ops.object.mode_set(mode="OBJECT")
        install_limits(rig)
        for side in ("L", "R"):
            helper = rig.pose.bones["forearm_twist." + side]
            counter = helper.constraints.new("COPY_ROTATION")
            counter.name = "Distributed forearm twist"
            counter.target = rig
            counter.subtarget = "forearm." + side
            counter.owner_space = counter.target_space = "LOCAL"
            counter.use_x = counter.use_z = False
            counter.use_y = True
            counter.invert_y = True
            counter.mix_mode = "AFTER"
            counter.euler_order = "YZX"
            counter.influence = 0.75
        # A Mixamo-style central control carries the torso and shares its
        # motion with the hips. Independent spine/pelvis edits remain available.
        pelvis = rig.pose.bones["pelvis"]
        follow = pelvis.constraints.new("COPY_ROTATION")
        follow.name = "Core hip follow"
        follow.target = rig
        follow.subtarget = "core"
        follow.target_space = "LOCAL"
        follow.owner_space = "LOCAL"
        follow.mix_mode = "BEFORE"
        follow.influence = 0.35
        carry = pelvis.constraints.new("COPY_LOCATION")
        carry.name = "Core translation"
        carry.target = rig
        carry.subtarget = "core"
        carry.target_space = "LOCAL"
        carry.owner_space = "LOCAL"
        carry.use_offset = True
        # The core and pelvis share a rest pivot. A larger wire envelope makes
        # the core easy to distinguish without adding scene mesh objects.
        data.bones["core"].bbone_x = 0.014
        data.bones["core"].bbone_z = 0.014
        for pb in rig.pose.bones:
            # Twist about the bent forearm's longitudinal axis, without an
            # Euler singularity at a normal 90-degree elbow bend.
            pb.rotation_mode = (
                "YZX" if pb.name.startswith(("forearm.", "forearm_twist.")) else "XYZ"
            )
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
                indices = np.flatnonzero(positive)
                indices = indices[np.argsort(column[indices])]
                values = column[indices]
                batches = np.split(
                    indices, np.flatnonzero(values[1:] != values[:-1]) + 1
                )
                for batch in batches:
                    group.add(
                        batch.tolist(),
                        float(column[batch[0]]) / WEIGHT_STEPS,
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
        if rig is not None and rig_for(root) == rig:
            remove(context, root)
        else:
            # Failed before the rig was tagged: discard only what was created.
            if rig is not None:
                bpy.data.objects.remove(rig, do_unlink=True)
            if data.users == 0:
                bpy.data.armatures.remove(data)
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
    if context.view_layer.objects.get(root.name) == root:
        root.select_set(True)
        context.view_layer.objects.active = root
