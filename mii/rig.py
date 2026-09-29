# mii/rig.py
"""
Pose layer for the Mii body skeleton.

Convention (the same for every joint):
  * Rotations are given in BODY axes at rest: +X = the Mii's left,
    +Y = up, +Z = forward (towards the camera in a front view).
  * Euler angles are intrinsic X-Y-Z in degrees (R = Rx @ Ry @ Rz).
  * The pivot is the joint; a joint's axes are carried by its parent, so an
    elbow bend stays an elbow bend however the shoulder is posed.
  * Right-side joints take the SAME values as the left for a symmetric pose;
    they are mirrored internally.

The backend applies each override as `local = R_parent @ rest_local`, where
R_parent is an Euler rotation in the parent bone's rest axes. `Pose` converts
body-space rotations into that form, so no backend changes are needed.
"""
import csv
import math
import os
from functools import lru_cache

import numpy as np

from .constants import Joint, BoneOverride

# Mirror across the body's sagittal plane (X = left/right).
_M = np.diag([-1.0, 1.0, 1.0])

_LEFT_TO_RIGHT = {
    Joint.SHOULDER_L: Joint.SHOULDER_R,
    Joint.ELBOW_L:    Joint.ELBOW_R,
    Joint.WRIST_L:    Joint.WRIST_R,
    Joint.HIP_L:      Joint.HIP_R,
    Joint.KNEE_L:     Joint.KNEE_R,
    Joint.ANKLE_L:    Joint.ANKLE_R,
}
_RIGHT_TO_LEFT = {r: l for l, r in _LEFT_TO_RIGHT.items()}
_RIGHT_JOINTS = frozenset(_RIGHT_TO_LEFT)

# Bone at the far end of each segment; used for directions (aim, hinges).
SEGMENT_END = {
    Joint.SHOULDER_L: Joint.ELBOW_L,  Joint.SHOULDER_R: Joint.ELBOW_R,
    Joint.ELBOW_L:    Joint.WRIST_L,  Joint.ELBOW_R:    Joint.WRIST_R,
    Joint.HIP_L:      Joint.KNEE_L,   Joint.HIP_R:      Joint.KNEE_R,
    Joint.KNEE_L:     Joint.ANKLE_L,  Joint.KNEE_R:     Joint.ANKLE_R,
}

# Hinge joints and the direction a positive bend moves the segment towards.
_HINGE_TARGET = {
    Joint.ELBOW_L: np.array([0.0, 0.0, 1.0]),   # hand comes forward
    Joint.KNEE_L:  np.array([0.0, 0.0, -1.0]),  # foot goes back
}

class SwingTwist:
    """Per-direction limits (degrees) for a ball joint, in body axes.

    The rotation is split into a twist about the joint's own axis (the
    limb's length, or up for the torso) and a swing, whose components
    about body X (forward/back) and Z (sideways) are limited separately.
    Values are for the left side; the right side is mirrored.
    """

    def __init__(self, x, z, twist):
        self.x, self.z, self.twist = x, z, twist


# Hinges: (min, max) bend. Ball joints: max rotation angle, or SwingTwist.
JOINT_LIMITS = {
    Joint.ELBOW_L: (0.0, 150.0),
    Joint.KNEE_L:  (0.0, 150.0),
    Joint.SHOULDER_L: 180.0,
    Joint.WRIST_L:    80.0,
    # -x swings the leg forward, +z outwards: a leg can't go far back or
    # cross far over the other one.
    Joint.HIP_L:      SwingTwist(x=(-125.0, 30.0), z=(-20.0, 50.0), twist=(-40.0, 40.0)),
    Joint.ANKLE_L:    45.0,
    Joint.NECK:       60.0,
    # +x leans forward, z sideways, twist turns the upper body.
    Joint.CHEST:      SwingTwist(x=(-15.0, 40.0), z=(-25.0, 25.0), twist=(-35.0, 35.0)),
}

# Bones that follow a joint by a fraction: the shirt's waist seam bends with
# the chest so the lower shirt doesn't shear.
_FOLLOWERS = {15: (Joint.CHEST, 0.5)}

_SKELETON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "FFL-Testing", "fs", "content", "models", "body")

# Body types with a skeleton, indexed like the backend's BodyType enum.
SKELETON_BODY_NAMES = {0: "wiiu", 1: "switch"}
# Default body per ShaderType when body_type is -1 (cShaderTypeDefaultBodyType).
_SHADER_DEFAULT_BODY = (0, 1, 2, 0, 3)


