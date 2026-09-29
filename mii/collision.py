# mii/collision.py
"""
Self-collision for posed bodies: keeps limbs from passing through the
torso, head, each other and the other legs.

Every body part is a capsule (a line segment with a radius) fitted to the
real body mesh (the backend's .rmdl files); the head is a sphere matching
FFL's head size. `resolve()` pushes intersecting limbs out by rotating the
shoulder (arms) or hip (legs) the least amount needed.

Units are the unscaled skeleton units used by `rig.Skeleton`.
"""
import os
import struct
from functools import lru_cache

import numpy as np

from .constants import Joint
from .rig import JOINT_LIMITS, Skeleton, _SKELETON_DIR, _limit_key, _mirror_axis

# Body parts that get a collider, and which joint moves to resolve a hit.
TORSO, WAIST, PELVIS, HEAD = 3, 15, 16, 14
_ARM_L, _ARM_R = (4, 5, 6), (9, 10, 11)
_LEG_L, _LEG_R = (17, 18, 19), (21, 22, 23)
_MOVER = {**{b: Joint.SHOULDER_L for b in _ARM_L}, **{b: Joint.SHOULDER_R for b in _ARM_R},
          **{b: Joint.HIP_L for b in _LEG_L}, **{b: Joint.HIP_R for b in _LEG_R}}
_LIMBS = [_ARM_L, _ARM_R, _LEG_L, _LEG_R]
_ROUND = (6, 11, 19, 23)  # hands and shoes
# Parts below a hinge also resolve by opening/closing the elbow or knee.
_HINGE = {5: Joint.ELBOW_L, 6: Joint.ELBOW_L, 10: Joint.ELBOW_R, 11: Joint.ELBOW_R,
          18: Joint.KNEE_L, 19: Joint.KNEE_L, 22: Joint.KNEE_R, 23: Joint.KNEE_R}

# FFL head (faceline + hair) as a sphere in head units, measured from the
# backend's glTF export; the head is drawn at 1/7.14286 of the body scale.
HEAD_CENTER = np.array([0.0, 36.0, -1.5])
HEAD_RADIUS = 33.0
HEAD_TO_BODY = 1.0 / 7.14286


def load_rmdl_vertices(path):
    """(positions (N, 3), bone index (N,)) of a rio .rmdl model."""
    with open(path, "rb") as f:
        d = f.read()
    if d[:8] != b"riomodel":
        raise ValueError(f"{path} is not a rio model")

    def buffer(off):  # rio Buffer<T>: relative offset + element count
        rel, count = struct.unpack_from("<iI", d, off)
        return off + rel, count

    mesh_off, mesh_count = buffer(16)
    pos, bones = [], []
    for i in range(mesh_count):
        vtx_off, vtx_count = buffer(mesh_off + i * 0x38)
        v = np.frombuffer(d, dtype=np.float32, count=vtx_count * 8, offset=vtx_off).reshape(-1, 8)
        pos.append(v[:, :3])
        bones.append(v[:, 3].astype(int))  # texCoord.x is the bone index
    return np.vstack(pos).astype(float), np.concatenate(bones)


class Capsule:
    """Segment a-b (bone-local) with a radius."""

    def __init__(self, bone, a, b, radius):
        self.bone, self.a, self.b, self.radius = bone, np.asarray(a), np.asarray(b), float(radius)

    def world(self, world_matrices):
        m = world_matrices[self.bone]
        return m[:3, :3] @ self.a + m[:3, 3], m[:3, :3] @ self.b + m[:3, 3]


def _fit_capsule(bone, points, enclose=False):
    """Capsule along the cloud's principal axis.

    The radius is the tube's typical radius and the segment spans the
    cloud's length minus that radius, so the rounded ends land on the
    extremes. With enclose=True (round parts: hands, shoes) the radius
    grows to cover the points around the segment instead.
    """
    c = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - c)
    axis = vt[0]
    t = (points - c) @ axis
    tube = np.median(np.linalg.norm((points - c) - np.outer(t, axis), axis=1))
    lo, hi = t.min() + tube, t.max() - tube
    if lo > hi:
        lo = hi = (t.min() + t.max()) / 2
    a, b = c + lo * axis, c + hi * axis
    r = tube
    if enclose:
        seg = np.clip(t, lo, hi)
        r = np.percentile(np.linalg.norm((points - c) - np.outer(seg, axis), axis=1), 85)
    return Capsule(bone, a, b, r)


