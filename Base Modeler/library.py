"""Rollback support for appending the bundled model."""

import bpy

_DATA_COLLECTIONS = (
    "objects",
    "collections",
    "meshes",
    "armatures",
    "materials",
    "images",
    "textures",
    "node_groups",
    "actions",
)


def snapshot():
    """Record existing IDs; creation rollback must retain user-owned data."""
    return {
        name: {block.as_pointer() for block in getattr(bpy.data, name)}
        for name in _DATA_COLLECTIONS
    }


def rollback(before):
    created = [
        block
        for name, pointers in before.items()
        for block in getattr(bpy.data, name)
        if block.as_pointer() not in pointers
    ]
    if created:
        bpy.data.batch_remove(ids=created)
