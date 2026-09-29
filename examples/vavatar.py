"""
vavatar.py — Webcam-driven full-body Mii (MediaPipe Tasks API).

Body: PoseLandmarker 3D world landmarks -> retarget.pose_from_mediapipe
      (arms/legs aimed in 3D, elbow/knee planes solved, torso lean/turn).
Head: FaceLandmarker transformation matrix -> NECK; blendshapes drive the
      mouth, blinks and eyebrows.

Requires: pip install mediapipe opencv-python numpy pillow
Models are downloaded to ~/.cache/miipy on first run.

Controls: Q quit | S save snapshot | +/- cycle expression | L toggle legs
"""
import argparse
import os
import sys
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mii import MiiPy, ViewType, Expression, Joint, Pose  # noqa: E402
from mii.retarget import pose_from_mediapipe, PoseFilter  # noqa: E402

MODELS = {
    "pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "face": "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/latest/face_landmarker.task",
}
EXPRESSIONS = [Expression.NORMAL, Expression.SMILE, Expression.BIG_SMILE, Expression.ANGER,
               Expression.SORROW, Expression.SURPRISE, Expression.LOVE, Expression.CHEERFUL,
               Expression.DETERMINED, Expression.BORED]
EXPRESSION_NAMES = {v: k for k, v in vars(Expression).items() if k.isupper()}


def model_path(name):
    path = os.path.join(os.path.expanduser("~/.cache/miipy"), os.path.basename(MODELS[name]))
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"[*] downloading {os.path.basename(path)} ...")
        urllib.request.urlretrieve(MODELS[name], path)
    return path


def head_rotation(face_result):
    """Head rotation (body axes) from the face transformation matrix."""
    if not face_result.facial_transformation_matrixes:
        return None
    m = np.asarray(face_result.facial_transformation_matrixes[0])[:3, :3]
    u, _, vt = np.linalg.svd(m)  # strip scale
    return u @ vt


def face_params(face_result):
    """Mouth, blink and eyebrow parameters from ARKit-style blendshapes."""
    if not face_result.face_blendshapes:
        return {}
    b = {c.category_name: c.score for c in face_result.face_blendshapes[0]}
    brow = b.get("browInnerUp", 0) - (b.get("browDownLeft", 0) + b.get("browDownRight", 0)) / 2
    return {
        "mouth_frame": min(1.0, b.get("jawOpen", 0) * 2.0),
        # FFL eyebrow Y is inverted: negative delta = raised.
        "eyebrow_delta_y": int(np.clip(-brow * 10, -8, 8)),
        "blink": (b.get("eyeBlinkLeft", 0) > 0.5, b.get("eyeBlinkRight", 0) > 0.5),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mii", help=".ffsd file")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--size", type=int, default=256, help="render resolution")
    ap.add_argument("--full-body", action="store_true", help="ALL_BODY view instead of upper body")
    ap.add_argument("--smooth", type=float, default=0.5, help="1 = raw, lower = smoother")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit(f"Cannot open camera {args.camera}")

    pose_opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path("pose")),
        running_mode=vision.RunningMode.VIDEO)
    face_opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path("face")),
        running_mode=vision.RunningMode.VIDEO, num_faces=1,
        output_face_blendshapes=True, output_facial_transformation_matrixes=True)

    smooth = PoseFilter(args.smooth)
    expr_idx, legs, snaps = 0, args.full_body, 0
    start = time.monotonic()
    fps, last = 0.0, start

    with vision.PoseLandmarker.create_from_options(pose_opts) as pose_lm, \
         vision.FaceLandmarker.create_from_options(face_opts) as face_lm, \
         MiiPy() as renderer:
        anim = renderer.animate(source=args.mii, size=args.size, bg_color=(0, 0, 0, 0),
                                view=ViewType.ALL_BODY if args.full_body else ViewType.UPPER_BODY)
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # selfie view: the Mii mirrors you
            image = mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            ts = int((time.monotonic() - start) * 1000)
            body = pose_lm.detect_for_video(image, ts)
            face = face_lm.detect_for_video(image, ts)

            if body.pose_world_landmarks:
                pose = pose_from_mediapipe(body.pose_world_landmarks[0], legs=legs, clamp=False, collide=False)
            else:  # keep the last body pose, still track the head
                pose = smooth.pose.copy() if smooth.pose else Pose()
            head = head_rotation(face)
            if head is not None:
                # NECK is carried by the chest: make the head relative to it.
                pose.set_rotation(Joint.NECK, pose.body_rotation(Joint.CHEST).T @ head)
            # Smooth first, then keep the smoothed pose out of the body.
            pose = smooth(pose.clamp()).resolve_collisions()

            params = face_params(face)
            expr = EXPRESSIONS[expr_idx]
            blink_l, blink_r = params.pop("blink", (False, False))
            if blink_l and blink_r:
                expr = Expression.BLINK
            elif blink_l or blink_r:
                # Same left/right convention as the body (the frame is already mirrored).
                expr = Expression.WINK_LEFT if blink_l else Expression.WINK_RIGHT

            mii = anim.frame(pose=pose, expression=expr, **params)

            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - last, 1e-6)
            last = now

            h = 480
            cam = cv2.resize(frame, (int(frame.shape[1] * h / frame.shape[0]), h))
            mii_bgr = cv2.cvtColor(np.asarray(mii.convert("RGB")), cv2.COLOR_RGB2BGR)
            view = np.hstack([cam, cv2.resize(mii_bgr, (h, h))])
            cv2.putText(view, f"{fps:4.1f} fps  {EXPRESSION_NAMES.get(expr, expr)}  legs:{'on' if legs else 'off'}  Q quit  S snap  +/- expr  L legs",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imshow("V-Avatar", view)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("s"):
                mii.save(f"vavatar_{snaps:03d}.png")
                snaps += 1
            elif key in (ord("+"), ord("=")):
                expr_idx = (expr_idx + 1) % len(EXPRESSIONS)
            elif key == ord("-"):
                expr_idx = (expr_idx - 1) % len(EXPRESSIONS)
            elif key == ord("l"):
                legs = not legs

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