def closest_points(p1, q1, p2, q2):
    """Closest points between segments p1-q1 and p2-q2 (Ericson, RTCD 5.1.9)."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1 @ d1, d2 @ d2, d2 @ r
    if a <= 1e-12 and e <= 1e-12:
        return p1, p2
    if a <= 1e-12:
        s, t = 0.0, np.clip(f / e, 0, 1)
    else:
        c = d1 @ r
        if e <= 1e-12:
            t, s = 0.0, np.clip(-c / a, 0, 1)
        else:
            b = d1 @ d2
            denom = a * e - b * b
            s = np.clip((b * f - c * e) / denom, 0, 1) if denom > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, np.clip(-c / a, 0, 1)
            elif t > 1:
                t, s = 1.0, np.clip((b - c) / a, 0, 1)
    return p1 + d1 * s, p2 + d2 * t


class CollisionModel:
    """Colliders for one skeleton, plus the pairs that must not intersect."""

    def __init__(self, skeleton, capsules, head_scale=1.0, margin=0.05):
        self.skeleton = skeleton
        self.capsules = capsules
        hc = HEAD_CENTER * HEAD_TO_BODY * head_scale
        self.capsules[HEAD] = Capsule(HEAD, hc, hc, HEAD_RADIUS * HEAD_TO_BODY * head_scale)
        self.margin = margin
        self.pairs = self._make_pairs()

    @classmethod
    @lru_cache(maxsize=None)
    def load(cls, name="wiiu", head_scale=1.0):
        """Fit colliders to the body mesh (both genders, so it fits either)."""
        skeleton = Skeleton.load(name)
        pts, bones = [], []
        for gender in ("male", "female"):
            p, b = load_rmdl_vertices(os.path.join(_SKELETON_DIR, f"body_{name}_{gender}_LE.rmdl"))
            pts.append(p)
            bones.append(b)
        pts, bones = np.vstack(pts), np.concatenate(bones)
        caps = {b: _fit_capsule(b, pts[bones == b], enclose=b in _ROUND)
                for b in (PELVIS, *_ARM_L, *_ARM_R, *_LEG_L, *_LEG_R)}
        # The shirt is split between the chest and a waist ring (bone 15):
        # fit the torso to both, in the chest's frame.
        rest = skeleton.rest_world
        waist = pts[bones == WAIST]
        waist = (np.linalg.inv(rest[TORSO]) @ rest[WAIST] @ np.c_[waist, np.ones(len(waist))].T).T[:, :3]
        caps[TORSO] = _fit_capsule(TORSO, np.vstack([pts[bones == TORSO], waist]))
        return cls(skeleton, caps, head_scale)

    def _make_pairs(self):
        """(bone, bone, allowed overlap): limb parts vs everything they could hit.

        Parts that already overlap in the rest pose (e.g. the thighs and the
        torso's bottom) may keep that much overlap, so only new penetration
        is resolved.
        """
        body = [TORSO, PELVIS, HEAD]
        cand = set()
        for i, limb in enumerate(_LIMBS):
            for part in limb:
                for other in body + [p for j, l in enumerate(_LIMBS) if j != i for p in l]:
                    if self.skeleton.parents[part] != other:  # skip the joint it hangs from
                        cand.add(tuple(sorted((part, other))))
        rest = self.skeleton.rest_world
        return [(a, b, max(0.0, self._penetration(a, b, rest)[0])) for a, b in sorted(cand)]

    def _penetration(self, a, b, world):
        ca, cb = self.capsules[a], self.capsules[b]
        pa, pb = closest_points(*ca.world(world), *cb.world(world))
        d = pb - pa
        dist = np.linalg.norm(d)
        n = d / dist if dist > 1e-9 else np.array([0.0, 0.0, 1.0])
        return ca.radius + cb.radius - dist, pa, pb, n  # n points from a to b

    def contacts(self, pose):
        """[(bone_a, bone_b, depth beyond the allowed overlap), ...] for a pose."""
        world = pose.world_matrices(self.skeleton)
        out = []
        for a, b, allowed in self.pairs:
            depth = self._penetration(a, b, world)[0] - allowed - self.margin
            if depth > 0:
                out.append((a, b, depth))
        return out

    def resolve(self, pose, iterations=12):
        """Return a copy of `pose` with limbs pushed out of the body and each other."""
        pose = pose.copy()
        for _ in range(iterations):
            world = pose.world_matrices(self.skeleton)
            hit = False
            for a, b, allowed in self.pairs:
                depth, pa, pb, n = self._penetration(a, b, world)
                depth -= allowed + self.margin * 0.5
                if depth <= 0:
                    continue
                hit = True
                sides = [(part, sign, p) for part, sign, p in ((a, -1, pa), (b, 1, pb)) if part in _MOVER]
                share = 1.2 * depth / len(sides)
                for part, sign, point in sides:
                    left = share
                    if part in _HINGE:  # half through the elbow/knee if it can help
                        left -= _push_hinge(pose, world, _HINGE[part], point, sign * n, share / 2)
                    _push(pose, world, _MOVER[part], point, sign * n, left)
                    world = pose.world_matrices(self.skeleton)
            if not hit:
                break
        return pose


def _push_hinge(pose, world, joint, point, direction, distance):
    """Bend a hinge so `point` moves along `direction`; returns distance achieved."""
    sk = pose.skeleton
    parent = sk.parents[joint]
    c = world[parent][:3, :3] @ sk.rest_world[parent][:3, :3].T
    axis = c @ _mirror_axis(joint, sk.hinge_axis(joint))
    gain = np.dot(direction, np.cross(axis, point - world[joint][:3, 3]))
    if abs(gain) < 0.3:  # the hinge barely moves the point this way
        return 0.0
    lo, hi = JOINT_LIMITS[_limit_key(joint)]
    current = pose.hinge_angle(joint)
    target = float(np.clip(current + np.degrees(distance / gain), lo, hi))
    pose.bend(joint, target)
    return abs(np.radians(target - current) * gain)


def _push(pose, world, joint, point, direction, distance):
    """Rotate `joint` so `point` moves `distance` along `direction` (world)."""
    pivot = world[joint][:3, 3]
    r = point - pivot
    axis = np.cross(r, direction)
    lever = np.linalg.norm(axis)
    if lever < 1e-6 or distance <= 0:
        return
    angle = min(np.degrees(distance / lever), 30.0)
    pose.rotate_world(joint, axis / lever, angle)
