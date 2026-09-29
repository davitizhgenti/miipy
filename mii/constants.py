# mii/constants.py


"""
Defines constants that map directly to the enums in the FFL-Testing C++ backend.
This provides a safe and readable way to use the magic numbers required by the renderer.

The primary source for the Expression values is the C++ header file:
'FFL-Testing/ffl/include/FFL_expression.h'
"""
from enum import IntEnum

class ViewType:
    FACE       = 0
    FACE_ONLY  = 1
    ALL_BODY   = 2
    UPPER_BODY = 7   # waist-up framing for V-Avatar (VIEW_TYPE_UPPER_BODY)

class ModelType:
    NORMAL = 0
    HAT = 1
    FACE_ONLY = 2

class Expression:
    """Maps to the FFLExpression enum in FFL_expression.h"""
    NORMAL = 0
    SMILE = 1
    ANGER = 2
    SORROW = 3
    SURPRISE = 4
    BLINK = 5
    OPEN_MOUTH = 6
    HAPPY_OPEN_MOUTH = 7
    ANGER_OPEN_MOUTH = 8
    SORROW_OPEN_MOUTH = 9
    SURPRISE_OPEN_MOUTH = 10
    BLINK_OPEN_MOUTH = 11
    WINK_LEFT = 12
    WINK_RIGHT = 13
    WINK_LEFT_OPEN_MOUTH = 14
    WINK_RIGHT_OPEN_MOUTH = 15
    LIKE = 16
    LIKE_WINK_RIGHT = 17
    FRUSTRATED = 18
    
    # Convenience aliases
    PUZZLED = 3  # Mapped to SORROW
    HAPPY   = 7  # Alias for SMILE_OPEN_MOUTH (squinted happy eyes + open mouth)

    # Miitomo expressions (19-69) — require ShaderType.DEFAULT
    BORED           = 19   # Bored (closed mouth)
    BORED_OPEN      = 20   # Bored open mouth
    SIGH            = 21   # Sigh mouth straight
    SIGH_OPEN       = 22   # Sigh
    DISGUSTED       = 23
    DISGUSTED_OPEN  = 24
    LOVE            = 25
    LOVE_OPEN       = 26
    DETERMINED      = 27
    DETERMINED_OPEN = 28
    CRY             = 29
    CRY_OPEN        = 30
    BIG_SMILE       = 31   # Big smile, squinted eyes (closed mouth) — "High Smile"
    BIG_SMILE_OPEN  = 32   # Big smile, squinted eyes (open mouth)
    CHEEKY          = 33
    SMUG            = 37
    SMUG_OPEN       = 38
    RESOLVE         = 39
    RESOLVE_OPEN    = 40
    MONEY           = 55
    MONEY_OPEN      = 56
    CONFUSED        = 57
    CONFUSED_OPEN   = 58
    CHEERFUL        = 59   # Cheerful, squinted eyes (closed mouth)
    CHEERFUL_OPEN   = 60   # Cheerful, squinted eyes (open mouth)
    GRUMBLE         = 63
    GRUMBLE_OPEN    = 64
    MOVED           = 65
    MOVED_OPEN      = 66
    SINGING         = 67
    SINGING_OPEN    = 68
    STUNNED         = 69

class ResourceType:
    MIDDLE = 0
    HIGH = 1

class ShaderType:
    """Maps to ShaderType in FFL-Testing/include/Types.h."""
    DEFAULT = 0 # Wii U shader, required for expressions to work correctly.
    WIIU    = 0
    SWITCH  = 1 # Also selects the Switch body when body_type is -1.
    SIMPLE  = 1 # Legacy name; this is the Switch shader.
    MIITOMO = 2
    WIIU_BLINN = 3
    WIIU_FFLICONWITHBODY = 4

class ClothesColor:
    DEFAULT = -1
    RED = 0
    ORANGE = 1
    YELLOW = 2
    LIME = 3
    GREEN = 4
    BLUE = 5
    CYAN = 6
    PINK = 7
    PURPLE = 8
    BROWN = 9
    WHITE = 10
    BLACK = 11

class PantsColor:
    DEFAULT = -1
    GRAY = 0
    BLUE = 1
    RED = 2
    GOLD = 3
    BODY = 4
    NONE = 5

