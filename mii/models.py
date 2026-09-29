# mii/models.py
import logging
import struct
from .constants import (
    ViewType, Expression, ResourceType, ShaderType, 
    ClothesColor, PantsColor, ModelType
)

logger = logging.getLogger("miipy")

def _clamp(val, min_v, max_v):
    return int(max(min_v, min(max_v, val)))

def _clamp_tuple(t, min_v, max_v):
    return tuple(int(max(min_v, min(max_v, x))) for x in t)

class RenderSettings:
    """Holds configuration for a render request."""
    # < = Little Endian
    # Suffix 75h = boneRotations[25][3], h = mouthFrame, hh = eyeRotation[2],
    #        bb  = eyebrowDeltaY + eyebrowDeltaRotate
    STRUCT_FORMAT = '<96sHBBHhBbBBIIIhhhhhhBBBBBB???bbbbbBBhhhB75hhhhbb'

    def __init__(self):
        self.resolution = 512
        self.tex_resolution = 512
        self.view_type = ViewType.FACE
        self.expression = Expression.NORMAL
        self.resource_type = ResourceType.HIGH
        self.shader_type = ShaderType.DEFAULT
        self.bg_color = (0, 0, 0, 0)
        self.camera_rot = (0, 0, 0)
        self.model_rot = (0, 0, 0)
        self.model_type = ModelType.NORMAL 
        self.flatten_nose = False
        self.clothes_color = ClothesColor.DEFAULT 
        self.pants_color = PantsColor.DEFAULT     
        self.body_type = -1          
        self.headwear_index = -1     
        self.headwear_color = -1     
        self.light_enable = True
        self.light_direction = (-1, -1, -1)
        self.instance_count = 1
        self.instance_rot_mode = 0
        self.draw_stage_mode = 0
        self.split_mode = 0
        self.verify_charinfo = False
        self.verify_crc16 = True
        self.aa_method = 0
        self.export_as_gltf = False
        self.expr_flags = (0, 0, 0)
        self.bones = []           # list of BoneOverride (low-level, parent-axis Euler)
        self.pose = None          # rig.Pose (preferred); explicit `bones` win per bone
        self.mouth_frame = 0.0    # 0.0=closed, 1.0=open; switches to open-mouth expression
        self.eye_rotation = (0.0, 0.0)  # (x, y) normalized ±1.0 (reserved for future)
        self.eyebrow_delta_y      = 0   # int, -18..+18: shift eyebrow up/down from default
        self.eyebrow_delta_rotate = 0   # int, -11..+11: tilt eyebrow

    def _pose_overrides(self):
        if self.pose is None:
            return []
        from .rig import Skeleton, SKELETON_BODY_NAMES, resolve_body_type
        body = resolve_body_type(self.body_type, self.shader_type)
        if body not in SKELETON_BODY_NAMES:
            logger.warning("pose ignored: body type %d has no skeleton", body)
            return []
        skeleton = Skeleton.load(SKELETON_BODY_NAMES[body])
        return self.pose.to_bone_overrides(skeleton)

    def pack(self, mii_data: bytes) -> bytes:
        if len(mii_data) != 96:
            raise ValueError(f"Mii data must be 96 bytes, got {len(mii_data)}")

        model_flag = (1 << self.model_type)
        if self.flatten_nose:
            model_flag |= (1 << 3)

        response_fmt = 2 # TGA
        if self.export_as_gltf:
            response_fmt = 1

        # Build flat bone array: 25 bones * 3 axes, fixed-point degrees*10
        bone_array = [0] * 75
        for override in self._pose_overrides() + list(self.bones):
            idx = int(override.bone)
            if 0 <= idx < 25:
                for axis, deg in enumerate(override.rotate[:3]):
                    bone_array[idx * 3 + axis] = _clamp(round(deg * 10), -32768, 32767)

        mouth = _clamp(int(self.mouth_frame * 1000), 0, 1000)
        eye_x = _clamp(int(self.eye_rotation[0] * 1000), -1000, 1000)
        eye_y = _clamp(int(self.eye_rotation[1] * 1000), -1000, 1000)

        return struct.pack(
            self.STRUCT_FORMAT,
            mii_data, 96,
            _clamp(model_flag, 0, 255),
            _clamp(response_fmt, 0, 255),
            int(self.resolution),
            _clamp(self.tex_resolution, -32768, 32767),
            _clamp(self.view_type, 0, 255),
            _clamp(self.resource_type, -128, 127),
            _clamp(self.shader_type, 0, 255),
            _clamp(self.expression, 0, 255),
            *self.expr_flags,
            *_clamp_tuple(self.camera_rot, -32768, 32767),
            *_clamp_tuple(self.model_rot, -32768, 32767),
            *_clamp_tuple(self.bg_color, 0, 255),
            _clamp(self.aa_method, 0, 255),
            _clamp(self.draw_stage_mode, 0, 255),
            self.verify_charinfo, self.verify_crc16, self.light_enable,
            _clamp(self.clothes_color, -128, 127),
            _clamp(self.pants_color, -128, 127),
            _clamp(self.body_type, -128, 127),
            _clamp(self.headwear_index, -128, 127),
            _clamp(self.headwear_color, -128, 127),
            _clamp(self.instance_count, 0, 255),
            _clamp(self.instance_rot_mode, 0, 255),
            *_clamp_tuple(self.light_direction, -32768, 32767),
            _clamp(self.split_mode, 0, 255),
            *bone_array,  # 75 int16: boneRotations[25][3]
            mouth,        # int16: mouthFrame
            eye_x, eye_y, # int16 x2: eyeRotation[2]
            _clamp(int(self.eyebrow_delta_y),      -18, 18),   # int8: eyebrowDeltaY
            _clamp(int(self.eyebrow_delta_rotate), -11, 11),   # int8: eyebrowDeltaRotate
        )