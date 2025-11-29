import struct
from .constants import ViewType, Expression, ResourceType, ShaderType

class RenderRequest:
    """
    Constructs the 155-byte binary packet for the FFL-Testing server.
    """
    STRUCT_FORMAT = '<96sHBBHhBbBBIIIhhhhhhBBBBBB???bBbbbBBhhhB'

    def __init__(self, mii_data: bytes):
        if len(mii_data) != 96:
            raise ValueError(f"Mii data must be 96 bytes, got {len(mii_data)}")

        self.mii_data = mii_data

        # Defaults
        self.resolution = 512
        self.zoom       = 512
        self.view_type  = ViewType.FACE
        self.expression = Expression.NORMAL
        self.resource_type = ResourceType.HIGH
        
        self.shader_type = ShaderType.DEFAULT

        self.bg_color = (0, 0, 0, 0) # Transparent
        self.camera_rot = (0, 0, 0)
        self.model_rot  = (0, 0, 0)
        self.export_as_gltf = False

    def pack(self):
        return struct.pack(
            self.STRUCT_FORMAT,
            self.mii_data, 96, (1 << 0), self.export_as_gltf,
            self.zoom, self.resolution, self.view_type,
            self.resource_type, self.shader_type, self.expression,
            0, 0, 0, # Expr Flags
            *self.camera_rot, *self.model_rot, *self.bg_color,
            0, 0, # AA, Draw Stage
            True, True, True, # Verify, CRC, Light
            -1, 1, -1, -1, -1, # Clothes, Pants, etc.
            0, 0, # Instance
            -1, -1, -1, # Light Dir
            0 # Split
        )