class Bone:
    """Maps to VriableIconBodyBoneKind in FFL-Testing/src/BodyModel.cpp.

    Low-level: rotations are raw Euler angles in the *parent* bone's rest
    axes. Prefer `Joint` + `rig.Pose`, which use one body-space convention.

    The body is rigid segments joined by spheres. ARM_x1/ARM_x2/WRIST_x are
    upper arm/forearm/hand, FOOT_x1/FOOT_x2/ANKLE_x are thigh/shin/shoe.
    ELBOW_x, SHOULDER_x and KNEE_x are the joint *spheres*: rotating them
    does not bend anything.
    """
    ALL_ROOT   = 0
    BODY       = 1
    SKL_ROOT   = 2
    CHEST      = 3
    ARM_L1     = 4
    ARM_L2     = 5
    WRIST_L    = 6
    ELBOW_L    = 7
    SHOULDER_L = 8
    ARM_R1     = 9
    ARM_R2     = 10
    WRIST_R    = 11
    ELBOW_R    = 12
    SHOULDER_R = 13
    HEAD       = 14
    NECK       = 14   # alias: same bone — controls the neck pivot, not the face itself
    CHEST2     = 15
    HIP        = 16
    FOOT_L1    = 17
    FOOT_L2    = 18
    ANKLE_L    = 19
    KNEE_L     = 20
    FOOT_R1    = 21
    FOOT_R2    = 22
    ANKLE_R    = 23
    KNEE_R     = 24

class Joint(IntEnum):
    """Posable joints of the body skeleton, named anatomically.

    Each value is the index of the bone that moves when the joint rotates
    (e.g. ELBOW_L moves the forearm). Used with `rig.Pose`.
    """
    ROOT       = 2    # whole body (SklRoot)
    CHEST      = 3    # torso
    NECK       = 14   # head
    SHOULDER_L = 4    # upper arm
    ELBOW_L    = 5    # forearm
    WRIST_L    = 6    # hand
    SHOULDER_R = 9
    ELBOW_R    = 10
    WRIST_R    = 11
    HIP_L      = 17   # thigh
    KNEE_L     = 18   # shin
    ANKLE_L    = 19   # shoe
    HIP_R      = 21
    KNEE_R     = 22
    ANKLE_R    = 23


class BoneOverride:
    """Rotation override for a single skeleton bone.

    Args:
        bone: A Bone constant identifying which bone to rotate.
        rotate: (x, y, z) rotation in degrees.
    """
    def __init__(self, bone, rotate=(0.0, 0.0, 0.0)):
        self.bone   = int(bone)
        self.rotate = tuple(float(v) for v in rotate)


# Per-bone rotation limits: (x_min, x_max, y_min, y_max, z_min, z_max).
# Used by constrain_bones() to prevent unrealistic poses from raw camera data.
# Legacy: these are in each bone's parent axes and the KNEE entries target the
# knee spheres (no visible effect). Use rig.JOINT_LIMITS / Pose.clamp() instead.
BONE_CONSTRAINTS = {
    Bone.ARM_L1:   (-10,  10, -30,  30, -120, 120),  # left upper arm
    Bone.ARM_R1:   (-10,  10, -30,  30, -120, 120),  # right upper arm
    Bone.ARM_L2:   (-10,  10, -10,  10,  -90,  90),  # left forearm
    Bone.ARM_R2:   (-10,  10, -10,  10,  -90,  90),  # right forearm
    Bone.FOOT_L1:  (-90,  90, -20,  20,  -20,  20),  # left thigh
    Bone.FOOT_R1:  (-90,  90, -20,  20,  -20,  20),  # right thigh
    Bone.KNEE_L:   (  0, 120,   0,   0,    0,   0),  # left knee (one-way bend)
    Bone.KNEE_R:   (  0, 120,   0,   0,    0,   0),  # right knee
    Bone.SKL_ROOT: (-15,  15, -15,  15,  -15,  15),  # body root
}


def constrain_bones(overrides):
    """Clamp each BoneOverride's rotation to the anatomically safe range.

    Returns a new list of BoneOverride objects with clamped values.
    Bones not in BONE_CONSTRAINTS are passed through unchanged.
    """
    result = []
    for bo in overrides:
        if bo.bone in BONE_CONSTRAINTS:
            xn, xx, yn, yx, zn, zx = BONE_CONSTRAINTS[bo.bone]
            rx, ry, rz = bo.rotate
            result.append(BoneOverride(bo.bone, rotate=(
                max(xn, min(xx, rx)),
                max(yn, min(yx, ry)),
                max(zn, min(zx, rz)),
            )))
        else:
            result.append(bo)
    return result