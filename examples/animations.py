"""
animations.py — Render a few looping full-body animations to GIFs.

Usage: python examples/animations.py path/to/mii.ffsd [out_dir]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import MiiPy, ViewType, Expression, Joint, Pose  # noqa: E402
from mii.animation import Clip, render_frames, save_gif, wave  # noqa: E402


def walk(t):
    s = wave(t)
    p = Pose()
    for side, sign in (("L", 1), ("R", -1)):
        leg = sign * s                       # +1 = this leg forward
        p.set(Joint[f"HIP_{side}"], x=-28 * leg)
        # Knee bends most while the leg swings through (moving forward).
        swing = sign * wave(t + 0.25)
        p.bend(Joint[f"KNEE_{side}"], 8 + 40 * max(0.0, swing))
        p.set(Joint[f"SHOULDER_{side}"], x=25 * leg)   # arms opposite to legs
        p.bend(Joint[f"ELBOW_{side}"], 20)
    p.set(Joint.CHEST, y=6 * s)
    return p


def hello_wave(t):
    s = wave(t * 2)  # two waves per loop
    return (Pose()
            .aim(Joint.SHOULDER_L, [1, 0.1, 0.3]).twist(Joint.SHOULDER_L, -95)
            .bend(Joint.ELBOW_L, 45 + 25 * s).set(Joint.WRIST_L, z=15 * s)
            .set(Joint.NECK, z=-6, y=10))


def jumping_jacks():
    closed = Pose()
    arms_up = Pose()
    for side, sx in (("L", 1), ("R", -1)):
        arms_up.aim(Joint[f"SHOULDER_{side}"], [0.35 * sx, 1, 0])
        arms_up.set(Joint[f"HIP_{side}"], z=22)
    return Clip([(0.0, closed), (0.5, arms_up)])


def dance(t):
    s, c = wave(t * 2), wave(t * 2 + 0.25)
    p = Pose().set(Joint.CHEST, y=15 * s, z=5 * c).set(Joint.NECK, z=12 * c)
    for side, sign in (("L", 1), ("R", -1)):
        up = max(0.0, sign * s)
        p.aim(Joint[f"SHOULDER_{side}"], [sign, -0.3 + 0.5 * up, 0.15])
        p.twist(Joint[f"SHOULDER_{side}"], -90 * up)
        p.bend(Joint[f"ELBOW_{side}"], 25 + 20 * up)
        p.set(Joint[f"HIP_{side}"], x=-10 * max(0.0, -sign * s))
        p.bend(Joint[f"KNEE_{side}"], 5 + 20 * max(0.0, -sign * s))
    return p


ANIMATIONS = {
    # name: (animation, frames, view rotation, expression)
    "walk":          (walk,             24, (0, 60, 0), Expression.NORMAL),
    "wave":          (hello_wave,       24, (0, 0, 0),  Expression.SMILE),
    "jumping_jacks": (jumping_jacks(),  20, (0, 0, 0),  Expression.BIG_SMILE),
    "dance":         (dance,            32, (0, 20, 0), Expression.CHEERFUL),
}


def main():
    mii = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(out_dir, exist_ok=True)
    with MiiPy() as r:
        for name, (animation, frames, rot, expr) in ANIMATIONS.items():
            ctx = r.animate(mii, size=320, view=ViewType.ALL_BODY, model_rot=rot, expression=expr)
            path = os.path.join(out_dir, f"{name}.gif")
            save_gif(render_frames(ctx, animation, frames), path, fps=16)
            print(f"saved {path}")


if __name__ == "__main__":
    main()
