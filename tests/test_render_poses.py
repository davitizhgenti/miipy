"""Golden-image regression for posed full-body renders (needs the backend).

Regenerate goldens after an intended change:
    MIIPY_UPDATE_GOLDEN=1 pytest tests/test_render_poses.py
"""
import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import Joint, Pose, ViewType  # noqa: E402
from mii.assets import AssetManager  # noqa: E402

HERE = os.path.dirname(__file__)
GOLDEN = os.path.join(HERE, "golden")
MII = os.path.join(HERE, "data", "dato.ffsd")
ROOT = os.path.join(HERE, "..")

have_backend = (AssetManager(ROOT).get_binary_path() and AssetManager(ROOT).get_resource_path()
                and os.path.exists(MII))
pytestmark = pytest.mark.skipif(not have_backend, reason="backend binary / FFLResHigh.dat / Mii missing")

POSES = {
    "rest": lambda: Pose(),
    "tpose": lambda: Pose().aim(Joint.SHOULDER_L, [1, 0, 0]).aim(Joint.SHOULDER_R, [-1, 0, 0]),
    "elbows90": lambda: Pose().bend(Joint.ELBOW_L, 90).bend(Joint.ELBOW_R, 90),
    "knee90": lambda: Pose().set(Joint.HIP_L, x=-50).bend(Joint.KNEE_L, 90),
    "neck": lambda: Pose().set(Joint.NECK, y=30, z=10),
}
VIEWS = {"front": (0, 0, 0), "side": (0, 90, 0)}


@pytest.fixture(scope="module")
def renderer():
    from mii import MiiPy
    with MiiPy() as r:
        yield r


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("name", POSES)
def test_pose_matches_golden(renderer, name, view):
    img = renderer.render(MII, size=192, view=ViewType.ALL_BODY, model_rot=VIEWS[view],
                          pose=POSES[name](), bg_color=(255, 255, 255, 255)).convert("RGB")
    path = os.path.join(GOLDEN, f"{name}_{view}.png")
    if os.environ.get("MIIPY_UPDATE_GOLDEN") or not os.path.exists(path):
        os.makedirs(GOLDEN, exist_ok=True)
        img.save(path)
        pytest.skip(f"wrote golden {path}")
    diff = np.abs(np.asarray(img, dtype=int) - np.asarray(Image.open(path).convert("RGB"), dtype=int))
    changed = (diff.max(axis=2) > 40).mean()
    assert changed < 0.005, f"{changed:.2%} of pixels differ from {path}"


def test_pose_changes_image(renderer):
    kw = dict(size=128, view=ViewType.ALL_BODY, bg_color=(255, 255, 255, 255))
    a = np.asarray(renderer.render(MII, pose=Pose(), **kw))
    b = np.asarray(renderer.render(MII, pose=POSES["tpose"](), **kw))
    assert (a != b).any()