def resolve_body_type(body_type, shader_type):
    if body_type < 0 or body_type > 4:
        return _SHADER_DEFAULT_BODY[shader_type % len(_SHADER_DEFAULT_BODY)]
    return body_type


# ---------------------------------------------------------------------------
# Rotation helpers
# ---------------------------------------------------------------------------

def euler_to_matrix(x, y, z):
    """Intrinsic X-Y-Z Euler angles in degrees -> Rx @ Ry @ Rz."""
    ax, ay, az = np.radians([x, y, z])
    cx, sx, cy, sy, cz, sz = (math.cos(ax), math.sin(ax), math.cos(ay),
                              math.sin(ay), math.cos(az), math.sin(az))
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rx @ ry @ rz


def matrix_to_euler(r):
    """Inverse of euler_to_matrix; returns degrees (x, y, z)."""
    y = math.asin(max(-1.0, min(1.0, r[0, 2])))
    if abs(r[0, 2]) < 0.999999:
        x = math.atan2(-r[1, 2], r[2, 2])
        z = math.atan2(-r[0, 1], r[0, 0])
    else:  # gimbal lock: fold z into x
        x = math.atan2(r[2, 1], r[1, 1])
        z = 0.0
    return tuple(math.degrees(a) for a in (x, y, z))


def axis_angle(axis, degrees):
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    a = math.radians(degrees)
    k = np.array([[0, -axis[2], axis[1]],
                  [axis[2], 0, -axis[0]],
                  [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(a) * k + (1 - math.cos(a)) * (k @ k)


def _to_axis_angle(r):
    """Rotation matrix -> (unit axis, degrees in [0, 180])."""
    q = matrix_to_quat(r)
    if q[0] < 0:
        q = -q
    s = np.linalg.norm(q[1:])
    if s < 1e-12:
        return np.array([1.0, 0.0, 0.0]), 0.0
    return q[1:] / s, math.degrees(2 * math.atan2(s, q[0]))


def shortest_arc(a, b):
    """Rotation matrix turning direction a onto direction b."""
    a = np.asarray(a, dtype=float) / np.linalg.norm(a)
    b = np.asarray(b, dtype=float) / np.linalg.norm(b)
    axis = np.cross(a, b)
    s = np.linalg.norm(axis)
    c = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if s < 1e-9:
        if c > 0:
            return np.eye(3)
        # Opposite: rotate 180 degrees about any perpendicular axis.
        perp = np.cross(a, [1.0, 0.0, 0.0])
        if np.linalg.norm(perp) < 1e-6:
            perp = np.cross(a, [0.0, 1.0, 0.0])
        return axis_angle(perp, 180.0)
    return axis_angle(axis, math.degrees(math.atan2(s, c)))


def matrix_to_quat(r):
    """Rotation matrix -> unit quaternion (w, x, y, z)."""
    t = np.trace(r)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (r[2, 1] - r[1, 2]) / s,
             (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2
        q = [(r[2, 1] - r[1, 2]) / s, 0.25 * s,
             (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
    elif r[1, 1] > r[2, 2]:
        s = math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2
        q = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s,
             0.25 * s, (r[1, 2] + r[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2
        q = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s,
             (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def quat_to_matrix(q):
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def slerp(q0, q1, t):
    d = float(np.dot(q0, q1))
    if d < 0:
        q1, d = -q1, -d
    if d > 0.9995:
        q = q0 + t * (q1 - q0)
        return q / np.linalg.norm(q)
    theta = math.acos(d)
    return (math.sin((1 - t) * theta) * q0 + math.sin(t * theta) * q1) / math.sin(theta)


# ---------------------------------------------------------------------------
# Skeleton
# ---------------------------------------------------------------------------

class Skeleton:
    """Rest pose of a body skeleton, loaded from the backend's CSV."""

    def __init__(self, name, parents, rest_local):
        self.name = name
        self.parents = parents                # list[int], -1 = root
        self.rest_local = rest_local          # (N, 4, 4)
        self.rest_world = self.forward({})    # (N, 4, 4)

    @classmethod
    @lru_cache(maxsize=None)
    def load(cls, name="wiiu", directory=None):
        path = os.path.join(directory or _SKELETON_DIR, f"body_{name}_skeleton.csv")
        parents, mats = [], []
        with open(path, newline="") as f:
            rows = csv.reader(f)
            next(rows)  # header
            for row in rows:
                if not row or row[0].startswith("#"):
                    continue
                parents.append(int(row[1]))
                mats.append(np.array([float(v) for v in row[2:18]]).reshape(4, 4))
        return cls(name, parents, np.array(mats))

    def forward(self, local_rotations):
        """World matrices with some bones' local 3x3 rotations replaced."""
        world = np.empty_like(self.rest_local)
        for bone, parent in enumerate(self.parents):
            local = self.rest_local[bone].copy()
            if bone in local_rotations:
                local[:3, :3] = local_rotations[bone]
            world[bone] = local if parent < 0 else world[parent] @ local
        return world

    def rest_direction(self, joint):
        """Rest-pose world direction of a joint's segment."""
        end = SEGMENT_END[joint]
        d = self.rest_world[end][:3, 3] - self.rest_world[joint][:3, 3]
        return d / np.linalg.norm(d)

    def hinge_axis(self, joint):
        """Left-side hinge axis (body space) for ELBOW/KNEE."""
        left = _RIGHT_TO_LEFT.get(joint, joint)
        axis = np.cross(self.rest_direction(left), _HINGE_TARGET[left])
        return axis / np.linalg.norm(axis)


# ---------------------------------------------------------------------------
# Pose
# ---------------------------------------------------------------------------

def _limit_key(joint):
    return _RIGHT_TO_LEFT.get(joint, joint)


class Pose:
    """A set of joint rotations in the body-space convention (see module doc).

    Rotations are stored in "left-side space": a right-side joint stores the
    rotation its left counterpart would have in a symmetric pose.
    """

    def __init__(self, skeleton=None):
        self.skeleton = skeleton or Skeleton.load("wiiu")
        self._rot = {}  # Joint -> 3x3, left-side space

    def copy(self):
        p = Pose(self.skeleton)
        p._rot = {j: r.copy() for j, r in self._rot.items()}
        return p

    # --- setting rotations -------------------------------------------------

    def set(self, joint, x=0.0, y=0.0, z=0.0):
        """Set a joint's rotation from body-space Euler angles (degrees)."""
        return self.set_rotation(joint, euler_to_matrix(x, y, z))

    def set_rotation(self, joint, rotation):
        """Set from a 3x3 matrix or a (w, x, y, z) quaternion."""
        joint = Joint(joint)
        r = np.asarray(rotation, dtype=float)
        self._rot[joint] = quat_to_matrix(r) if r.shape == (4,) else r
        return self

    def bend(self, joint, degrees):
        """Bend a hinge joint (ELBOW_x / KNEE_x). Positive = natural flexion."""
        joint = Joint(joint)
        if _limit_key(joint) not in _HINGE_TARGET:
            raise ValueError(f"{joint.name} is not a hinge joint")
        return self.set_rotation(joint, axis_angle(self.skeleton.hinge_axis(joint), degrees))

    def twist(self, joint, degrees):
        """Roll a limb about its own length (keeps where it points).

        For a shoulder this turns the plane the elbow bends in; applied on
        top of the joint's current rotation.
        """
        joint = Joint(joint)
        if joint not in SEGMENT_END or _limit_key(joint) in _HINGE_TARGET:
            raise ValueError(f"{joint.name} cannot twist")
        axis = self.skeleton.rest_direction(_limit_key(joint))
        return self.set_rotation(joint, self.rotation(joint) @ axis_angle(axis, degrees))

    def aim(self, joint, direction):
        """Point a limb segment along a body-space direction.

        Parents must be posed first. Hinge joints only bend in their plane.
        """
        joint = Joint(joint)
        if joint not in SEGMENT_END:
            raise ValueError(f"{joint.name} has no segment to aim")
        sk = self.skeleton
        parent = sk.parents[joint]
        posed_parent = self.world_matrices()[parent][:3, :3]
        rest_parent = sk.rest_world[parent][:3, :3]
        # Target in the frame the joint's rotation is expressed in.
        target = rest_parent @ posed_parent.T @ np.asarray(direction, dtype=float)
        rest_dir = sk.rest_direction(joint)
        if _limit_key(joint) in _HINGE_TARGET:
            axis = _mirror_axis(joint, sk.hinge_axis(joint))
            t = target - axis * np.dot(target, axis)
            angle = math.degrees(math.atan2(np.dot(np.cross(rest_dir, t), axis),
                                            np.dot(rest_dir, t)))
            return self.bend(joint, angle)
        body = shortest_arc(rest_dir, target)
        return self.set_rotation(joint, _mirror(joint, body))

    def aim_limb(self, joint, upper_direction, lower_direction):
        """Point a two-segment limb (SHOULDER_x or HIP_x) at two directions.

        Aims the upper segment, twists it so the lower segment's hinge
        (elbow/knee) can reach `lower_direction`, then bends the hinge.
        """
        joint = Joint(joint)
        hinge = SEGMENT_END.get(joint)
        if hinge is None or _limit_key(hinge) not in _HINGE_TARGET:
            raise ValueError(f"{joint.name} is not the root of a two-segment limb")
        self.aim(joint, upper_direction)
        self.twist(joint, self._hinge_twist(joint, hinge, lower_direction))
        return self.aim(hinge, lower_direction)

    def _hinge_twist(self, joint, hinge, lower_direction):
        """Twist (stored-space degrees) putting lower_direction in the hinge plane."""
        sk = self.skeleton
        parent = sk.parents[joint]
        to_frame = sk.rest_world[parent][:3, :3] @ self.world_matrices()[parent][:3, :3].T
        r = self.body_rotation(joint)
        u = r @ sk.rest_direction(joint)                      # upper segment
        a = r @ _mirror_axis(hinge, sk.hinge_axis(hinge))     # hinge axis
        f0 = r @ sk.rest_direction(hinge)                     # unbent lower segment
        f = to_frame @ np.asarray(lower_direction, dtype=float)
        f = f / np.linalg.norm(f)
        # Twisting by t about u turns a into R(u, t) a; solve a(t) . f = 0.
        ap = a - u * np.dot(a, u)
        fp = f - u * np.dot(f, u)
        if np.linalg.norm(ap) < 1e-6 or np.linalg.norm(fp) < 0.05:
            return 0.0  # limb (nearly) straight: twist is not observable
        e1 = ap / np.linalg.norm(ap)
        e2 = np.cross(u, e1)
        c1, c2 = np.dot(fp, e1), np.dot(fp, e2)
        c = -np.dot(a, u) * np.dot(u, f) / (np.linalg.norm(ap) * math.hypot(c1, c2))
        beta, delta = math.atan2(c2, c1), math.acos(max(-1.0, min(1.0, c)))
        best = None
        for t in (beta + delta, beta - delta):
            rt = axis_angle(u, math.degrees(t))
            at, ft = rt @ a, rt @ f0
            bend = math.degrees(math.atan2(np.dot(np.cross(ft, f), at), np.dot(ft, f)))
            score = (bend < -1.0, abs(t))  # prefer natural flexion, then least twist
            if best is None or score < best[0]:
                best = (score, math.degrees(t))
        t = (best[1] + 180.0) % 360.0 - 180.0
        return -t if joint in _RIGHT_JOINTS else t

    def reach(self, joint, target, pole=None):
        """Two-bone IK: move a limb's hand/foot to `target` (body space).

        `joint` is SHOULDER_x or HIP_x. The elbow/knee stays on the side it
        is currently on (or towards `pole`); out-of-reach targets are
        approached as closely as possible.
        """
        joint = Joint(joint)
        hinge = SEGMENT_END[joint]
        end = SEGMENT_END[hinge]
        sk = self.skeleton
        rest = sk.rest_world
        l1 = np.linalg.norm(rest[hinge][:3, 3] - rest[joint][:3, 3])
        l2 = np.linalg.norm(rest[end][:3, 3] - rest[hinge][:3, 3])

        world = self.world_matrices()
        s = world[joint][:3, 3]
        to_target = np.asarray(target, dtype=float) - s
        d = np.linalg.norm(to_target)
        if d < 1e-6:
            return self
        u = to_target / d
        # Fully extended = the rest pose's span (the rest limb isn't quite
        # straight, and the elbow/knee can't bend backwards past it).
        span = np.linalg.norm(rest[end][:3, 3] - rest[joint][:3, 3])
        d = min(max(d, abs(l1 - l2) + 1e-3), span - 1e-3)
        if pole is None:
            pole = world[hinge][:3, 3] - s
        pole = np.asarray(pole, dtype=float)
        pole = pole - u * np.dot(pole, u)
        if np.linalg.norm(pole) < 1e-3:  # straight limb: bend the natural way
            default = np.array([0.0, 0.0, -1.0 if _limit_key(joint) == Joint.SHOULDER_L else 1.0])
            pole = default - u * np.dot(default, u)
        pole /= np.linalg.norm(pole)
        cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
        a = math.acos(max(-1.0, min(1.0, cos_a)))
        knee = s + l1 * (math.cos(a) * u + math.sin(a) * pole)
        return self.aim_limb(joint, knee - s, s + d * u - knee)

    def to_dict(self):
        """{joint name: quaternion [w, x, y, z]} for saving (e.g. as JSON)."""
        return {j.name: matrix_to_quat(r).tolist() for j, r in self._rot.items()}

    @classmethod
    def from_dict(cls, data, skeleton=None):
        pose = cls(skeleton)
        for name, q in data.items():
            pose.set_rotation(Joint[name], np.asarray(q, dtype=float))
        return pose

    def hinge_angle(self, joint):
        """Current bend of a hinge joint (ELBOW_x / KNEE_x) in degrees."""
        joint = Joint(joint)
        q = matrix_to_quat(self.rotation(joint))
        angle = math.degrees(2 * math.atan2(np.dot(q[1:], self.skeleton.hinge_axis(joint)), q[0]))
        return (angle + 180.0) % 360.0 - 180.0

    def rotate_world(self, joint, axis, degrees):
        """Rotate a joint (and everything below it) about a world-space axis."""
        joint = Joint(joint)
        sk = self.skeleton
        parent = sk.parents[joint]
        # The joint's frame is carried by its parent: world = C @ R_body @ rest.
        c = self.world_matrices()[parent][:3, :3] @ sk.rest_world[parent][:3, :3].T
        r = c.T @ axis_angle(axis, degrees) @ c @ self.body_rotation(joint)
        return self.set_rotation(joint, _mirror(joint, r))

    def resolve_collisions(self, head_scale=1.0):
        """Copy of this pose with limbs pushed out of the body and each other."""
        from .collision import CollisionModel
        return CollisionModel.load(self.skeleton.name, head_scale).resolve(self)

    def reset(self, joint=None):
        if joint is None:
            self._rot.clear()
        else:
            self._rot.pop(Joint(joint), None)
        return self

    # --- reading -----------------------------------------------------------

    def rotation(self, joint):
        """Stored rotation (left-side space) as a 3x3 matrix."""
        return self._rot.get(Joint(joint), np.eye(3)).copy()

    def euler(self, joint):
        return matrix_to_euler(self.rotation(joint))

    def body_rotation(self, joint):
        """Rotation actually applied, in body space (right side mirrored)."""
        return _mirror(Joint(joint), self.rotation(joint))

    # --- operations --------------------------------------------------------

    def mirror(self):
        """Swap left and right (a mirror-image pose)."""
        p = Pose(self.skeleton)
        for j, r in self._rot.items():
            if j in _LEFT_TO_RIGHT:
                p._rot[_LEFT_TO_RIGHT[j]] = r.copy()
            elif j in _RIGHT_TO_LEFT:
                p._rot[_RIGHT_TO_LEFT[j]] = r.copy()
            else:
                p._rot[j] = _M @ r @ _M
        return p

    def lerp(self, other, t):
        """Interpolate towards another pose (slerp per joint)."""
        p = Pose(self.skeleton)
        for j in set(self._rot) | set(other._rot):
            q = slerp(matrix_to_quat(self.rotation(j)), matrix_to_quat(other.rotation(j)), t)
            p._rot[j] = quat_to_matrix(q)
        return p

    def clamp(self, limits=None):
        """Return a copy with every joint limited to its anatomical range."""
        limits = JOINT_LIMITS if limits is None else limits
        p = self.copy()
        for j, r in p._rot.items():
            lim = limits.get(_limit_key(j))
            if lim is None:
                continue
            if isinstance(lim, SwingTwist):
                p._rot[j] = self._clamp_swing_twist(j, r, lim)
            elif isinstance(lim, tuple):  # hinge: keep only the bend component
                axis = self.skeleton.hinge_axis(j)
                q = matrix_to_quat(r)
                angle = math.degrees(2 * math.atan2(np.dot(q[1:], axis), q[0]))
                angle = (angle + 180.0) % 360.0 - 180.0
                p._rot[j] = axis_angle(axis, min(max(angle, lim[0]), lim[1]))
            else:
                axis, angle = _to_axis_angle(r)
                if angle > lim:
                    p._rot[j] = axis_angle(axis, lim)
        return p

    def _twist_axis(self, joint):
        if _limit_key(joint) in SEGMENT_END:
            return self.skeleton.rest_direction(_limit_key(joint))
        return np.array([0.0, 1.0, 0.0])

    def _clamp_swing_twist(self, joint, r, lim):
        axis = self._twist_axis(joint)
        q = matrix_to_quat(r)
        if q[0] < 0:
            q = -q
        # Twist = rotation about `axis`; swing = the rest (r = swing @ twist).
        tw = np.array([q[0], *(axis * np.dot(q[1:], axis))])
        n = np.linalg.norm(tw)
        tw = tw / n if n > 1e-9 else np.array([1.0, 0.0, 0.0, 0.0])
        twist_deg = math.degrees(2 * math.atan2(np.dot(tw[1:], axis), tw[0]))
        swing = r @ quat_to_matrix(tw).T
        sw_axis, sw_deg = _to_axis_angle(swing)
        w = sw_axis * sw_deg  # swing as a rotation vector (degrees)
        wx = min(max(w[0], lim.x[0]), lim.x[1])
        wz = min(max(w[2], lim.z[0]), lim.z[1])
        # A swing is perpendicular to the twist axis: rebuild its y part.
        w = np.array([wx, -(wx * axis[0] + wz * axis[2]) / axis[1], wz])
        swing = axis_angle(w, np.linalg.norm(w)) if np.linalg.norm(w) > 1e-9 else np.eye(3)
        twist = axis_angle(axis, min(max(twist_deg, lim.twist[0]), lim.twist[1]))
        return swing @ twist

    # --- output ------------------------------------------------------------

    def local_rotations(self, skeleton=None):
        """{bone index: posed local 3x3 rotation} for posed joints."""
        sk = skeleton or self.skeleton
        out = {}
        for j in self._rot:
            parent = sk.parents[j]
            wp = sk.rest_world[parent][:3, :3]
            r_parent = wp.T @ self.body_rotation(j) @ wp
            out[int(j)] = r_parent @ sk.rest_local[j][:3, :3]
        for bone, (joint, f) in _FOLLOWERS.items():
            if joint in self._rot:
                wp = sk.rest_world[sk.parents[bone]][:3, :3]
                r_parent = wp.T @ self._follow(joint, f) @ wp
                out[bone] = r_parent @ sk.rest_local[bone][:3, :3]
        return out

    def _follow(self, joint, fraction):
        q = slerp(np.array([1.0, 0.0, 0.0, 0.0]), matrix_to_quat(self.body_rotation(joint)), fraction)
        return quat_to_matrix(q)

    def world_matrices(self, skeleton=None):
        sk = skeleton or self.skeleton
        return sk.forward(self.local_rotations(sk))

    def world_positions(self, skeleton=None):
        """{Joint: world position} of each posable joint (FK)."""
        world = self.world_matrices(skeleton)
        return {j: world[j][:3, 3].copy() for j in Joint}

    def to_bone_overrides(self, skeleton=None):
        """BoneOverrides in the backend's convention (Euler in parent rest axes)."""
        sk = skeleton or self.skeleton
        out = []
        for j in self._rot:
            wp = sk.rest_world[sk.parents[j]][:3, :3]
            r_parent = wp.T @ self.body_rotation(j) @ wp
            out.append(BoneOverride(int(j), rotate=matrix_to_euler(r_parent)))
        for bone, (joint, f) in _FOLLOWERS.items():
            if joint in self._rot:
                wp = sk.rest_world[sk.parents[bone]][:3, :3]
                out.append(BoneOverride(bone, rotate=matrix_to_euler(wp.T @ self._follow(joint, f) @ wp)))
        return out


def _mirror(joint, r):
    return _M @ r @ _M if joint in _RIGHT_JOINTS else r


def _mirror_axis(joint, axis):
    # M R(a, t) M = R(-M a, t): a mirrored rotation turns about -M a.
    return -(_M @ axis) if joint in _RIGHT_JOINTS else axis
