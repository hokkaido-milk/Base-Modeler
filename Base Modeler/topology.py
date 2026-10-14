"""Local wrist tessellation repair; vertex order, rest data and UVs stay intact."""

import bmesh
import numpy as np
from .identity import region_name

TAG = "base_modeler_tessellation_schema"


def repair_tessellation(objects):
    """Replace only sliver-producing n-gons with quality triangles, once.

    Never accept a user's changed topology as a new valid slider binding.
    BMesh carries all point and corner data, including rest positions and UVs.
    """
    repaired = 0
    for ob in objects:
        if region_name(ob) != "Body_Surface" or ob.get(TAG, 0) >= 1:
            continue
        mesh = ob.data
        counts = [len(mesh.vertices), len(mesh.edges), len(mesh.polygons)]
        if list(ob.get("base_modeler_topology", [])) != counts:
            continue
        mesh.calc_loop_triangles()
        q = np.empty(len(mesh.vertices) * 3, np.float32)
        mesh.vertices.foreach_get("co", q)
        q = q.reshape(-1, 3)
        tri = np.array([t.vertices[:] for t in mesh.loop_triangles])
        p = q[tri]
        area = (
            np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1) * 0.5
        )
        bad = {
            mesh.loop_triangles[i].polygon_index
            for i in np.flatnonzero(area < 1e-9)
            if len(mesh.polygons[mesh.loop_triangles[i].polygon_index].vertices) > 4
        }
        if bad:
            edit = bmesh.new()
            try:
                edit.from_mesh(mesh)
                edit.faces.ensure_lookup_table()
                bmesh.ops.triangulate(
                    edit,
                    faces=[edit.faces[i] for i in bad],
                    quad_method="BEAUTY",
                    ngon_method="BEAUTY",
                )
                edit.to_mesh(mesh)
            finally:
                edit.free()
            mesh.update()
            ob["base_modeler_topology"] = [
                len(mesh.vertices),
                len(mesh.edges),
                len(mesh.polygons),
            ]
            repaired += len(bad)
        ob[TAG] = 1
    return repaired
