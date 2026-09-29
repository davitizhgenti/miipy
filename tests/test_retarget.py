import math
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import Joint, Pose  # noqa: E402
from mii import retarget as rt  # noqa: E402

LANDMARK_OF = {
    rt.L_SHOULDER: Joint.SHOULDER_L, rt.R_SHOULDER: Joint.SHOULDER_R,
    rt.L_ELBOW: Joint.ELBOW_L, rt.R_ELBOW: Joint.ELBOW_R,
    rt.L_WRIST: Joint.WRIST_L, rt.R_WRIST: Joint.WRIST_R,
    rt.L_HIP: Joint.HIP_L, rt.R_HIP: Joint.HIP_R,
    rt.L_KNEE: Joint.KNEE_L, rt.R_KNEE: Joint.KNEE_R,
    rt.L_ANKLE: Joint.ANKLE_L, rt.R_ANKLE: Joint.ANKLE_R,
}
SEGMENTS = [(Joint.SHOULDER_L, Joint.ELBOW_L), (Joint.ELBOW_L, Joint.WRIST_L),
            (Joint.SHOULDER_R, Joint.ELBOW_R), (Joint.ELBOW_R, Joint.WRIST_R),
            (Joint.HIP_L, Joint.KNEE_L), (Joint.KNEE_L, Joint.ANKLE_L),
            (Joint.HIP_R, Joint.KNEE_R), (Joint.KNEE_R, Joint.ANKLE_R)]


def fake_landmarks(pose, scale=0.1):
    """MediaPipe-style world landmarks for a posed Mii (y down, z away)."""
    pos = pose.world_positions()
    lm = [SimpleNamespace(x=0.0, y=0.0, z=0.0, visibility=0.0) for _ in range(33)]
    for i, joint in LANDMARK_OF.items():
        x, y, z = pos[joint] * scale
        lm[i] = SimpleNamespace(x=x, y=-y, z=-z, visibility=0.99)
    return lm


def angle(a, b):
    return math.degrees(math.acos(np.clip(np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b), -1, 1)))


def assert_same_limbs(a, b, tol=1.0):
    pa, pb = a.world_positions(), b.world_positions()
    for s, e in SEGMENTS:
        assert angle(pa[e] - pa[s], pb[e] - pb[s]) < tol, f"{s.name}->{e.name}"


SOURCES = {
    "rest": lambda: Pose(),
    "tpose": lambda: Pose().aim(Joint.SHOULDER_L, [1, 0, 0]).aim(Joint.SHOULDER_R, [-1, 0, 0]),
    "reach": lambda: (Pose().aim(Joint.SHOULDER_L, [0.3, 0.2, 1]).bend(Joint.ELBOW_L, 40)
                      .aim(Joint.SHOULDER_R, [-1, -0.5, 0.2]).bend(Joint.ELBOW_R, 100)),
    "walk": lambda: (Pose().set(Joint.HIP_L, x=-30).bend(Joint.KNEE_L, 20)
                     .set(Joint.HIP_R, x=25).bend(Joint.KNEE_R, 40)),
    "wave": lambda: (Pose().aim(Joint.SHOULDER_L, [1, 0.3, 0]).twist(Joint.SHOULDER_L, -95)
                     .bend(Joint.ELBOW_L, 100)).mirror().aim(Joint.SHOULDER_L, [1, 0.3, 0])
                     .twist(Joint.SHOULDER_L, -95).bend(Joint.ELBOW_L, 100),
    "hips": lambda: (Pose().set(Joint.SHOULDER_L, z=15).twist(Joint.SHOULDER_L, 80).bend(Joint.ELBOW_L, 60)
                     .set(Joint.SHOULDER_R, z=15).twist(Joint.SHOULDER_R, 80).bend(Joint.ELBOW_R, 60)),
    "kick": lambda: (Pose().set(Joint.HIP_L, x=-60, z=20).twist(Joint.HIP_L, 30).bend(Joint.KNEE_L, 70)),
    "lean": lambda: Pose().set(Joint.CHEST, x=15, y=20).aim(Joint.SHOULDER_L, [1, 0.5, 0]),
}


@pytest.mark.parametrize("name", SOURCES)
def test_roundtrip(name):
    source = SOURCES[name]()
    assert_same_limbs(source, rt.pose_from_mediapipe(fake_landmarks(source)))


def test_mirror_option():
    source = SOURCES["reach"]()
    assert_same_limbs(source.mirror(), rt.pose_from_mediapipe(fake_landmarks(source), mirror=True))


def test_invisible_limbs_stay_at_rest():
    lm = fake_landmarks(SOURCES["tpose"]())
    lm[rt.L_ELBOW].visibility = 0.1
    pose = rt.pose_from_mediapipe(lm)
    assert np.allclose(pose.rotation(Joint.SHOULDER_L), np.eye(3))
    assert not np.allclose(pose.rotation(Joint.SHOULDER_R), np.eye(3))


def test_filter_converges():
    f = rt.PoseFilter(alpha=0.5)
    target = SOURCES["tpose"]()
    f(Pose())
    for _ in range(20):
        out = f(target)
    assert_same_limbs(out, target, tol=0.1)
