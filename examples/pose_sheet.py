"""
pose_sheet.py — Render canonical poses (front + side view) into one PNG
for reviewing that joints bend correctly.

Usage: python examples/pose_sheet.py path/to/mii.ffsd [out.png] [--body switch]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import MiiPy, ViewType, Joint, Pose, Skeleton  # noqa: E402

BODY_TYPES = {"wiiu": 0, "switch": 1}


def both(pose, fn):
    """Apply fn(pose, side) for both sides; same values = symmetric."""
    for side in "LR":
        fn(pose, side)
    return pose


def wave(pose):
    # Twist the upper arm so the elbow bends upwards instead of forwards.
    return (pose.aim(Joint.SHOULDER_L, [1, 0.3, 0]).twist(Joint.SHOULDER_L, -95)
            .bend(Joint.ELBOW_L, 100).set(Joint.WRIST_L, z=20))


def poses(skeleton):
    P = lambda: Pose(skeleton)  # noqa: E731
    return [
        ("rest", P()),
        ("T-pose", P().aim(Joint.SHOULDER_L, [1, 0, 0]).aim(Joint.SHOULDER_R, [-1, 0, 0])),
        ("arms up", P().aim(Joint.SHOULDER_L, [0.15, 1, 0]).aim(Joint.SHOULDER_R, [-0.15, 1, 0])),
        ("arms forward", P().aim(Joint.SHOULDER_L, [0.1, 0, 1]).aim(Joint.SHOULDER_R, [-0.1, 0, 1])),
        ("elbows 90", both(P(), lambda p, s: p.bend(Joint[f"ELBOW_{s}"], 90))),
        ("wave (L)", wave(P())),
        ("hands on hips", both(P(), lambda p, s: p.set(Joint[f"SHOULDER_{s}"], z=15)
                              .twist(Joint[f"SHOULDER_{s}"], 80).bend(Joint[f"ELBOW_{s}"], 60))),
        ("knee bend (L)", P().set(Joint.HIP_L, x=-50).bend(Joint.KNEE_L, 90)),
        ("sit", both(P(), lambda p, s: p.set(Joint[f"HIP_{s}"], x=-90).bend(Joint[f"KNEE_{s}"], 90))),
        ("walk", P().set(Joint.HIP_L, x=-30).bend(Joint.KNEE_L, 20).set(Joint.HIP_R, x=25)
                    .bend(Joint.KNEE_R, 40).set(Joint.SHOULDER_L, x=30).set(Joint.SHOULDER_R, x=-30)
                    .bend(Joint.ELBOW_L, 20).bend(Joint.ELBOW_R, 20)),
        ("head turn+tilt", P().set(Joint.NECK, y=40, z=15)),
        ("lean + twist", P().set(Joint.CHEST, x=20, y=25)),
        ("mirror of wave", wave(P()).mirror()),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mii")
    ap.add_argument("out", nargs="?", default="pose_sheet.png")
    ap.add_argument("--body", choices=BODY_TYPES, default="wiiu")
    ap.add_argument("--size", type=int, default=256)
    args = ap.parse_args()

    skeleton = Skeleton.load(args.body)
    items = poses(skeleton)
    cell, label_h = args.size, 18
    sheet = Image.new("RGB", (cell * 2 * 4, (cell + label_h) * ((len(items) + 3) // 4)), "white")
    draw = ImageDraw.Draw(sheet)

    with MiiPy() as r:
        for i, (name, pose) in enumerate(items):
            x0 = (i % 4) * cell * 2
            y0 = (i // 4) * (cell + label_h)
            for k, rot in enumerate([(0, 0, 0), (0, 90, 0)]):
                img = r.render(args.mii, size=cell, view=ViewType.ALL_BODY, model_rot=rot,
                               body_type=BODY_TYPES[args.body], pose=pose,
                               bg_color=(255, 255, 255, 255))
                sheet.paste(img.convert("RGB"), (x0 + k * cell, y0 + label_h))
            draw.text((x0 + 4, y0 + 3), f"{name}  (front | side)", fill="black")
    sheet.save(args.out)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
