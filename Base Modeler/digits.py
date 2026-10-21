"""Neutral digit landmarks and topology-aware skin binding."""

import heapq
import numpy as np
from .pose import CENTER_X, smooth

# Longitudinal joint stations measured on this foundation's neutral skin.
# Thumb includes the metacarpal; the other fingers have three phalanges.
FINGERS = {
    "thumb": ((0.598, -0.062), (0.622, -0.088), (0.639, -0.103), (0.650, -0.112)),
    "index": ((0.651, -0.077), (0.681, -0.083), (0.707, -0.087), (0.727, -0.088)),
    "middle": ((0.655, -0.060), (0.686, -0.067), (0.712, -0.073), (0.732, -0.075)),
    "ring": ((0.654, -0.044), (0.684, -0.048), (0.705, -0.053), (0.725, -0.056)),
    "little": ((0.650, -0.026), (0.673, -0.028), (0.690, -0.030), (0.701, -0.031)),
}
# Big toe has two phalanges; the remaining toes have three.
TOES = {
    "big": ((0.051, -0.090), (0.051, -0.112), (0.051, -0.134)),
    "second": ((0.069, -0.088), (0.069, -0.103), (0.069, -0.112), (0.069, -0.129)),
    "third": ((0.080, -0.080), (0.080, -0.098), (0.080, -0.104), (0.080, -0.120)),
    "fourth": ((0.090, -0.072), (0.090, -0.088), (0.090, -0.094), (0.090, -0.107)),
    "little": ((0.099, -0.065), (0.099, -0.077), (0.099, -0.084), (0.099, -0.094)),
}


def chains(side):
    sign = 1 if side == "L" else -1
    for kind, table in (("finger", FINGERS), ("toe", TOES)):
        for digit, stations in table.items():
            points = np.array(
                [
                    (CENTER_X + sign * x, y, 1.42 if kind == "finger" else 0.005)
                    for x, y in stations
                ],
                dtype=np.float32,
            )
            names = [f"{kind}_{digit}.{i+1:02d}.{side}" for i in range(len(points) - 1)]
            yield kind, digit, points, names


def closest_segments(points, joints):
    """Distance to each bone axis and its unbounded longitudinal coordinate."""
    a, b = joints[:-1], joints[1:]
    axis = b - a
    length = np.linalg.norm(axis, axis=1)
    parameter = np.einsum("nsd,sd->ns", points[:, None] - a, axis) / length**2
    nearest = a + np.clip(parameter, 0, 1)[:, :, None] * axis
    distance = np.linalg.norm(points[:, None] - nearest, axis=2)
    return distance, parameter, length


def joint_blend(a, b, coordinate):
    """A C1 ramp with bounded gradient through a tight joint's inner crease."""
    t = np.clip((coordinate - a) / (b - a), 0, 1)
    shoulder = 0.15
    linear = (t - shoulder * 0.5) / (1 - shoulder)
    start = t * t / (2 * shoulder * (1 - shoulder))
    end = 1 - (1 - t) ** 2 / (2 * shoulder * (1 - shoulder))
    return np.where(t < shoulder, start, np.where(t > 1 - shoulder, end, linear))


def geodesic_distances(points, edges, chains):
    """Distance to each digit through skin edges, across neither air nor gaps."""
    adjacency = [[] for _ in points]
    lengths = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)
    for (a, b), length in zip(edges, lengths):
        adjacency[a].append((b, float(length)))
        adjacency[b].append((a, float(length)))
    fields = []
    for joints in chains:
        distance, parameter, length = closest_segments(points, joints)
        # Seed only the terminal cap. Shaft-distance seeds can accidentally
        # land on a neighbouring toe across a narrow air gap.
        tip_distance = np.linalg.norm(points - joints[-1], axis=1)
        seed = int(np.argmin(tip_distance))
        cost = np.full(len(points), np.inf)
        cost[seed] = tip_distance[seed]
        queue = [(float(cost[seed]), seed)]
        while queue:
            value, a = heapq.heappop(queue)
            if value > cost[a]:
                continue
            for b, step in adjacency[a]:
                candidate = value + step
                if candidate < cost[b]:
                    cost[b] = candidate
                    heapq.heappush(queue, (candidate, b))
        # Remove the expected longitudinal trip from cap to joint. This
        # avoids favouring short digits at the web while retaining the long
        # skin detour between separate toes/fingers.
        cumulative = np.r_[0, np.cumsum(length)]
        nearest = distance.argmin(1)
        projected = np.clip(parameter[np.arange(len(points)), nearest], 0, 1)
        projected = np.where(
            (nearest == 0) & (parameter[:, 0] < 0), parameter[:, 0], projected
        )
        along = cumulative[nearest] + projected * length[nearest]
        cost -= np.maximum(cumulative[-1] - along, 0)
        fields.append(cost)
    return np.array(fields).T


