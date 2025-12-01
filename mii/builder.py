import os
import subprocess
import sys
import platform
import shutil
import stat
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_tool(name):
    if not shutil.which(name):
        raise RuntimeError(f"Error: '{name}' is not installed or not in PATH.")

def reset_submodule(project_root):
    """
    Resets the FFL-Testing submodule to a clean state.
    """
    logger.info("[-] Resetting FFL-Testing submodule...")
    try:
        # De-initialize to remove local config
        subprocess.check_call(
            ["git", "submodule", "deinit", "-f", "FFL-Testing"], 
            cwd=project_root, stdout=subprocess.DEVNULL
        )
        # Update to fetch fresh copy
        subprocess.check_call(
            ["git", "submodule", "update", "--init", "--recursive", "--force"], 
            cwd=project_root
        )
        logger.info("Submodule reset successful.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to reset submodule: {e}")
        sys.exit(1)

def install_resource(source_path, submodule_dir):
    """
    Copies the user provided resource file to FFL-Testing/FFLResHigh.dat
    """
    if not os.path.exists(source_path):
        logger.error(f"Resource file not found: {source_path}")
        sys.exit(1)

    target_path = os.path.join(submodule_dir, "FFLResHigh.dat")
    
    logger.info(f"[-] Installing resource...")
    logger.info(f"    Source: {source_path}")
    logger.info(f"    Dest:   {target_path}")
    
    try:
        shutil.copy2(source_path, target_path)
        logger.info("Resource installed.")
    except Exception as e:
        logger.error(f"Failed to copy resource: {e}")
        sys.exit(1)

def build_backend():
    """
    Parses arguments and runs the build process.
    """
    parser = argparse.ArgumentParser(description="MiiPy Backend Builder")
    parser.add_argument("--reset", action="store_true", help="Reset git submodule to clean state before building")
    parser.add_argument("--resource", type=str, help="Path to your FFLResHigh.dat file (will be copied)")
    
    # Allow calling without args if just rebuilding
    args = parser.parse_args()

    # PATHS
    package_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(package_dir)
    source_dir = os.path.join(project_root, "FFL-Testing")
    build_dir = os.path.join(source_dir, "build")

    logger.info("Mii Backend Builder\n")

    # 1. Validation & Tools
    check_tool("cmake")
    if args.reset:
        check_tool("git")

    # 2. Reset Submodule (Optional)
    if args.reset:
        if not os.path.exists(os.path.join(project_root, ".git")):
            logger.error("Not a git repository. Cannot reset submodule.")
            sys.exit(1)
        reset_submodule(project_root)

    # 3. Install Resource (Optional but recommended)
    if args.resource:
        install_resource(args.resource, source_dir)
    
    # 4. Check Resource Existence (Critical)
    final_res_path = os.path.join(source_dir, "FFLResHigh.dat")
    if not os.path.exists(final_res_path):
        logger.error("Build Error: 'FFLResHigh.dat' is missing in FFL-Testing.")
        logger.error("Usage: python -m mii.builder --resource <path/to/dat>")
        sys.exit(1)

    # 5. CMake Configuration
    if not os.path.exists(os.path.join(source_dir, "CMakeLists.txt")):
        logger.error("FFL-Testing source missing. Try running with --reset")
        sys.exit(1)

    logger.info("[*] Compiling Mii Backend...")
    
    cmake_args = [
        f"-S {source_dir}", f"-B {build_dir}",
        "-DCMAKE_BUILD_TYPE=Release", "-DRIO_NO_CLIP_CONTROL=ON",
        "-DCMAKE_CXX_FLAGS='-DNDEBUG -O3'"
    ]
    if platform.system() == "Linux":
        cmake_args.append("-DRIO_USE_HEADLESS_GLFW=ON")

    try:
        logger.info("[-] Running CMake Configure...")
        subprocess.check_call(f"cmake {' '.join(cmake_args)}", shell=True)
        
        logger.info("[-] Running CMake Build...")
        subprocess.check_call(f"cmake --build {build_dir} -j 4", shell=True)
    except subprocess.CalledProcessError:
        logger.error("Build Failed. Check logs.")
        sys.exit(1)

    logger.info("Build Complete.")

if __name__ == "__main__":
    build_backend()