"""The artist-facing body controls. Ratios are neutral at one, amounts at zero."""

from dataclasses import dataclass

SOURCE_HEIGHT_CM = 179.08274633809924


@dataclass(frozen=True)
class Control:
    id: str
    label: str
    group: str
    minimum: float = 0.85
    default: float = 1.0
    maximum: float = 1.15
    description: str = "Scale this body region continuously; 1 is the supplied shape."


def amount(id, label, group, description, maximum=1.0, minimum=-1.0):
    return Control(id, label, group, minimum, 0.0, maximum, description)


CONTROLS = (
    Control(
        "height",
        "Height (cm)",
        "Global",
        120.0,
        SOURCE_HEIGHT_CM,
        200.0,
        "Overall measured height in centimeters; keep the source floor fixed.",
    ),
    Control(
        "torso_leg",
        "Torso / leg ratio",
        "Global",
        description="Increase torso length relative to legs while retaining overall height.",
    ),
    Control(
        "build",
        "Build",
        "Global",
        description="Change overall body breadth and limb thickness, retaining the head.",
    ),
    amount(
        "fullness",
        "Fullness",
        "Global",
        "Add or remove rounded volume across the torso and limbs.",
    ),
    amount(
        "muscle",
        "Muscle definition",
        "Global",
        "Change localized muscle bulges on the actual surface.",
    ),
    Control(
        "head_size",
        "Head size",
        "Head",
        0.9,
        1.0,
        1.1,
        "Scale the complete head and facial features with a blended neck connection.",
    ),
    Control(
        "shoulder_span",
        "Shoulder span",
        "Shoulders",
        description="Widen shoulders and carry arms and hands with them.",
    ),
    Control("ribcage_width", "Ribcage width", "Ribcage"),
    amount(
        "breast_size",
        "Size",
        "Breast",
        "Change breast width, height and projection together.",
        maximum=2.5,
    ),
    amount(
        "breast_gap",
        "Gap",
        "Breast",
        "Move breast contours closer together or farther apart.",
    ),
    amount(
        "breast_firmness",
        "Firmness / sag",
        "Breast",
        "Sculpt a lifted or lowered rest shape; this is not a physics simulation.",
        minimum=-1.5,
    ),
    Control("waist_size", "Waist size", "Waist"),
    Control(
        "hip_size",
        "Hip size",
        "Hips",
        maximum=1.3,
        description="Change pelvis width and depth; carry the leg centers with the pelvis.",
    ),
    amount("hip_curve", "Outer curve", "Hips", "Change the contour of the outer hips."),
    amount(
        "butt_size",
        "Size",
        "Butt",
        "Change buttock width, height and rear projection together.",
        maximum=2.0,
    ),
    amount(
        "butt_gap",
        "Gap",
        "Butt",
        "Move the rear lobes while pinning the center crease.",
    ),
    amount(
        "butt_firmness",
        "Firmness / sag",
        "Butt",
        "Lift and round or lower and soften the posterior contours.",
    ),
    Control(
        "thigh_length",
        "Length",
        "Thigh",
        description="Lengthen thighs, carrying the torso without resizing it; measured height updates.",
    ),
    Control("thigh_size", "Thickness", "Thigh", maximum=1.3),
    amount(
        "thigh_taper",
        "Taper",
        "Thigh",
        "Change upper-thigh fullness with a blended knee transition.",
    ),
    Control(
        "leg_length",
        "Length",
        "Leg",
        description="Lengthen lower legs, carrying the torso without resizing it; measured height updates.",
    ),
    amount(
        "leg_size",
        "Calf / ankle size",
        "Leg",
        "Change calf fullness and ankle thickness together.",
    ),
    Control(
        "leg_alignment",
        "Alignment (degrees)",
        "Leg",
        -4.0,
        0.0,
        4.0,
        "Move knees inward or outward with continuous transitions to hips and feet.",
    ),
    Control(
        "foot_size",
        "Foot size",
        "Foot",
        description="Scale feet, toes and toenails together with a fixed ankle transition.",
    ),
    Control(
        "arm_size",
        "Arm size",
        "Arm",
        description="Change upper arm, forearm and wrist thickness together.",
    ),
    Control(
        "arm_length",
        "Arm length",
        "Arm",
        description="Lengthen both arm segments and carry the hands with their wrists.",
    ),
    Control(
        "hand_size",
        "Hand size",
        "Hand",
        description="Scale palms, fingers and fingernails together around the wrist.",
    ),
)
BY_ID = {c.id: c for c in CONTROLS}
GROUPS = tuple(dict.fromkeys(c.group for c in CONTROLS))


def defaults():
    return {c.id: c.default for c in CONTROLS}
