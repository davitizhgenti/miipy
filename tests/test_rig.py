import math
import os
import struct
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import Joint, Pose, Skeleton, RenderSettings, Bone, BoneOverride  # noqa: E402
from mii.rig import euler_to_matrix, matrix_to_euler  # noqa: E402

M = np.diag([-1.0, 1.0, 1.0])
SKELETONS = ["wiiu", "switch"]


def angle_between(a, b):
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    return math.degrees(math.acos(np.clip(np.dot(a, b), -1, 1)))


def segment(pos, a, b):
    return pos[b] - pos[a]


def rio_make_r(x, y, z):
    """Port of rio::Matrix34f::makeR (rio_MatrixImpl.h) for radians x, y, z."""
    sx, sy, sz = math.sin(x), math.sin(y), math.sin(z)
    cx, cy, cz = math.cos(x), math.cos(y), math.cos(z)
    return np.array([
        [cy * cz, sx * sy * cz - cx * sz, cx * cz * sy + sx * sz],
        [cy * sz, sx * sy * sz + cx * cz, cx * sz * sy - sx * cz],
        [-sy, sx * cy, cx * cy],
    ])


def backend_local_rotations(skeleton, overrides):
    """What BodyModel::applyBoneRotations does with the packed Euler values."""
    out = {}
    for o in overrides:
        rx, ry, rz = (round(d * 10) * math.pi / 1800.0 for d in o.rotate)
        rot = (rio_make_r(rx, 0, 0) @ rio_make_r(0, ry, 0)) @ rio_make_r(0, 0, rz)
        out[o.bone] = rot @ skeleton.rest_local[o.bone][:3, :3]
    return out


@pytest.fixture(params=SKELETONS)
def skeleton(request):
    return Skeleton.load(request.param)


# --- conventions ---------------------------------------------------------------

def test_euler_roundtrip():
    rng = np.random.default_rng(0)
    for x, y, z in rng.uniform(-80, 80, size=(50, 3)):
        assert np.allclose(matrix_to_euler(euler_to_matrix(x, y, z)), (x, y, z), atol=1e-6)


def test_euler_matches_rio_single_axis_composition():
    x, y, z = 30.0, -20.0, 50.0
    r = np.radians([x, y, z])
    rio = rio_make_r(r[0], 0, 0) @ rio_make_r(0, r[1], 0) @ rio_make_r(0, 0, r[2])
    assert np.allclose(euler_to_matrix(x, y, z), rio)


def test_backend_reproduces_pose(skeleton):
    """Pose -> packed Euler overrides -> backend maths == Pose's own FK."""
    p = (Pose(skeleton).set(Joint.SHOULDER_L, 10, 20, 70).bend(Joint.ELBOW_L, 80)
         .set(Joint.SHOULDER_R, -30, 5, 40).bend(Joint.KNEE_R, 60)
         .set(Joint.NECK, 15, -25, 5).set(Joint.HIP_L, -45, 0, 10))
    expected = skeleton.forward(p.local_rotations())
    got = skeleton.forward(backend_local_rotations(skeleton, p.to_bone_overrides()))
    assert np.allclose(got[:, :3, 3], expected[:, :3, 3], atol=0.01 * skeleton.rest_world[14][1, 3])


def test_rest_pose_is_identity(skeleton):
    p = Pose(skeleton)
    assert p.to_bone_overrides() == []
    assert np.allclose(p.world_matrices(), skeleton.rest_world)


def test_body_axes():
    p = Pose()
    rest = p.world_positions()
    # +X is the Mii's left, +Y up.
    assert rest[Joint.SHOULDER_L][0] > 0 > rest[Joint.SHOULDER_R][0]
    assert rest[Joint.NECK][1] > rest[Joint.HIP_L][1]


# --- arms -----------------------------------------------------------------------

