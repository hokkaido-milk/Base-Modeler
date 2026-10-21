"""Fit limb joints to skin cross sections and carry them through body shaping."""

import numpy as np


class SkinSections:
    """Sample corresponding closed skin contours in the neutral and shaped body.

    Sections use anatomical stations in the neutral mesh. Their intersected
    edges and fractions are then reused on the shaped mesh, so custom lengths,
    widths and height do not depend on a world-axis search in the new shape.
    """

    def __init__(self, reference, current, triangles):
        self.reference = reference
        self.current = current
        self.triangles = triangles
        self.faces = reference[triangles]

    def center(self, axis, station, near, fixed_axis=None, depth_fraction=None):
        # Avoid sections passing exactly through an edge/vertex. Two tenths of
        # a micron is below the mesh tolerance and keeps crossings unambiguous.
        if np.any(abs(self.reference[:, axis] - station) < 1e-9):
            station += 2e-7
        distance = self.faces[:, :, axis] - station
        crossing = (distance.min(1) < 0) & (distance.max(1) > 0)
        faces = self.triangles[crossing]
        distance = distance[crossing]
        endpoints = []
        owners = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            mask = distance[:, a] * distance[:, b] < 0
            endpoints.append(np.sort(faces[mask][:, (a, b)], axis=1))
            owners.append(np.flatnonzero(mask))
        edges = np.concatenate(endpoints)
        owners = np.concatenate(owners)
        if not len(edges):
            raise ValueError("No skin cross section at a rig joint.")
        unique, inverse = np.unique(edges, axis=0, return_inverse=True)
        a, b = unique.T
        da = self.reference[a, axis] - station
        db = self.reference[b, axis] - station
        fraction = da / (da - db)
        source = self.reference[a] + fraction[:, None] * (
            self.reference[b] - self.reference[a]
        )
        current = self.current[a] + fraction[:, None] * (
            self.current[b] - self.current[a]
        )
        order = np.argsort(owners)
        owner_counts = np.bincount(owners, minlength=len(faces))
        if not np.all(owner_counts == 2):
            raise ValueError("A rig cross section is not a closed skin contour.")
        segments = inverse[order].reshape(-1, 2)
        neighbors = [[] for _ in unique]
        for a, b in segments:
            neighbors[a].append(b)
            neighbors[b].append(a)
        remaining = set(range(len(unique)))
        candidates = []
        while remaining:
            start = remaining.pop()
            component = {start}
            pending = [start]
            while pending:
                for neighbor in neighbors[pending.pop()]:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        component.add(neighbor)
                        pending.append(neighbor)
            if len(component) < 3 or any(len(neighbors[i]) != 2 for i in component):
                continue
            ids = np.array(sorted(component))
            if fixed_axis is not None:
                # Keep a forefoot joint on its metatarsal/toe ray instead of
                # averaging the broad foot and pulling it into a toe web.
                pairs = np.array([(i, j) for i in ids for j in neighbors[i] if i < j])
                u, v = pairs.T
                da = source[u, fixed_axis] - near[fixed_axis]
                db = source[v, fixed_axis] - near[fixed_axis]
                cut = da * db < 0
                if not cut.any():
                    continue
                u, v = u[cut], v[cut]
                fraction = da[cut] / (da[cut] - db[cut])
                hits = source[u] + fraction[:, None] * (source[v] - source[u])
                mapped_hits = current[u] + fraction[:, None] * (current[v] - current[u])
                remaining_axis = next(
                    k for k in range(3) if k not in (axis, fixed_axis)
                )
                order = np.argsort(hits[:, remaining_axis])
                if len(order) % 2:
                    continue
                for first, second in order.reshape(-1, 2):
                    low, high = hits[[first, second], remaining_axis]
                    if high - low < 1e-9:
                        continue
                    fraction = (
                        float(
                            np.clip(
                                (near[remaining_axis] - low) / (high - low), 0.25, 0.75
                            )
                        )
                        if depth_fraction is None
                        else depth_fraction
                    )
                    center = hits[first] * (1 - fraction) + hits[second] * fraction
                    mapped = (
                        mapped_hits[first] * (1 - fraction)
                        + mapped_hits[second] * fraction
                    )
                    candidates.append((float(np.linalg.norm(center - near)), mapped))
                continue
            center = (source[ids].min(0) + source[ids].max(0)) * 0.5
            mapped = (current[ids].min(0) + current[ids].max(0)) * 0.5
            candidates.append((float(np.linalg.norm(center - near)), mapped))
        if not candidates:
            raise ValueError("No closed skin contour surrounds a rig joint.")
        return min(candidates, key=lambda item: item[0])[1]
