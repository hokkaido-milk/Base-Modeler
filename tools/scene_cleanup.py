"""Cleanup for generated shipping scenes, never for an arbitrary user scene."""

import bpy


def clean_scene(root):
    keep = {root, *root.children_recursive}
    for ob in list(bpy.data.objects):
        if ob not in keep:
            bpy.data.objects.remove(ob, do_unlink=True)
    for ob in keep:
        ob.animation_data_clear()
        ob.use_fake_user = False
        for key in list(ob.keys()):
            if key != "base_modeler" and not key.startswith("base_modeler_"):
                del ob[key]
        if ob.type == "MESH":
            assert not ob.modifiers and not ob.data.shape_keys
            ob.vertex_groups.clear()
            ob.data.use_fake_user = False
            used = {face.material_index for face in ob.data.polygons}
            for i in reversed(range(len(ob.data.materials))):
                if i not in used:
                    ob.data.materials.pop(index=i)
            for key in list(ob.data.keys()):
                del ob.data[key]
    for image in list(bpy.data.images):
        if image.source == "VIEWER":
            bpy.data.images.remove(image, do_unlink=True)
            continue
        if image.source == "FILE":
            if not image.packed_file:
                image.pack()
            # The texture is packed; retain a portable fallback filename.
            image.filepath = (
                "//Face_Albedo.png"
                if image.name.startswith("Face_Albedo")
                else "//" + image.name + ".png"
            )
    for blocks in (bpy.data.materials, bpy.data.images, bpy.data.node_groups):
        for block in blocks:
            block.use_fake_user = False
    for collection in list(bpy.data.collections):
        if not collection.all_objects:
            bpy.data.collections.remove(collection)
    for scene in bpy.data.scenes:
        scene.animation_data_clear()
        scene.camera = None
        scene.world = None
        for key in list(scene.keys()):
            del scene[key]
    bpy.context.view_layer.update()
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    for group in list(bpy.data.node_groups):
        if group.users == 0:
            bpy.data.node_groups.remove(group)
    assert (
        not bpy.data.cameras
        and not bpy.data.lights
        and not bpy.data.actions
        and not bpy.data.texts
    )
    assert all(material.users > 0 for material in bpy.data.materials)
