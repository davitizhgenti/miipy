import os
import subprocess
import sys
import platform
import shutil
import stat

def check_cmake():
    if not shutil.which("cmake"):
        raise RuntimeError("❌ CMake is not installed or not in PATH. Please install it.")

def build_backend():
    """
    Compiles the FFL-Testing C++ code inside the submodule.
    The final binary will be located in 'FFL-Testing/build/'.
    """
    # PATHS
    package_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(package_dir)
    source_dir = os.path.join(project_root, "FFL-Testing")
    build_dir = os.path.join(source_dir, "build")
    bin_name = "ffl_testing_2.exe" if os.name == 'nt' else "ffl_testing_2"

    # PRE-FLIGHT CHECKS
    if not os.path.exists(os.path.join(source_dir, "CMakeLists.txt")):
        raise FileNotFoundError(f"❌ FFL-Testing source not found. Run: git submodule update --init --recursive")
        
    required_dat_path = os.path.join(source_dir, "FFL-Testing", "FFLResHigh.dat")
    # This check is now in the __init__.py but we can keep it here for manual builds.
    if not os.path.exists(required_dat_path):
        print(f"⚠️ Warning: '{required_dat_path}' is missing. The build will proceed, but the renderer will fail at runtime.")

    print(f"[*] Compiling Mii Backend...")
    check_cmake()

    # CONFIGURATION
    cmake_args = [
        f"-S {source_dir}", f"-B {build_dir}",
        "-DCMAKE_BUILD_TYPE=Release", "-DRIO_NO_CLIP_CONTROL=ON",
        "-DCMAKE_CXX_FLAGS='-DNDEBUG -O3'"
    ]
    if platform.system() == "Linux":
        cmake_args.append("-DRIO_USE_HEADLESS_GLFW=ON")

    try:
        subprocess.check_call(f"cmake {' '.join(cmake_args)}", shell=True)
        subprocess.check_call(f"cmake --build {build_dir} -j 4", shell=True)
    except subprocess.CalledProcessError:
        raise RuntimeError("❌ Build Failed. Check the compilation logs.")

    # VERIFICATION
    # The binary should be directly in the build directory.
    found_bin = os.path.join(build_dir, bin_name)
    
    if os.path.exists(found_bin):
        # Ensure executable permissions are set.
        if os.name != 'nt':
            os.chmod(found_bin, stat.S_IRWXU) # chmod 700
        print(f"✅ Build Complete! Binary is at: {found_bin}")
    else:
        raise FileNotFoundError(f"❌ Build finished, but binary not found at expected location: {found_bin}")

def main():
    """Provides a user-friendly manual build interface."""
    print("MiiPy Backend Builder")
    try:
        build_backend()
    except Exception as e:
        print(f"\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()