import subprocess
import time
import socket
import os
import sys
import atexit
import shutil

class FFLBackend:
    def __init__(self, resource_path, port=12346, show_logs=False):
        self.port = port
        self.process = None
        self.show_logs = show_logs
        
        # PATHS
        package_dir = os.path.dirname(os.path.abspath(__file__)) 
        root_dir = os.path.dirname(package_dir)
        
        bin_name = "ffl_testing_2.exe" if os.name == 'nt' else "ffl_testing_2"
        self.binary_path = os.path.join(root_dir, "FFL-Testing", "build", bin_name)
        
        # The working directory is the root of the submodule
        self.work_dir = os.path.join(root_dir, "FFL-Testing")
        
        # VERIFICATION
        if not os.path.exists(self.binary_path):
             raise FileNotFoundError(f"Binary not found: {self.binary_path}")
        if not os.path.exists(resource_path):
             raise FileNotFoundError(f"Resource file not found: {resource_path}")
        if not os.path.exists(self.work_dir):
             raise FileNotFoundError(f"Submodule directory not found: {self.work_dir}")

    def start(self):
        if self.is_running(): return
        
        if self.show_logs:
            print(f"[*] Starting Renderer Service...")
        
        stdout, stderr = (sys.stdout, sys.stderr) if self.show_logs else (subprocess.DEVNULL, subprocess.DEVNULL)
        
        try:
            self.process = subprocess.Popen(
                [self.binary_path, "--server", "--port", str(self.port)],
                cwd=self.work_dir, # Run from FFL-Testing root
                stdout=stdout,
                stderr=stderr
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start binary: {e}")

        if not self._wait_for_port():
            self.stop()
            raise RuntimeError("Backend failed to start. Run with show_logs=True for details.")
        
        atexit.register(self.stop)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

    def is_running(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            return s.connect_ex(('127.0.0.1', self.port)) == 0

    def _wait_for_port(self, timeout=5):
        start = time.time()
        while time.time() - start < timeout:
            if self.is_running(): return True
            time.sleep(0.2)
        return False