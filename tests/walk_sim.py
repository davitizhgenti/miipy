"""
walk_sim.py — Walk a Mii around with WASD (interactive, needs pygame).

The Mii walks with a procedural gait (hips, knees, arm swing, torso sway,
body bob) whose speed matches the ground scrolling under its feet, turns
towards the direction you steer, and eases into an idle stance when you
stop. The camera follows it over a checkerboard field with trees.

Controls:
  W A S D   walk (away / left / towards / right on screen)
  Shift     run
  Q / Esc   quit

Usage: python tests/walk_sim.py [path/to/mii.ffsd]
"""
import math
import os
import random
import sys

import numpy as np

try:
    import pygame
except ImportError:
    sys.exit("walk_sim needs pygame: pip install pygame")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import MiiPy, ViewType, Expression, Joint, Pose  # noqa: E402

W, H = 960, 640
MII_SIZE = 380                   # render resolution of the Mii
FEET_Y = H - 90                  # screen row where the Mii stands
CAM_HEIGHT = 9.0                 # camera height above the ground (skeleton units)
CAM_DIST = 34.0                  # camera distance to the Mii
TURN_SPEED = math.radians(420)   # heading change per second
TILE = 4.0                       # checkerboard tile size
TREE_RADIUS = 1.6                # trunk + the Mii's own width: trees are solid
NEAR_CLIP = 8.0                  # don't draw scenery closer to the camera than this


# --- gait --------------------------------------------------------------------------

def gait(t, run=0.0):
    """Walk (run=0) to run (run=1) cycle at phase t in [0, 1)."""
    s = math.sin(2 * math.pi * t)
    hip = 26 + 14 * run
    p = Pose()
    for side, sign in (("L", 1), ("R", -1)):
        leg = sign * s                                   # +1 = this leg forward
        swing = sign * math.sin(2 * math.pi * (t + 0.25))  # > 0 while the leg swings forward
        p.set(Joint[f"HIP_{side}"], x=-hip * leg)
        p.bend(Joint[f"KNEE_{side}"], 6 + (38 + 40 * run) * max(0.0, swing) + 10 * run)
        p.set(Joint[f"SHOULDER_{side}"], x=(24 + 20 * run) * leg)  # arms opposite the legs
        p.bend(Joint[f"ELBOW_{side}"], 15 + 55 * run)
    p.set(Joint.CHEST, x=4 + 10 * run, y=6 * s)          # lean in, sway with the stride
    p.set(Joint.NECK, x=-3 - 8 * run, y=-4 * s)          # keep looking ahead
    return p


def stride_and_bob(run):
    """Ground covered per cycle and body height per phase, measured by FK.

    The standing foot moves backwards at walking speed, so the distance per
    cycle is twice the stance foot's travel; the body is lowered so the
    lowest foot stays on the ground.
    """
    ts = np.linspace(0, 1, 64, endpoint=False)
    ankles = [gait(t, run).world_positions() for t in ts]
    z = np.array([a[Joint.ANKLE_L][2] for a in ankles])
    low = np.array([min(a[Joint.ANKLE_L][1], a[Joint.ANKLE_R][1]) for a in ankles])
    rest_low = min(Pose().world_positions()[Joint.ANKLE_L][1], Pose().world_positions()[Joint.ANKLE_R][1])
    return 2 * (z.max() - z.min()), ts, low - rest_low


# --- world ---------------------------------------------------------------------------

class Camera:
    """Pinhole camera looking along -Z at the Mii from CAM_DIST away."""

    def __init__(self, px_per_unit):
        self.f = px_per_unit * CAM_DIST
        self.horizon = FEET_Y - px_per_unit * CAM_HEIGHT

    def project(self, x, z, focus, y=0.0):
        depth = CAM_DIST - (z - focus[1])
        if depth < 1.0:
            return None
        return (W / 2 + self.f * (x - focus[0]) / depth,
                self.horizon + self.f * (CAM_HEIGHT - y) / depth, depth)


