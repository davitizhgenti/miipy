# mii/assets.py
import os
import logging
from .exceptions import AssetError

logger = logging.getLogger(__name__)

class AssetManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.submodule_path = os.path.join(root_dir, "FFL-Testing")
        self.bin_name = "ffl_testing_2.exe" if os.name == 'nt' else "ffl_testing_2"

    def get_binary_path(self):
        """Finds the binary in the source root or build folder."""
        possible_paths = [
            os.path.join(self.submodule_path, self.bin_name),          # FFL-Testing/ffl_testing_2
            os.path.join(self.submodule_path, "build", self.bin_name), # FFL-Testing/build/ffl_testing_2
        ]
        for p in possible_paths:
            if os.path.exists(p): return p
        return None

    def get_resource_path(self):
        """
        Locates FFLResHigh.dat.
        Checks FFL-Testing/ first, then Project Root.
        """
        # Priority 1: Inside submodule (Best for "No Copy" mode)
        res_internal = os.path.join(self.submodule_path, "FFLResHigh.dat")
        if os.path.exists(res_internal):
            return res_internal
            
        # Priority 2: Project Root
        res_root = os.path.join(self.root_dir, "FFLResHigh.dat")
        if os.path.exists(res_root):
            return res_root
            
        return None

    def validate_environment(self, resource_path):
        """
        Checks if required files exist in their source locations.
        Returns the CWD where the binary should run (The Submodule Root).
        """
        # We run from the submodule root so the binary can find 'shaders/' and 'fs/' relative to itself.
        runtime_cwd = self.submodule_path
        
        # print(f"[*] inspecting assets in: {runtime_cwd}")

        # 1. Check Resource File
        target_res = os.path.join(runtime_cwd, "FFLResHigh.dat")
        if os.path.abspath(resource_path) != os.path.abspath(target_res):
            if not os.path.exists(target_res):
                print(f"Error: FFLResHigh.dat must be located at: {target_res}")
                print(f"   (You provided: {resource_path})")
                raise AssetError("FFLResHigh.dat missing from source root.")
        # else:
        #     print(f"   [OK] Resource: {target_res}")

        # 2. Check Shaders
        shaders_path = os.path.join(runtime_cwd, "fs", "content", "shaders")
        if not os.path.exists(shaders_path):
            print(f"[MISSING] Shaders not found at: {shaders_path}")

        # 3. Check Body Models CSV
        csv_path = os.path.join(runtime_cwd, "fs", "content", "body_models.csv")
        if not os.path.exists(csv_path):
            print(f"[MISSING] CSV not found at: {csv_path}")

        return runtime_cwd

    def cleanup(self):
        pass # Nothing to clean up