def test_t_pose_with_aim(skeleton):
    p = Pose(skeleton).aim(Joint.SHOULDER_L, [1, 0, 0]).aim(Joint.SHOULDER_R, [-1, 0, 0])
    pos = p.world_positions()
    assert angle_between(segment(pos, Joint.SHOULDER_L, Joint.ELBOW_L), [1, 0, 0]) < 0.5
    assert angle_between(segment(pos, Joint.SHOULDER_R, Joint.ELBOW_R), [-1, 0, 0]) < 0.5


def test_same_values_give_symmetric_pose(skeleton):
    p = Pose(skeleton)
    for side in ("L", "R"):
        p.set(Joint[f"SHOULDER_{side}"], 20, 10, 60).bend(Joint[f"ELBOW_{side}"], 70)
        p.set(Joint[f"HIP_{side}"], -30, 5, 0).bend(Joint[f"KNEE_{side}"], 45)
    pos = p.world_positions()
    size = skeleton.rest_world[14][1, 3]
    for left, right in [(Joint.WRIST_L, Joint.WRIST_R), (Joint.ELBOW_L, Joint.ELBOW_R),
                        (Joint.ANKLE_L, Joint.ANKLE_R), (Joint.KNEE_L, Joint.KNEE_R)]:
        assert np.allclose(pos[left], M @ pos[right], atol=0.02 * size)


def test_mirror(skeleton):
    p = Pose(skeleton).set(Joint.SHOULDER_L, 10, 30, 80).bend(Joint.KNEE_R, 90).set(Joint.NECK, 0, 30, 10)
    a, b = p.world_positions(), p.mirror().world_positions()
    size = skeleton.rest_world[14][1, 3]
    assert np.allclose(a[Joint.WRIST_L], M @ b[Joint.WRIST_R], atol=0.02 * size)
    assert np.allclose(a[Joint.ANKLE_R], M @ b[Joint.ANKLE_L], atol=0.02 * size)
    assert np.allclose(p.mirror().body_rotation(Joint.NECK), M @ p.body_rotation(Joint.NECK) @ M)


@pytest.mark.parametrize("side", ["L", "R"])
def test_elbow_bend_brings_hand_forward(skeleton, side):
    p = Pose(skeleton).bend(Joint[f"ELBOW_{side}"], 90)
    fore = segment(p.world_positions(), Joint[f"ELBOW_{side}"], Joint[f"WRIST_{side}"])
    rest = skeleton.rest_direction(Joint[f"ELBOW_{side}"])
    assert fore[2] > 0.9 * np.linalg.norm(fore)          # pointing forward
    assert abs(angle_between(fore, rest) - 90) < 0.5


@pytest.mark.parametrize("shoulder", [(0, 0, 0), (0, 0, 80), (60, 0, 0), (-40, 30, 20), (0, 90, 90)])
def test_elbow_bend_is_carried_by_shoulder(skeleton, shoulder):
    """The elbow angle depends only on the bend, not on how the arm is posed."""
    def elbow_angle(pose):
        pos = pose.world_positions()
        return angle_between(segment(pos, Joint.SHOULDER_L, Joint.ELBOW_L),
                             segment(pos, Joint.ELBOW_L, Joint.WRIST_L))
    base = elbow_angle(Pose(skeleton).bend(Joint.ELBOW_L, 60))
    posed = elbow_angle(Pose(skeleton).set(Joint.SHOULDER_L, *shoulder).bend(Joint.ELBOW_L, 60))
    assert abs(base - posed) < 0.1


def test_twist_keeps_direction_and_turns_bend_plane(skeleton):
    base = Pose(skeleton).aim(Joint.SHOULDER_L, [1, 0, 0])
    twisted = base.copy().twist(Joint.SHOULDER_L, -90)
    a, b = base.world_positions(), twisted.world_positions()
    assert np.allclose(a[Joint.ELBOW_L], b[Joint.ELBOW_L], atol=1e-6)   # still points +X
    up = twisted.bend(Joint.ELBOW_L, 90).world_positions()
    fore = segment(up, Joint.ELBOW_L, Joint.WRIST_L)
    assert fore[1] > 0.9 * np.linalg.norm(fore)                         # now bends upwards
    with pytest.raises(ValueError):
        Pose(skeleton).twist(Joint.ELBOW_L, 10)


