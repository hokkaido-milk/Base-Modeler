"""Repair imported shading data when upgrading an existing Base Modeler body."""


def match_skin_tone(objects):
    head = next(
        (
            m
            for ob in objects
            for m in ob.data.materials
            if m and m.name.startswith("Head_Skin")
        ),
        None,
    )
    if head is None:
        return
    tone = tuple(head.diffuse_color)
    brown = (0.4620769918, 0.155926466, 0.0722718537, 1.0)
    head_shader = (
        next((n for n in head.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if head.node_tree
        else None
    )
    for ob in objects:
        for slot in ob.material_slots:
            material = slot.material
            if not material:
                continue
            body = material.name.startswith("Connective_Tissue")
            if not body and not material.name.startswith("Head_Skin"):
                continue
            # Keep unrelated objects that happen to share a source material intact.
            if material.users > 1:
                material = material.copy()
                slot.material = material
            if body:
                material.diffuse_color = tone
            if not material.node_tree:
                continue
            for node in material.node_tree.nodes:
                if node.type == "MIX_RGB":
                    for name in ("Color1", "Color2"):
                        socket = node.inputs[name]
                        if not socket.is_linked and all(
                            abs(a - b) < 1e-6
                            for a, b in zip(socket.default_value, brown)
                        ):
                            socket.default_value = tone
                elif body and node.type == "BSDF_PRINCIPLED":
                    node.inputs["Base Color"].default_value = tone
                    if head_shader:
                        for name in ("Roughness", "Specular IOR Level"):
                            node.inputs[name].default_value = head_shader.inputs[
                                name
                            ].default_value


def prepare_surfaces(objects):
    for ob in objects:
        mesh = ob.data
        custom = mesh.attributes.get("custom_normal")
        if custom:
            mesh.attributes.remove(custom)
            mesh.update()
        for slot in ob.material_slots:
            material = slot.material
            if (
                not material
                or not material.name.startswith("Connective_Tissue")
                or not material.node_tree
            ):
                continue
            tree = material.node_tree
            links = [
                link
                for link in tree.links
                if link.from_node.type == "NEW_GEOMETRY"
                and link.from_socket.name == "Position"
            ]
            if not links:
                continue
            # Do not change an unrelated object that shares the old material.
            if material.users > 1:
                material = material.copy()
                slot.material = material
                tree = material.node_tree
                links = [
                    link
                    for link in tree.links
                    if link.from_node.type == "NEW_GEOMETRY"
                    and link.from_socket.name == "Position"
                ]
            anchor = tree.nodes.new("ShaderNodeAttribute")
            anchor.attribute_name = "base_modeler_rest"
            anchor.label = "Source coordinates: stable during body edits"
            for link in links:
                target = link.to_socket
                tree.links.remove(link)
                tree.links.new(anchor.outputs["Vector"], target)
