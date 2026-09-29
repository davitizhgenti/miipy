import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import Joint, Pose  # noqa: E402
from mii.animation import Clip  # noqa: E402


def test_clip_hits_keyframes_and_loops():
    a, b = Pose(), Pose().bend(Joint.ELBOW_L, 90)
    clip = Clip([(0.0, a), (0.5, b)])
    assert np.allclose(clip(0.0).rotation(Joint.ELBOW_L), a.rotation(Joint.ELBOW_L))
    assert np.allclose(clip(0.5).rotation(Joint.ELBOW_L), b.rotation(Joint.ELBOW_L))
    assert np.allclose(clip(1.0).rotation(Joint.ELBOW_L), a.rotation(Joint.ELBOW_L))   # loops back
    assert np.allclose(clip(0.25).rotation(Joint.ELBOW_L), clip(0.75).rotation(Joint.ELBOW_L))


def test_clip_no_loop_holds_last_pose():
    b = Pose().bend(Joint.KNEE_L, 60)
    clip = Clip([(0.0, Pose()), (0.5, b)], loop=False)
    assert np.allclose(clip(0.9).rotation(Joint.KNEE_L), b.rotation(Joint.KNEE_L))