def draw_ground(screen, cam, focus):
    screen.fill((150, 200, 245))
    pygame.draw.rect(screen, (120, 180, 95), (0, cam.horizon, W, H))
    cx, cz = int(focus[0] // TILE), int(focus[1] // TILE)
    for j in range(cz - 40, cz + 9):
        for i in range(cx - 16, cx + 17):
            corners = [cam.project(i * TILE + dx, j * TILE + dz, focus)
                       for dx, dz in ((0, 0), (TILE, 0), (TILE, TILE), (0, TILE))]
            if None in corners:
                continue
            color = (132, 196, 104) if (i + j) % 2 else (116, 178, 90)
            pygame.draw.polygon(screen, color, [c[:2] for c in corners])


def draw_tree(screen, cam, focus, x, z):
    base = cam.project(x, z, focus)
    top = cam.project(x, z, focus, y=11.0)
    if base is None or top is None or base[2] < NEAR_CLIP:
        return
    s = cam.f / base[2]
    pygame.draw.line(screen, (110, 75, 45), base[:2], top[:2], max(2, int(0.9 * s)))
    pygame.draw.circle(screen, (60, 130, 60), (int(top[0]), int(top[1])), max(3, int(4.0 * s)))
    pygame.draw.circle(screen, (80, 155, 75), (int(top[0] - s), int(top[1] - s)), max(2, int(2.6 * s)))


def draw_minimap(screen, pos, heading, trail, trees):
    size, scale = 150, 1.2
    ox, oy = W - size - 12, 12
    pygame.draw.rect(screen, (235, 240, 230), (ox, oy, size, size))
    pygame.draw.rect(screen, (60, 60, 60), (ox, oy, size, size), 1)
    to_map = lambda x, z: (ox + size / 2 + (x - pos[0]) * scale, oy + size / 2 + (z - pos[1]) * scale)  # noqa: E731
    for x, z in trees:
        mx, my = to_map(x, z)
        if ox < mx < ox + size and oy < my < oy + size:
            pygame.draw.circle(screen, (70, 140, 70), (int(mx), int(my)), 3)
    pts = [to_map(x, z) for x, z in trail]
    pts = [p for p in pts if ox < p[0] < ox + size and oy < p[1] < oy + size]
    if len(pts) > 1:
        pygame.draw.lines(screen, (220, 120, 40), False, pts, 2)
    c = (ox + size / 2, oy + size / 2)
    tip = (c[0] + 9 * math.sin(heading), c[1] + 9 * math.cos(heading))
    pygame.draw.circle(screen, (40, 90, 220), c, 5)
    pygame.draw.line(screen, (40, 90, 220), c, tip, 3)


# --- main loop --------------------------------------------------------------------------

def main():
    mii = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "data", "dato.ffsd")
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Mii walk  -  WASD to walk, Shift to run")
    font = pygame.font.SysFont(None, 22)
    clock = pygame.time.Clock()

    walk_stride, phases, walk_bob = stride_and_bob(0.0)
    run_stride, _, run_bob = stride_and_bob(1.0)
    random.seed(4)
    trees = [(random.uniform(-80, 80), random.uniform(-80, 80)) for _ in range(70)]

    with MiiPy() as renderer:
        anim = renderer.animate(mii, size=MII_SIZE, view=ViewType.ALL_BODY, bg_color=(0, 0, 0, 0))
        rest = np.asarray(anim.frame(pose=Pose()))
        rows = np.where(rest[:, :, 3].any(axis=1))[0]
        feet_row, top_row = rows[-1], rows[0]
        px_per_unit = (feet_row - top_row) / 20.4       # feet to top of head ~ 20.4 units
        cam = Camera(px_per_unit)

        pos = np.zeros(2)          # (x, z) on the ground; +z points at the camera
        heading = 0.0              # 0 = facing the camera
        phase, amount, speed_now = 0.0, 0.0, 0.0
        trail = [tuple(pos)]
        running = True
        while running:
            dt = min(clock.tick(60) / 1000.0, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN
                                                 and event.key in (pygame.K_q, pygame.K_ESCAPE)):
                    running = False
            keys = pygame.key.get_pressed()
            move = np.array([keys[pygame.K_d] - keys[pygame.K_a], keys[pygame.K_s] - keys[pygame.K_w]], float)
            run = 1.0 if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] else 0.0

            # Turn towards the steering direction, then walk once roughly facing it.
            moving = np.linalg.norm(move) > 0
            if moving:
                target = math.atan2(move[0], move[1])
                diff = (target - heading + math.pi) % (2 * math.pi) - math.pi
                heading += max(-TURN_SPEED * dt, min(TURN_SPEED * dt, diff))
                facing = max(0.0, math.cos(diff))
            else:
                facing = 0.0
            amount += ((1.0 if moving else 0.0) - amount) * min(1.0, dt * 6)   # ease in/out of the gait
            stride = walk_stride + (run_stride - walk_stride) * run
            cadence = 0.95 + 0.55 * run                                        # cycles per second
            target_speed = stride * cadence * facing * (1.0 if moving else 0.0)
            speed_now += (target_speed - speed_now) * min(1.0, dt * 8)
            if amount > 0.01:
                phase = (phase + cadence * dt * max(amount, 0.2)) % 1.0
            pos += speed_now * dt * np.array([math.sin(heading), math.cos(heading)])
            for tree in trees:  # slide around trees instead of walking through them
                away = pos - tree
                d = np.linalg.norm(away)
                if 1e-6 < d < TREE_RADIUS:
                    pos = np.array(tree) + away / d * TREE_RADIUS
            if np.linalg.norm(pos - np.array(trail[-1])) > 0.8:
                trail = (trail + [tuple(pos)])[-400:]

            pose = Pose().lerp(gait(phase, run), amount)
            bob = np.interp(phase, phases, walk_bob + (run_bob - walk_bob) * run, period=1.0) * amount
            img = anim.frame(pose=pose, model_rot=(0, int(math.degrees(heading)), 0),
                             expression=Expression.SMILE if moving else Expression.NORMAL)

            # draw: ground, trees behind the Mii, Mii, trees in front, HUD
            draw_ground(screen, cam, pos)
            order = sorted(trees, key=lambda t: t[1])
            for x, z in order:
                if z <= pos[1]:
                    draw_tree(screen, cam, pos, x, z)
            sprite = pygame.image.frombuffer(img.tobytes(), img.size, "RGBA")
            shadow = pygame.Surface((int(6 * px_per_unit), int(1.6 * px_per_unit)), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 60), shadow.get_rect())
            screen.blit(shadow, shadow.get_rect(center=(W / 2, FEET_Y)))
            screen.blit(sprite, (W / 2 - MII_SIZE / 2, FEET_Y - feet_row + bob * px_per_unit))
            for x, z in order:
                # Trees between the camera and the Mii would hide it: only
                # draw those that stand off to the side.
                if z > pos[1] and abs(x - pos[0]) > 7.0:
                    draw_tree(screen, cam, pos, x, z)
            draw_minimap(screen, pos, heading, trail, trees)
            hud = f"WASD walk   Shift run   Q quit      {speed_now:4.1f} u/s   {clock.get_fps():4.1f} fps"
            screen.blit(font.render(hud, True, (20, 20, 20)), (12, 12))
            pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
