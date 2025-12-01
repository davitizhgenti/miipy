# mii/models.py
import struct
from .constants import (
    ViewType, Expression, ResourceType, ShaderType, 
    ClothesColor, PantsColor, ModelType
)

def _clamp(val, min_v, max_v):
    return int(max(min_v, min(max_v, val)))

def _clamp_tuple(t, min_v, max_v):
    return tuple(int(max(min_v, min(max_v, x))) for x in t)

class RenderSettings:
    """Holds configuration for a render request."""
    # < = Little Endian
    STRUCT_FORMAT = '<96sHBBHhBbBBIIIhhhhhhBBBBBB???bbbbbBBhhhB'

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

    def pack(self, mii_data: bytes) -> bytes:
        if len(mii_data) != 96:
            raise ValueError(f"Mii data must be 96 bytes, got {len(mii_data)}")

        model_flag = (1 << self.model_type)
        if self.flatten_nose:
            model_flag |= (1 << 3)

        response_fmt = 2 # TGA
        if self.export_as_gltf:
            response_fmt = 1

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
            _clamp(self.split_mode, 0, 255)
        )