def bind_digits(points, edges, bones, names, weights):
    """Replace distal hand/foot weights with local phalanx blends on the skin."""
    fitted = {name: (head, tail) for name, head, tail, _, _ in bones}
    for side, sign in (("L", 1), ("R", -1)):
        for kind in ("finger", "toe"):
            mask = (points[:, 0] - CENTER_X) * sign > (
                0.585 if kind == "finger" else 0.015
            )
            mask &= points[:, 2] > 1.3 if kind == "finger" else points[:, 2] < 0.055
            if kind == "toe":
                mask &= points[:, 1] < -0.045
            ids = np.flatnonzero(mask)
            local = np.full(len(points), -1, dtype=np.int32)
            local[ids] = np.arange(len(ids))
            selected = mask[edges].all(1)
            local_edges = local[edges[selected]]
            entries = []
            for entry_kind, digit, _, bone_names in chains(side):
                if entry_kind != kind:
                    continue
                joints = np.array(
                    [fitted[bone_names[0]][0]] + [fitted[n][1] for n in bone_names]
                )
                entries.append((digit, bone_names, joints))
            distance = geodesic_distances(
                points[ids], local_edges, [e[2] for e in entries]
            )
            # A soft partition around the web avoids a discontinuity where two
            # digits meet. Farther along each digit the skin route to its
            # neighbours is long, so their influence is exactly zero.
            membership = 1 - smooth(
                0,
                0.009 if kind == "finger" else 0.006,
                distance - distance.min(1)[:, None],
            )
            membership /= membership.sum(1)[:, None]
            digit_names = [name for _, bone_names, _ in entries for name in bone_names]
            columns = [names.index(name) for name in digit_names]
            lookup = {name: i for i, name in enumerate(digit_names)}
            digit_weights = np.zeros((len(ids), len(digit_names)), np.float32)
            activation = np.zeros(len(ids), np.float32)
            for index, (digit, bone_names, joints) in enumerate(entries):
                take = np.flatnonzero(membership[:, index] > 0)
                distance, parameter, length = closest_segments(
                    points[ids[take]], joints
                )
                cumulative = np.r_[0, np.cumsum(length)]
                nearest = distance.argmin(1)
                projected = np.clip(parameter[np.arange(len(take)), nearest], 0, 1)
                # Segment projections meet at the shared joint, avoiding a
                # discontinuity across the inside of a curved phalanx chain.
                projected = np.where(
                    (nearest == 0) & (parameter[:, 0] < 0), parameter[:, 0], projected
                )
                along = cumulative[nearest] + projected * length[nearest]
                # Short, smooth transitions at the knuckle and each interphalangeal
                # joint keep the palm stable and leave distal pads rigid.
                band = min(
                    0.010 if kind == "finger" else 0.008, float(length[0]) * 0.48
                )
                amount = joint_blend(-band, band, along) * membership[take, index]
                # A projected thumb axis can reach across the hollow palm.
                # Keep each digit's support local to its actual capsule;
                # geodesic ownership alone has no parent/palm competitor.
                radius = 0.018 if kind == "finger" else 0.010
                amount *= 1 - smooth(radius, radius * 2, distance.min(1))
                if kind == "finger" and digit == "thumb":
                    # The metacarpal carries the thenar pad, while the back
                    # half of the palm remains with the hand control.
                    amount *= 1 - smooth(-0.062, -0.043, points[ids[take], 1])
                activation[take] += amount
                previous = np.ones(len(take))
                for j, name in enumerate(bone_names):
                    if j == len(bone_names) - 1:
                        following = np.zeros(len(take))
                    else:
                        fraction = 0.4 if digit in ("thumb", "big") else 0.5
                        width = min(float(length[j]), float(length[j + 1])) * fraction
                        following = joint_blend(
                            cumulative[j + 1] - width, cumulative[j + 1] + width, along
                        )
                    digit_weights[take, lookup[name]] = amount * (previous - following)
                    previous = following
            # Fair only the opening around each web. Fully owned phalanges stay
            # fixed, preventing smoothing from bleeding through nearby digits.
            src = np.r_[local_edges[:, 0], local_edges[:, 1]]
            dst = np.r_[local_edges[:, 1], local_edges[:, 0]]
            degree = np.bincount(src, minlength=len(ids)).astype(np.float32)
            field = digit_weights
            fair = (activation > 0) & (activation < 0.999)
            for _ in range(6):
                total = np.zeros_like(field)
                np.add.at(total, src, field[dst])
                average = total / np.maximum(degree[:, None], 1)
                field[fair] = field[fair] * 0.65 + average[fair] * 0.35
            amount = field.sum(1)
            weights[ids] *= 1 - amount[:, None]
            weights[np.ix_(ids, columns)] += field
    return weights


def bind_nails(points, edges, bones, names, weights, kind):
    adjacency = [[] for _ in points]
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    terminals = []
    fitted = {name: (head, tail) for name, head, tail, _, _ in bones}
    for side in ("L", "R"):
        for entry_kind, _, _, bone_names in chains(side):
            if entry_kind == kind:
                name = bone_names[-1]
                terminals.append((names.index(name), np.array(fitted[name])))
    remaining = set(range(len(points)))
    while remaining:
        seed = remaining.pop()
        ids = [seed]
        pending = [seed]
        while pending:
            for neighbor in adjacency[pending.pop()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
                    ids.append(neighbor)
        center = points[ids].mean(0)
        group = min(
            terminals,
            key=lambda entry: float(closest_segments(center[None], entry[1])[0].min()),
        )[0]
        weights[ids] = 0
        weights[ids, group] = 1
