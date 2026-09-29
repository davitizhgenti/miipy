"""
pose_editor.py — Pose a Mii's body with the mouse.

Left panel: a draggable skeleton (front or side view) with the collision
shapes. Right panel: the live Mii render of the same pose.

Drag the handles:
  hands / feet   move them anywhere (two-bone IK through the elbow/knee)
  elbows / knees swing the upper arm / thigh, keeping the bend
  head           tilt (front view) or nod (side view)
  chest          lean the upper body

Keys:
  F  front / side view        C  collisions on/off     Y  symmetric editing
  A / D  turn head            Z / X  twist torso       M  mirror pose
  R  reset                    +/-  expression          S  save pose (.json + .png)
  Q  quit

Usage: python examples/pose_editor.py [path/to/mii.ffsd]
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import MiiPy, ViewType, Expression, Joint, Pose  # noqa: E402
from mii.collision import CollisionModel, HEAD  # noqa: E402
from mii.rig import euler_to_matrix, shortest_arc  # noqa: E402

PANEL = 540
SCALE = (PANEL - 60) / 21.0          # pixels per skeleton unit (feet to top of head ~ 20.5)
FLOOR = PANEL - 30                   # screen y of the skeleton's y = 0
EXPRESSIONS = [Expression.NORMAL, Expression.SMILE, Expression.BIG_SMILE, Expression.SURPRISE,
               Expression.ANGER, Expression.SORROW, Expression.CHEERFUL, Expression.LOVE]
EXPRESSION_NAMES = {v: k for k, v in vars(Expression).items() if k.isupper()}

# Handle name -> (kind, joint that moves, bone the handle sits on)
HANDLES = {
    "hand_L": ("reach", Joint.SHOULDER_L, Joint.WRIST_L),
    "hand_R": ("reach", Joint.SHOULDER_R, Joint.WRIST_R),
    "foot_L": ("reach", Joint.HIP_L, Joint.ANKLE_L),
    "foot_R": ("reach", Joint.HIP_R, Joint.ANKLE_R),
    "elbow_L": ("aim", Joint.SHOULDER_L, Joint.ELBOW_L),
    "elbow_R": ("aim", Joint.SHOULDER_R, Joint.ELBOW_R),
    "knee_L": ("aim", Joint.HIP_L, Joint.KNEE_L),
    "knee_R": ("aim", Joint.HIP_R, Joint.KNEE_R),
    "head": ("look", Joint.NECK, "head"),
    "chest": ("look", Joint.CHEST, Joint.NECK),
}
LIMB_JOINTS = {"L": [Joint.SHOULDER_L, Joint.ELBOW_L, Joint.WRIST_L, Joint.HIP_L, Joint.KNEE_L, Joint.ANKLE_L],
               "R": [Joint.SHOULDER_R, Joint.ELBOW_R, Joint.WRIST_R, Joint.HIP_R, Joint.KNEE_R, Joint.ANKLE_R]}


class Editor:
    def __init__(self, renderer, mii):
        self.pose = Pose()                     # what the user asked for
        self.collisions = CollisionModel.load("wiiu")
        self.side = False
        self.collide = True
        self.symmetric = False
        self.expr = 0
        self.drag = None
        self.hover = None
        self.anim = renderer.animate(mii, size=PANEL, view=ViewType.ALL_BODY,
                                     bg_color=(235, 235, 235, 255))
        self.render_img = None
        self.dirty = True
        self._shown = None
        self.saved = 0

    # --- pose shown = clamped and (optionally) collision-free -------------------

    def shown(self):
        if self._shown is None:
            pose = self.pose.clamp()
            self._shown = self.collisions.resolve(pose) if self.collide else pose
        return self._shown

    def changed(self):
        self._shown = None
        self.dirty = True

    # --- projection (orthographic: front shows X/Y, side shows Z/Y) -----------

    def to_screen(self, p):
        h = p[2] if self.side else p[0]
        return int(PANEL / 2 + h * SCALE), int(FLOOR - p[1] * SCALE)

    def from_screen(self, x, y, keep):
        """3D point under the mouse, keeping `keep`'s depth coordinate."""
        p = np.array(keep, dtype=float)
        h = (x - PANEL / 2) / SCALE
        if self.side:
            p[2] = h
        else:
            p[0] = h
        p[1] = (FLOOR - y) / SCALE
        return p

    def handle_positions(self, world):
        out = {}
        for name, (_, _, bone) in HANDLES.items():
            if bone == "head":  # centre of the head collider (not a bone origin)
                cap = self.collisions.capsules[HEAD]
                out[name] = cap.world(world)[0]
            else:
                out[name] = world[bone][:3, 3]
        return out

    # --- editing ----------------------------------------------------------------

    def apply_drag(self, name, x, y):
        kind, joint, bone = HANDLES[name]
        world = self.pose.world_matrices()
        current = self.handle_positions(world)[name]
        target = self.from_screen(x, y, current)
        if kind == "reach":
            self.pose.reach(joint, target)
        elif kind == "aim":
            self.pose.aim(joint, target - world[joint][:3, 3])
        else:  # look: rotate NECK/CHEST so the head/neck points at the mouse
            sk = self.pose.skeleton
            parent = sk.parents[joint]
            pivot = world[joint][:3, 3]
            rest_dir = self.handle_positions(sk.rest_world)[name] - sk.rest_world[joint][:3, 3]
            carried = world[parent][:3, :3] @ sk.rest_world[parent][:3, :3].T
            twist = self._twist(joint)
            aim = shortest_arc(rest_dir, carried.T @ (target - pivot))
            self.pose.set_rotation(joint, aim @ twist)
        if self.symmetric and name[-2:] in ("_L", "_R"):
            src, dst = ("L", "R") if name.endswith("_L") else ("R", "L")
            for a, b in zip(LIMB_JOINTS[src], LIMB_JOINTS[dst]):
                self.pose.set_rotation(b, self.pose.rotation(a))  # stored mirrored already
        self.changed()

    def _twist(self, joint):
        """Keep the head/torso turn (Y rotation) while re-aiming it."""
        y = self.pose.euler(joint)[1]
        return euler_to_matrix(0, y, 0)

    def turn(self, joint, degrees):
        self.pose.set_rotation(joint, self.pose.rotation(joint) @ euler_to_matrix(0, degrees, 0))
        self.changed()

    # --- drawing ------------------------------------------------------------------

    def draw_skeleton(self, shown):
        img = np.full((PANEL, PANEL, 3), 250, np.uint8)
        world = shown.world_matrices()
        # collision shapes; red where the requested pose would intersect
        hits = {b for a, b2, _ in self.collisions.contacts(self.pose.clamp()) for b in (a, b2)}
        for bone, cap in self.collisions.capsules.items():
            a, b = (self.to_screen(p) for p in cap.world(world))
            color = (170, 170, 235) if bone in hits else (215, 215, 215)
            r = max(1, int(cap.radius * SCALE))
            cv2.line(img, a, b, color, 2 * r, cv2.LINE_AA)
            cv2.circle(img, a, r, color, -1, cv2.LINE_AA)
            cv2.circle(img, b, r, color, -1, cv2.LINE_AA)
        # bones
        sk = shown.skeleton
        for bone, parent in enumerate(sk.parents):
            if parent >= 2:
                cv2.line(img, self.to_screen(world[parent][:3, 3]), self.to_screen(world[bone][:3, 3]),
                         (90, 90, 90), 2, cv2.LINE_AA)
        # handles
        for name, p in self.handle_positions(world).items():
            active = name in (self.drag, self.hover)
            # OpenCV colours are BGR: blue = Mii's left, orange = Mii's right
            color = (230, 120, 40) if name.endswith("_L") else (40, 140, 240) if name.endswith("_R") else (60, 170, 60)
            cv2.circle(img, self.to_screen(p), 11 if active else 8, color, -1, cv2.LINE_AA)
            cv2.circle(img, self.to_screen(p), 11 if active else 8, (40, 40, 40), 1, cv2.LINE_AA)
        lines = [f"{'SIDE' if self.side else 'FRONT'} view  |  collisions {'ON' if self.collide else 'off'}"
                 f"  |  symmetric {'ON' if self.symmetric else 'off'}",
                 "drag handles   F view  C collide  Y sym  A/D head  Z/X torso",
                 "M mirror  R reset  +/- expr  S save  Q quit"]
        for i, t in enumerate(lines):
            cv2.putText(img, t, (8, 18 + 16 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (30, 30, 30), 1, cv2.LINE_AA)
        cv2.putText(img, "L = Mii's left (blue)   R = Mii's right (orange)", (8, PANEL - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1, cv2.LINE_AA)
        return img

    def frame(self):
        shown = self.shown()
        if self.dirty or self.render_img is None:
            mii = self.anim.frame(pose=shown, model_rot=(0, 90, 0) if self.side else (0, 0, 0),
                                  expression=EXPRESSIONS[self.expr])
            self.render_img = cv2.cvtColor(np.asarray(mii.convert("RGB")), cv2.COLOR_RGB2BGR)
            self.dirty = False
        view = np.hstack([self.draw_skeleton(shown), self.render_img])
        cv2.putText(view, EXPRESSION_NAMES.get(EXPRESSIONS[self.expr], ""), (PANEL + 8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1, cv2.LINE_AA)
        return view

    # --- input ----------------------------------------------------------------------

    def on_mouse(self, event, x, y, flags, _):
        if x >= PANEL:
            return
        world = self.shown().world_matrices()
        near = min(((np.hypot(*(np.subtract(self.to_screen(p), (x, y)))), n)
                    for n, p in self.handle_positions(world).items()), default=(1e9, None))
        self.hover = near[1] if near[0] < 14 else None
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drag = self.hover
        elif event == cv2.EVENT_LBUTTONUP:
            self.drag = None
        elif event == cv2.EVENT_MOUSEMOVE and self.drag:
            self.apply_drag(self.drag, x, y)

    def on_key(self, key):
        if key == ord("f"):
            self.side = not self.side
        elif key == ord("c"):
            self.collide = not self.collide
        elif key == ord("y"):
            self.symmetric = not self.symmetric
        elif key == ord("m"):
            self.pose = self.pose.mirror()
        elif key == ord("r"):
            self.pose = Pose()
        elif key in (ord("a"), ord("d")):
            self.turn(Joint.NECK, 10 if key == ord("a") else -10)
        elif key in (ord("z"), ord("x")):
            self.turn(Joint.CHEST, 10 if key == ord("z") else -10)
        elif key in (ord("+"), ord("=")):
            self.expr = (self.expr + 1) % len(EXPRESSIONS)
        elif key == ord("-"):
            self.expr = (self.expr - 1) % len(EXPRESSIONS)
        elif key == ord("s"):
            self.save()
        else:
            return
        self.changed()

    def save(self):
        name = f"pose_{self.saved:03d}"
        with open(name + ".json", "w") as f:
            json.dump(self.shown().to_dict(), f, indent=1)
        cv2.imwrite(name + ".png", self.render_img)
        print(f"saved {name}.json / {name}.png   (load with Pose.from_dict(json.load(open(...))))")
        self.saved += 1


def window_open(name):
    # Closing the window with its X button makes some OpenCV backends (Qt)
    # raise here instead of reporting it as hidden.
    try:
        return cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


def main():
    mii = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "tests", "data", "dato.ffsd")
    with MiiPy() as renderer:
        editor = Editor(renderer, mii)
        cv2.namedWindow("Mii Pose Editor")
        cv2.setMouseCallback("Mii Pose Editor", editor.on_mouse)
        while True:
            cv2.imshow("Mii Pose Editor", editor.frame())
            key = cv2.waitKey(15) & 0xFF
            if key == ord("q") or not window_open("Mii Pose Editor"):
                break
            if key != 255:
                editor.on_key(key)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
