# mii/animation.py
"""
Pose animation helpers: keyframe clips and GIF export.

An animation is anything that maps a phase t in [0, 1) to a Pose: either a
`Clip` of keyframes or a plain function (handy for cyclic motion like walking).
"""
import math

from .rig import Pose


def smoothstep(x):
    return x * x * (3 - 2 * x)


class Clip:
    """Keyframed poses. keyframes: [(time, Pose), ...] with times in [0, 1].

    With loop=True the last keyframe blends back into the first.
    """

    def __init__(self, keyframes, loop=True, ease=smoothstep):
        self.keyframes = sorted(keyframes, key=lambda k: k[0])
        self.loop = loop
        self.ease = ease

    def __call__(self, t):
        keys = self.keyframes
        if self.loop:
            t %= 1.0
            keys = keys + [(keys[0][0] + 1.0, keys[0][1])]
        else:
            t = min(max(t, keys[0][0]), keys[-1][0])
        for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                x = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return p0.lerp(p1, self.ease(x))
        return keys[-1][1].copy()


def render_frames(anim_ctx, animation, frames, **frame_kwargs):
    """Render `frames` evenly spaced poses of `animation` with an AnimationContext."""
    return [anim_ctx.frame(pose=animation(i / frames), **frame_kwargs) for i in range(frames)]


def save_gif(images, path, fps=24, background=(255, 255, 255)):
    """Save RGBA frames as a looping GIF (flattened onto `background`)."""
    from PIL import Image
    flat = []
    for img in images:
        bg = Image.new("RGB", img.size, background)
        bg.paste(img, mask=img.getchannel("A") if img.mode == "RGBA" else None)
        flat.append(bg)
    flat[0].save(path, save_all=True, append_images=flat[1:], loop=0,
                 duration=round(1000 / fps), disposal=2)


def wave(t):
    """Phase-based helper: sine wave in [-1, 1]."""
    return math.sin(2 * math.pi * t)


__all__ = ["Clip", "Pose", "render_frames", "save_gif", "smoothstep", "wave"]
