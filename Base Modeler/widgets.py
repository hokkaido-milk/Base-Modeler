"""Solid custom-shape widgets: clickable from any angle, owned by their rig."""

from math import cos, sin, tau
import bpy

TAG = "base_modeler_widget"
# Earlier target balls carried their own tag; cleanup still releases them.
LEGACY_TAGS = (TAG, "base_modeler_target_controls")


def _object(name, vertices, faces):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    ob = bpy.data.objects.new(name, mesh)
    ob[TAG] = True
    return ob


def ball(name, segments=16, rings=10):
    """A unit sphere with a nub along +Y showing the control's orientation."""
    vertices = [(0.0, 0.0, 1.0)]
    for ring in range(1, rings):
        polar = tau / 2 * ring / rings
        for i in range(segments):
            azimuth = tau * i / segments
            vertices.append(
                (sin(polar) * cos(azimuth), sin(polar) * sin(azimuth), cos(polar))
            )
    vertices.append((0.0, 0.0, -1.0))
    bottom = len(vertices) - 1
    faces = [(0, 1 + i, 1 + (i + 1) % segments) for i in range(segments)]
    for ring in range(rings - 2):
        a, b = 1 + ring * segments, 1 + (ring + 1) * segments
        faces += [
            (a + i, b + i, b + (i + 1) % segments, a + (i + 1) % segments)
            for i in range(segments)
        ]
    last = 1 + (rings - 2) * segments
    faces += [(last + (i + 1) % segments, last + i, bottom) for i in range(segments)]
    # Orientation nub: a cone leaving the surface along the bone's Y axis.
    base = len(vertices)
    cone = 8
    for i in range(cone):
        angle = tau * i / cone
        vertices.append((0.32 * cos(angle), 0.9, 0.32 * sin(angle)))
    vertices.append((0.0, 1.75, 0.0))
    faces += [(base + i, base + (i + 1) % cone, base + cone) for i in range(cone)]
    return _object(name, vertices, faces)


def ring(name, tube=0.07, segments=48, sides=8):
    """A unit torus around the bone's Y axis, solid from every viewing angle."""
    vertices = []
    for i in range(segments):
        angle = tau * i / segments
        for j in range(sides):
            phi = tau * j / sides
            radius = 1.0 + tube * cos(phi)
            vertices.append((radius * cos(angle), tube * sin(phi), radius * sin(angle)))
    faces = [
        (
            i * sides + j,
            i * sides + (j + 1) % sides,
            (i + 1) % segments * sides + (j + 1) % sides,
            (i + 1) % segments * sides + j,
        )
        for i in range(segments)
        for j in range(sides)
    ]
    return _object(name, vertices, faces)


def assign(pose_bone, shape, scale, offset=(0.0, 0.0, 0.0)):
    """Show a widget at a fixed metric size, independent of bone length."""
    pose_bone.custom_shape = shape
    pose_bone.use_custom_shape_bone_size = False
    pose_bone.custom_shape_scale_xyz = scale
    pose_bone.custom_shape_translation = offset
    pose_bone.bone.show_wire = False
    if hasattr(pose_bone, "custom_shape_wire_width"):
        pose_bone.custom_shape_wire_width = 2.0


def cleanup(rig):
    """Release only widget data owned by this add-on."""
    shapes = {
        pb.custom_shape
        for pb in rig.pose.bones
        if pb.custom_shape and any(pb.custom_shape.get(t) for t in LEGACY_TAGS)
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
