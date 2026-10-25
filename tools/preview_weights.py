"""Compare identical skeletal poses before/after weighting, including bone roll changes."""

from pathlib import Path
import json
import bpy
import numpy as np
from mathutils import Vector, Euler

OUT = Path(__file__).resolve().parents[1] / "artifacts/weight_refinement"
AFTER = OUT / "Female Anatomy - Limited Rig.blend"
bpy.ops.wm.open_mainfile(filepath=str(AFTER))
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
new_axes = {b.name: b.matrix_local.to_3x3().copy() for b in rig.data.bones}
poses = [
    ("elbow", {"forearm.L": (100, 0, 0)}, (0.35, -0.12, 1.43), (0.8, -2, 0.7), 0.68),
    ("twist", {"forearm.L": (90, 80, 0)}, (0.35, -0.12, 1.43), (0.8, -2, 0.7), 0.68),
    (
        "shoulder",
        {"upper_arm.L": (-80, 0, 0), "forearm.L": (70, 0, 0)},
        (0.16, -0.02, 1.30),
        (1, -3, 0.3),
        0.72,
    ),
    (
        "seated",
        {
            "thigh.L": (90, 0, 0),
            "thigh.R": (90, 0, 0),
            "shin.L": (-90, 0, 0),
            "shin.R": (-90, 0, 0),
        },
        (0, -0.12, 0.88),
        (1, -3, 0.3),
        1.5,
    ),
    (
        "torso",
        {"spine": (30, 0, 15), "chest": (15, 15, 0)},
        (0, 0, 1.25),
        (1, -3, 0.2),
        0.9,
    ),
]
reports = {}
for tag in ("Before", "After"):
    bpy.ops.wm.open_mainfile(
        filepath=str(OUT / "Before.blend" if tag == "Before" else AFTER)
    )
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    rig.update_tag()
    bpy.context.view_layer.update()
    objects = [o for o in rig.parent.children_recursive if o.type == "MESH"]
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob not in objects:
            ob.hide_render = True
    geometry = {}
    for ob in objects:
        p = np.array([v.co[:] for v in ob.data.vertices])
        edges = np.array([e.vertices[:] for e in ob.data.edges])
        ob.data.calc_loop_triangles()
        tri = np.array([t.vertices[:] for t in ob.data.loop_triangles])
        v = p[tri]
        area = np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)
        length = np.linalg.norm(p[edges[:, 1]] - p[edges[:, 0]], axis=1)
        geometry[ob.name] = (edges, tri, length, area)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    s = scene.display.shading
    s.light = "STUDIO"
    s.color_type = "SINGLE"
    s.single_color = (0.64, 0.64, 0.64)
    s.show_cavity = True
    s.cavity_type = "BOTH"
    s.background_type = "WORLD"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Review World")
    scene.world.color = (0.15, 0.15, 0.15)
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    cam = bpy.data.objects.new(
        "Weight Review Camera", bpy.data.cameras.new("Weight Review Camera")
    )
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    reports[tag] = {}
    for label, pose, target, offset, scale in poses:
        for pb in rig.pose.bones:
            pb.matrix_basis.identity()
        for name, angles in pose.items():
            pb = rig.pose.bones[name]
            order = "YZX" if name.startswith("forearm.") else "XYZ"
            rotation = Euler(np.radians(angles), order).to_matrix()
            if tag == "Before":
                old = pb.bone.matrix_local.to_3x3()
                change = old.inverted() @ new_axes[name]
                rotation = change @ rotation @ change.inverted()
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = rotation.to_quaternion()
            else:
                pb.rotation_euler = np.radians(angles)
        rig.update_tag()
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        rows = {}
        for ob in objects:
            ev = ob.evaluated_get(graph)
            mesh = ev.to_mesh()
            p = np.array([v.co[:] for v in mesh.vertices])
            ev.to_mesh_clear()
            edges, tri, length, area = geometry[ob.name]
            ratio = (
                np.linalg.norm(p[edges[:, 1]] - p[edges[:, 0]], axis=1)[length > 1e-5]
                / length[length > 1e-5]
            )
            v = p[tri]
            newarea = np.linalg.norm(
                np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1
            )
            valid = area > 2e-9
            rows[ob.get("base_modeler_region", ob.name)] = {
                "stretch_p99": float(np.quantile(ratio, 0.99)),
                "compression_p01": float(np.quantile(ratio, 0.01)),
                "max_stretch": float(ratio.max()),
                "collapsed_faces": int(np.sum(valid & (newarea < area * 0.01))),
            }
        reports[tag][label] = rows
        cam.location = Vector(target) + Vector(offset)
        cam.rotation_euler = (
            (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        )
        cam.data.ortho_scale = scale
        scene.render.filepath = str(OUT / f"{tag.lower()}_{label}.png")
        bpy.ops.render.render(write_still=True)
(OUT / "pose_comparison.json").write_text(json.dumps(reports, indent=2) + "\n")
