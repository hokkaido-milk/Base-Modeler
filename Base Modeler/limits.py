"""Native local-space posing limits, in degrees relative to the fitted T-pose.

These are drawing-reference guardrails, not a clinical range-of-motion model.
Parent and child budgets are shared (especially head/neck); independent Euler
bounds cannot prevent every compound-pose collision.
"""

from math import radians


def rotation_limits(name):
    """Return XYZ intervals; Y is each bone's longitudinal/twist axis."""
    central = {
        "core": ((-25, 40), (-20, 20), (-20, 20)),
        "pelvis": ((-25, 30), (-25, 25), (-20, 20)),
        "spine": ((-20, 35), (-20, 20), (-25, 25)),
        "chest": ((-15, 25), (-25, 25), (-20, 20)),
        "neck": ((-35, 40), (-55, 55), (-30, 30)),
        "head": ((-20, 25), (-25, 25), (-15, 15)),
    }
    if name in central:
        return central[name]
    if name == "root" or name.startswith("forearm_twist."):
        return None
    kind = name.split(".")[0]
    if kind.startswith(("finger_", "toe_")):
        joint = int(name.split(".")[1])
        if kind == "finger_thumb":
            return (
                ((-35, 45), (-35, 35), (-40, 40))
                if joint == 1
                else (
                    ((-10, 80), (0, 0), (-10, 10))
                    if joint == 2
                    else ((-10, 85), (0, 0), (0, 0))
                )
            )
        if kind.startswith("finger_"):
            return (
                ((-20, 95), (0, 0), (-20, 20))
                if joint == 1
                else ((0, 110 if joint == 2 else 85), (0, 0), (0, 0))
            )
        return ((-35, 50), (0, 0), (-8, 8)) if joint == 1 else ((0, 70), (0, 0), (0, 0))
    bounds = {
        "shoulder": ((-15, 25), (-15, 15), (-20, 20)),
        # Rest arms are abducted 90 degrees; negative X lowers them.
        "upper_arm": ((-100, 90), (-85, 85), (-100, 50)),
        # Elbow roll places X on the flexion axis, toward the front on both sides.
        "forearm": ((-5, 150), (-90, 90), (0, 0)),
        "hand": ((-75, 80), (0, 0), (-25, 35)),
        "thigh": ((-30, 135), (-45, 45), (-25, 55)),
        "shin": ((-145, 3), (-8, 8), (-3, 3)),
        "foot": ((-50, 30), (-15, 15), (-20, 20)),
        "toe": ((-15, 20), (0, 0), (-5, 5)),
    }[kind]
    # Mirrored bones have matching flexion X, mirrored transverse Z.
    if name.endswith(".R"):
        bounds = (bounds[0], bounds[1], (-bounds[2][1], -bounds[2][0]))
    return bounds


def install_limits(rig):
    """Use constraints as well as channel locks, so animation respects limits."""
    for pb in rig.pose.bones:
        helper = pb.name.startswith("forearm_twist.")
        movable = pb.name in ("root", "core")
        pb.lock_location = (not movable,) * 3
        pb.lock_scale = (True,) * 3
        if not movable:
            c = pb.constraints.new("LIMIT_LOCATION")
            c.name = "Joint position (locked)"
            c.owner_space = "LOCAL"
            c.use_min_x = c.use_max_x = True
            c.use_min_y = c.use_max_y = True
            c.use_min_z = c.use_max_z = True
            c.use_transform_limit = True
        c = pb.constraints.new("LIMIT_SCALE")
        c.name = "Bone scale (locked)"
        c.owner_space = "LOCAL"
        for axis in "xyz":
            setattr(c, "use_min_" + axis, True)
            setattr(c, "use_max_" + axis, True)
            setattr(c, "min_" + axis, 1.0)
            setattr(c, "max_" + axis, 1.0)
        c.use_transform_limit = True
        limits = ((0, 0),) * 3 if helper else rotation_limits(pb.name)
        if limits is None:
            pb.lock_rotation = (False,) * 3
            continue
        pb.lock_rotation = tuple(lo == hi for lo, hi in limits)
        c = pb.constraints.new("LIMIT_ROTATION")
        c.name = "Human rotation range"
        c.owner_space = "LOCAL"
        c.euler_order = "YZX" if pb.name.startswith("forearm.") else "XYZ"
        c.use_transform_limit = True
        for axis, (lo, hi) in zip("xyz", limits):
            setattr(c, "use_limit_" + axis, True)
            setattr(c, "min_" + axis, radians(lo))
            setattr(c, "max_" + axis, radians(hi))
