"""Remove the eyebrow, eyelid-line and eyelash shells from the foundation head.

Run Blender with the foundation opened, after load_plugin.py and before
clean_assets.py. The shells float above the finished skin and share no
vertices with it. Faces and edges are deleted; vertices remain as loose
points, so vertex order stays aligned with every sculpt, contact and arm
partition asset. Running it again changes nothing.
"""

import bmesh
import bpy
from base_modeler.identity import region_name

MATERIAL = "Eyelashes_and_Eyebrows"

head = next(
    ob for ob in bpy.data.objects if ob.type == "MESH" and region_name(ob) == "Head"
)
slots = [slot.material.name if slot.material else "" for slot in head.material_slots]
if MATERIAL in slots:
    index = slots.index(MATERIAL)
    mesh = head.data
    count = len(mesh.vertices)
    edit = bmesh.new()
    try:
        edit.from_mesh(mesh)
        faces = [f for f in edit.faces if f.material_index == index]
        edges = {e for f in faces for e in f.edges}
        # The shells are separate components: none of these edges touch skin.
        assert all(all(g in faces for g in e.link_faces) for e in edges)
        bmesh.ops.delete(edit, geom=list(edges), context="EDGES_FACES")
        edit.to_mesh(mesh)
    finally:
        edit.free()
    mesh.update()
    assert len(mesh.vertices) == count
    head["base_modeler_topology"] = [
        len(mesh.vertices),
        len(mesh.edges),
        len(mesh.polygons),
    ]
    print(f"Removed {MATERIAL} shells from {head.name}", flush=True)
else:
    print(f"No {MATERIAL} shells remain on {head.name}", flush=True)
