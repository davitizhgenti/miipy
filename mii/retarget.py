# mii/retarget.py
"""
Drive a `rig.Pose` from MediaPipe Pose *world* landmarks (3D, metres,
hip-centred), so arms and legs follow the tracked person in 3D.

Only limb directions are used, so the person's proportions don't matter.
"""
import numpy as np

from .constants import Joint
from .rig import Pose

# MediaPipe Pose landmark indices (left = the person's anatomical left).
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28

# (root joint, start, middle, end landmark) of each two-segment limb.
_ARMS = [(Joint.SHOULDER_L, L_SHOULDER, L_ELBOW, L_WRIST),
         (Joint.SHOULDER_R, R_SHOULDER, R_ELBOW, R_WRIST)]
_LEGS = [(Joint.HIP_L, L_HIP, L_KNEE, L_ANKLE),
         (Joint.HIP_R, R_HIP, R_KNEE, R_ANKLE)]


def to_body_space(landmark):
    """MediaPipe world axes (x = image right, y down, z away from camera)
    -> body axes (x = Mii's left, y up, z forward/towards the camera).

    A person facing the camera has their left side at image right, so the
    Mii copies the person (not a mirror image). Pass mirror=True to
    pose_from_mediapipe for a selfie-style mirror.
    """
    return np.array([landmark.x, -landmark.y, -landmark.z])


def _torso_frame(p):
    """Rotation whose columns are the torso's left, up and forward axes."""
    left = p[L_SHOULDER] - p[R_SHOULDER]
    up = (p[L_SHOULDER] + p[R_SHOULDER]) / 2 - (p[L_HIP] + p[R_HIP]) / 2
    left /= np.linalg.norm(left)
    fwd = np.cross(left, up)
    fwd /= np.linalg.norm(fwd)
    up = np.cross(fwd, left)
    return np.column_stack([left, up, fwd])


def pose_from_mediapipe(world_landmarks, skeleton=None, legs=True, torso=True,
                        mirror=False, min_visibility=0.5, clamp=True, collide=True):
    """Build a Pose from `results.pose_world_landmarks.landmark` (or any
    sequence of objects with x, y, z and optionally visibility).

    clamp applies joint limits; collide pushes limbs out of the body."""
    lm = list(world_landmarks)
    p = {i: to_body_space(lm[i]) for i in range(len(lm))}
    visible = lambda *ids: all(getattr(lm[i], "visibility", 1.0) >= min_visibility for i in ids)  # noqa: E731

    pose = Pose(skeleton)
    if torso and visible(L_SHOULDER, R_SHOULDER, L_HIP, R_HIP):
        pose.set_rotation(Joint.CHEST, _torso_frame(p))
    for joint, a, b, c in _ARMS + (_LEGS if legs else []):
        if visible(a, b, c):
            pose.aim_limb(joint, p[b] - p[a], p[c] - p[b])
        elif visible(a, b):
            pose.aim(joint, p[b] - p[a])
    if mirror:
        pose = pose.mirror()
    if clamp:
        pose = pose.clamp()
    return pose.resolve_collisions() if collide else pose


class PoseFilter:
    """Exponential smoothing of poses (slerp towards each new pose).

    alpha = 1 follows instantly; smaller values are smoother but lag more.
    """

    def __init__(self, alpha=0.5):
        self.alpha = alpha
        self.pose = None

    def __call__(self, pose):
        self.pose = pose if self.pose is None else self.pose.lerp(pose, self.alpha)
        return self.pose
