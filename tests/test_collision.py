import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import Joint, Pose  # noqa: E402
from mii.collision import CollisionModel, closest_points, load_rmdl_vertices  # noqa: E402
from mii.rig import _SKELETON_DIR, JOINT_LIMITS  # noqa: E402

COLLIDING = {
    "hand through chest": lambda: Pose().aim(Joint.SHOULDER_L, [-0.6, -0.4, 0.2]).bend(Joint.ELBOW_L, 30),
    "arms crossed": lambda: (Pose().aim(Joint.SHOULDER_L, [-0.5, -0.3, 0.6]).bend(Joint.ELBOW_L, 60)
                             .aim(Joint.SHOULDER_R, [0.5, -0.3, 0.6]).bend(Joint.ELBOW_R, 60)),
    "hand into face": lambda: (Pose().aim(Joint.SHOULDER_L, [0.2, 0.6, 0.8]).twist(Joint.SHOULDER_L, -90)
                               .bend(Joint.ELBOW_L, 140)),
    "hand into hip": lambda: Pose().aim(Joint.SHOULDER_L, [-0.3, -1, 0.3]).bend(Joint.ELBOW_L, 20),
    "legs crossed": lambda: Pose().set(Joint.HIP_L, z=-25).set(Joint.HIP_R, z=-25),
}
FREE = {
    "rest": lambda: Pose(),
    "tpose": lambda: Pose().aim(Joint.SHOULDER_L, [1, 0, 0]).aim(Joint.SHOULDER_R, [-1, 0, 0]),
    "walk": lambda: (Pose().set(Joint.HIP_L, x=-30).bend(Joint.KNEE_L, 20)
                     .set(Joint.HIP_R, x=25).bend(Joint.KNEE_R, 40)),
    "elbows90": lambda: Pose().bend(Joint.ELBOW_L, 90).bend(Joint.ELBOW_R, 90),
}


@pytest.fixture(scope="module", params=["wiiu", "switch"])
def model(request):
    return CollisionModel.load(request.param)


def test_mesh_loader_reads_bones():
    pos, bones = load_rmdl_vertices(os.path.join(_SKELETON_DIR, "body_wiiu_male_LE.rmdl"))
    assert pos.shape == (len(bones), 3)
    assert {3, 4, 5, 6, 16, 17, 18, 19} <= set(bones)


def test_closest_points_crossing_segments():
    a, b = closest_points(np.array([-1., 0, 0]), np.array([1., 0, 0]),
                          np.array([0., -1, 1]), np.array([0., 1, 1]))
    assert np.allclose(a, [0, 0, 0]) and np.allclose(b, [0, 0, 1])


@pytest.mark.parametrize("name", FREE)
def test_free_poses_are_untouched(model, name):
    pose = FREE[name]()
    assert model.contacts(pose) == []
    fixed = model.resolve(pose)
    for j in Joint:
        assert np.allclose(fixed.rotation(j), pose.rotation(j))


@pytest.mark.parametrize("name", COLLIDING)
def test_collisions_are_resolved(model, name):
    pose = COLLIDING[name]()
    if model.skeleton.name == "wiiu":
        assert model.contacts(pose), "test pose should start out colliding"
    fixed = model.resolve(pose)
    assert model.contacts(fixed) == []
    for hinge in (Joint.ELBOW_L, Joint.ELBOW_R, Joint.KNEE_L, Joint.KNEE_R):
        lo, hi = JOINT_LIMITS[Joint.ELBOW_L if "ELBOW" in hinge.name else Joint.KNEE_L]
        assert lo - 1e-6 <= fixed.hinge_angle(hinge) <= hi + 1e-6


def test_pose_shortcut():
    pose = COLLIDING["legs crossed"]()
    assert CollisionModel.load("wiiu").contacts(pose.resolve_collisions()) == []