# --- legs -----------------------------------------------------------------------

@pytest.mark.parametrize("side", ["L", "R"])
def test_knee_bend_moves_foot_back(skeleton, side):
    rest = Pose(skeleton).world_positions()
    p = Pose(skeleton).bend(Joint[f"KNEE_{side}"], 90)
    pos = p.world_positions()
    knee, ankle = Joint[f"KNEE_{side}"], Joint[f"ANKLE_{side}"]
    assert np.allclose(pos[knee], rest[knee])                   # thigh did not move
    shin = segment(pos, knee, ankle)
    assert shin[2] < -0.9 * np.linalg.norm(shin)               # shin points backwards
    assert pos[ankle][1] > rest[ankle][1]                      # foot lifted


def test_hip_flexion_lifts_leg_forward(skeleton):
    # Negative X about the body's left axis swings the leg forward.
    pos = Pose(skeleton).set(Joint.HIP_L, x=-90).world_positions()
    thigh = segment(pos, Joint.HIP_L, Joint.KNEE_L)
    assert thigh[2] > 0.9 * np.linalg.norm(thigh)


@pytest.mark.parametrize("side", ["L", "R"])
def test_aim_hinge(skeleton, side):
    knee = Joint[f"KNEE_{side}"]
    target = Pose(skeleton).bend(knee, 50).world_positions()
    p = Pose(skeleton).aim(knee, segment(target, knee, Joint[f"ANKLE_{side}"]))
    assert np.allclose(p.rotation(knee), Pose(skeleton).bend(knee, 50).rotation(knee), atol=1e-6)


# --- limits & interpolation -------------------------------------------------------

def hinge_angle(p, joint):
    pos = p.world_positions()
    end = {Joint.ELBOW_L: Joint.WRIST_L, Joint.KNEE_L: Joint.ANKLE_L}[joint]
    return angle_between(segment(pos, joint, end), p.skeleton.rest_direction(joint))


def test_clamp_hinges():
    p = Pose().bend(Joint.ELBOW_L, -30).bend(Joint.KNEE_L, 170).clamp()
    assert hinge_angle(p, Joint.ELBOW_L) < 0.1
    assert abs(hinge_angle(p, Joint.KNEE_L) - 150) < 0.1


def test_clamp_ball_joint():
    p = Pose().set(Joint.NECK, y=90).clamp()
    assert abs(abs(p.euler(Joint.NECK)[1]) - 60) < 0.1


def test_clamp_keeps_valid_pose():
    p = Pose().set(Joint.SHOULDER_L, 10, 20, 30).bend(Joint.ELBOW_L, 45)
    c = p.clamp()
    for j in (Joint.SHOULDER_L, Joint.ELBOW_L):
        assert np.allclose(c.rotation(j), p.rotation(j))


def test_lerp():
    a, b = Pose().bend(Joint.ELBOW_L, 0), Pose().bend(Joint.ELBOW_L, 90)
    assert abs(hinge_angle(a.lerp(b, 0.5), Joint.ELBOW_L) - 45) < 0.1


# --- packing ---------------------------------------------------------------------

def unpack_bones(settings):
    fmt = RenderSettings.STRUCT_FORMAT
    prefix = fmt[:fmt.index("75h")]
    start = len(struct.unpack(prefix, bytes(struct.calcsize(prefix))))
    fields = struct.unpack(fmt, settings.pack(bytes(96)))
    return np.array(fields[start:start + 75]).reshape(25, 3)


def test_pack_pose_and_explicit_bones_win():
    s = RenderSettings()
    s.pose = Pose().bend(Joint.ELBOW_L, 90).set(Joint.NECK, y=20)
    s.bones = [BoneOverride(Bone.HEAD, rotate=(0, 0, 5))]
    bones = unpack_bones(s)
    assert bones[Joint.ELBOW_L].any()
    assert tuple(bones[Bone.HEAD]) == (0, 0, 50)
    assert not bones[Joint.KNEE_L].any()


