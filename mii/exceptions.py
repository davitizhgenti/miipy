# mii/exceptions.py


class MiiError(Exception):
    """Base class for all MiiPy errors."""
    pass

class AssetError(MiiError):
    """Raised when FFLResHigh.dat or submodule assets are missing."""
    pass

class BackendError(MiiError):
    """Raised when the C++ backend fails to start or crashes."""
    pass

class RenderError(MiiError):
    """Raised when network communication or image decoding fails."""
    pass