"""Local skin tessellation repair; vertex order, rest data and UVs stay intact."""

import bmesh
import numpy as np
from .identity import region_name

TAG = "base_modeler_tessellation_schema"
SCHEMA = 2


def repair_tessellation(objects):
    """Replace only sliver-producing n-gons with quality triangles, once.

    Never accept a user's changed topology as a new valid slider binding.
    BMesh carries all point and corner data, including rest positions and UVs.
    """
    repaired = 0
    for ob in objects:
        if region_name(ob) != "Body_Surface" or ob.get(TAG, 0) >= SCHEMA:
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
        # Long, concave hip quads can place an implicit diagonal almost along
        # the lower rim. Fix its diagonal before posing/sculpting, rather than
        # letting a near-collinear triangle collapse during hip compression.
        hip_quads = {"FIXED": [], "ALTERNATE": []}
        for face in mesh.polygons:
            if len(face.vertices) != 4:
                continue
            v = q[list(face.vertices)]
            center = v.mean(0)
            if not (0.84 < center[2] < 1.10 and center[1] > 0.0):
                continue

            def areas(indices):
                t = v[indices]
                return np.linalg.norm(
                    np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1
                )

            ac = areas([[0, 1, 2], [0, 2, 3]])
            bd = areas([[0, 1, 3], [1, 2, 3]])
            poor, good, method = (
                (ac, bd, "ALTERNATE") if ac.min() < bd.min() else (bd, ac, "FIXED")
            )
            if poor.min() < poor.max() * 0.35 and good.min() > poor.min() * 1.5:
                hip_quads[method].append(face.index)
        if bad or any(hip_quads.values()):
            edit = bmesh.new()
            try:
                edit.from_mesh(mesh)
                edit.faces.ensure_lookup_table()
                source_faces = list(edit.faces)
                bmesh.ops.triangulate(
                    edit,
                    faces=[source_faces[i] for i in bad],
                    quad_method="BEAUTY",
                    ngon_method="BEAUTY",
                )
                for method, indices in hip_quads.items():
                    bmesh.ops.triangulate(
                        edit,
                        faces=[source_faces[i] for i in indices],
                        quad_method=method,
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
            repaired += len(bad) + sum(map(len, hip_quads.values()))
        ob[TAG] = SCHEMA
    return repaired