def test_pack_uses_body_skeleton():
    s = RenderSettings()
    s.pose = Pose(Skeleton.load("wiiu")).bend(Joint.ELBOW_L, 90)
    wiiu = unpack_bones(s)
    s.body_type = 1  # switch
    switch = unpack_bones(s)
    assert wiiu[Joint.ELBOW_L].any() and switch[Joint.ELBOW_L].any()
    assert not np.array_equal(wiiu, switch)   # conversion used each body's rest frames


@pytest.mark.parametrize("root,end,target", [
    (Joint.SHOULDER_L, Joint.WRIST_L, [3.5, 10, 2]), (Joint.SHOULDER_R, Joint.WRIST_R, [-2, 13, 1]),
    (Joint.HIP_L, Joint.ANKLE_L, [1, 3, 2.5]), (Joint.HIP_R, Joint.ANKLE_R, [-1.5, 1.5, -1.5])])
def test_reach_puts_hand_or_foot_on_target(root, end, target):
    pose = Pose().reach(root, target)
    assert np.allclose(pose.world_positions()[end], target, atol=0.01)


def test_reach_out_of_range_gets_as_close_as_possible():
    pose = Pose().reach(Joint.SHOULDER_L, [9, 9, 0])
    pos = pose.world_positions()
    to_hand = pos[Joint.WRIST_L] - pos[Joint.SHOULDER_L]
    assert angle_between(to_hand, np.array([9, 9, 0]) - pos[Joint.SHOULDER_L]) < 1.0


def test_pose_dict_roundtrip():
    pose = Pose().bend(Joint.ELBOW_L, 70).set(Joint.NECK, y=20).reach(Joint.HIP_R, [-1.5, 2, 1.5])
    again = Pose.from_dict(pose.to_dict())
    for j in Joint:
        assert np.allclose(again.rotation(j), pose.rotation(j))


def hip_swing(pose, joint):
    """Thigh direction's forward and outward angles (degrees) in body space."""
    pos = pose.world_positions()
    d = pos[{Joint.HIP_L: Joint.KNEE_L, Joint.HIP_R: Joint.KNEE_R}[joint]] - pos[joint]
    side = d[0] if joint == Joint.HIP_L else -d[0]
    return math.degrees(math.atan2(d[2], -d[1])), math.degrees(math.atan2(side, -d[1]))


@pytest.mark.parametrize("side", ["L", "R"])
def test_hip_cannot_go_far_back_or_cross_over(side):
    hip = Joint[f"HIP_{side}"]
    rest_fwd, rest_out = hip_swing(Pose(), hip)
    back, _ = hip_swing(Pose().set(hip, x=80).clamp(), hip)
    # limits act on the swing rotation, so projected angles land within a few degrees
    assert back - rest_fwd > -33                      # extension stops at ~30 degrees
    _, inward = hip_swing(Pose().set(hip, z=-60 if side == "L" else 60).clamp(), hip)
    assert inward - rest_out > -23                     # adduction stops at ~20 degrees


def test_hip_forward_and_outward_are_free():
    for p in (Pose().set(Joint.HIP_L, x=-90), Pose().set(Joint.HIP_L, z=45),
              Pose().set(Joint.HIP_L, x=-60, z=30)):
        assert np.allclose(p.clamp().rotation(Joint.HIP_L), p.rotation(Joint.HIP_L), atol=1e-6)


def test_chest_lean_limits():
    c = Pose().set(Joint.CHEST, z=40).clamp()
    assert abs(abs(math.degrees(math.asin(c.body_rotation(Joint.CHEST)[0, 1]))) - 25) < 0.5
    assert np.allclose(Pose().set(Joint.CHEST, x=30).clamp().rotation(Joint.CHEST),
                       Pose().set(Joint.CHEST, x=30).rotation(Joint.CHEST), atol=1e-6)


def test_waist_seam_follows_chest():
    p = Pose().set(Joint.CHEST, z=20)
    overrides = {o.bone: o.rotate for o in p.to_bone_overrides()}
    assert 15 in overrides and abs(overrides[15][2] - 10) < 0.5
