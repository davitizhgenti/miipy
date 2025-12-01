# mii/constants.py


"""
Defines constants that map directly to the enums in the FFL-Testing C++ backend.
This provides a safe and readable way to use the magic numbers required by the renderer.

The primary source for the Expression values is the C++ header file:
'FFL-Testing/ffl/include/FFL_expression.h'
"""

class ViewType:
    FACE = 0
    FACE_ONLY = 1
    ALL_BODY = 2

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
    
    # Convenience alias for similar visual results
    PUZZLED = 3 # Mapped to SORROW

class ResourceType:
    MIDDLE = 0
    HIGH = 1

class ShaderType:
    DEFAULT = 0 # The standard shader, required for expressions to work correctly.
    SIMPLE = 1  # A fallback shader that is more compatible but lacks features.

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