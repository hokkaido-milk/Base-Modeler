"""Stable region identifiers keep bindings independent of display names."""

import re

REGION_KEY = "base_modeler_region"
REGIONS = (
    "Biceps_brachii",
    "Biceps_femoris_region",
    "Body_Surface",
    "Brachioradialis",
    "Deltoid",
    "External_oblique",
    "Fingernails",
    "Forearm_extensor_group",
    "Forearm_flexor_group",
    "Gastrocnemius",
    "Gluteus_maximus",
    "Gluteus_medius",
    "Head",
    "Infraspinatus_region",
    "Latissimus_dorsi",
    "Medial_hamstring_group",
    "Pectoralis_major",
    "Rectus_abdominis",
    "Rectus_femoris",
    "Serratus_anterior",
    "Sternocleidomastoid",
    "Tensor_fasciae_latae",
    "Teres_major_region",
    "Tibialis_anterior",
    "Toenails",
    "Trapezius",
    "Triceps_brachii",
    "Vastus_lateralis",
    "Vastus_medialis",
)


def region_name(ob):
    """Read the binding identity, with a fallback for existing saved models."""
    return ob.get(REGION_KEY) or re.sub(r"\.\d+$", "", ob.name)


def meshes_for(root):
    return sorted(
        (ob for ob in root.children_recursive if ob.type == "MESH"), key=region_name
    )


def assign_regions(root):
    """Tag known regions on existing files without guessing unknown identities."""
    for ob in meshes_for(root):
        name = region_name(ob)
        if name in REGIONS and REGION_KEY not in ob:
            ob[REGION_KEY] = name
