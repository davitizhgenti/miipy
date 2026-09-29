# mii/builder.py
import os
import subprocess
import platform
import shutil
import logging

from .exceptions import BuildError

logger = logging.getLogger("miipy")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_DIR = os.path.join(PROJECT_ROOT, "FFL-Testing")
BUILD_DIR = os.path.join(SOURCE_DIR, "build")


def check_tool(name):
    if not shutil.which(name):
        raise BuildError(f"'{name}' is not installed or not in PATH.")


def reset_submodule():
    """Resets the FFL-Testing submodule to a clean state."""
    check_tool("git")
    if not os.path.exists(os.path.join(PROJECT_ROOT, ".git")):
        raise BuildError("Not a git repository. Cannot reset submodule.")
    logger.info("[-] Resetting FFL-Testing submodule...")
    try:
        subprocess.check_call(["git", "submodule", "deinit", "-f", "FFL-Testing"],
                              cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL)
        subprocess.check_call(["git", "submodule", "update", "--init", "--recursive", "--force"],
                              cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        raise BuildError(f"Failed to reset submodule: {e}") from e


def install_resource(source_path):
    """Copies the user provided resource file to FFL-Testing/FFLResHigh.dat."""
    if not os.path.exists(source_path):
        raise BuildError(f"Resource file not found: {source_path}")
    target_path = os.path.join(SOURCE_DIR, "FFLResHigh.dat")
    logger.info(f"[-] Installing resource {source_path} -> {target_path}")
    shutil.copy2(source_path, target_path)


def apply_patches():
    """Apply miipy's changes (patches/*.patch) to the FFL-Testing submodule.

    Skips patches that are already applied, so this is safe to run every build.
    """
    patch_dir = os.path.join(PROJECT_ROOT, "patches")
    patches = sorted(p for p in os.listdir(patch_dir) if p.endswith(".patch")) \
        if os.path.isdir(patch_dir) else []
    for name in patches:
        path = os.path.join(patch_dir, name)
        applied = subprocess.run(["git", "apply", "--reverse", "--check", path],
                                 cwd=SOURCE_DIR, capture_output=True).returncode == 0
        if applied:
            continue
        check_tool("git")
        logger.info(f"[-] Applying {name}...")
        result = subprocess.run(["git", "apply", path], cwd=SOURCE_DIR,
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise BuildError(f"Could not apply {name} to FFL-Testing "
                             f"(submodule at a different commit?):\n{result.stderr}")


def build_backend(reset=False, resource=None):
    """Configure and compile the C++ backend. Raises BuildError on failure."""
    logger.info("Mii Backend Builder")
    check_tool("cmake")
    if reset:
        reset_submodule()
    if resource:
        install_resource(resource)

    if not os.path.exists(os.path.join(SOURCE_DIR, "FFLResHigh.dat")):
        raise BuildError("'FFLResHigh.dat' is missing in FFL-Testing. "
                         "Run: python -m mii build --resource <path/to/FFLResHigh.dat>")
    if not os.path.exists(os.path.join(SOURCE_DIR, "CMakeLists.txt")):
        raise BuildError("FFL-Testing source missing. Try: python -m mii build --reset")
    apply_patches()

    configure = ["cmake", "-S", SOURCE_DIR, "-B", BUILD_DIR,
                 "-DCMAKE_BUILD_TYPE=Release", "-DRIO_NO_CLIP_CONTROL=ON",
                 "-DCMAKE_CXX_FLAGS=-DNDEBUG -O3"]
    if platform.system() == "Linux":
        configure.append("-DRIO_USE_HEADLESS_GLFW=ON")

    try:
        logger.info("[-] Running CMake Configure...")
        subprocess.check_call(configure)
        logger.info("[-] Running CMake Build...")
        subprocess.check_call(["cmake", "--build", BUILD_DIR, "-j", "4"])
    except subprocess.CalledProcessError as e:
        raise BuildError("Build failed. Check the compiler output above.") from e

    logger.info("Build Complete.")
