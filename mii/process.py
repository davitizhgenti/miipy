# mii/process.py
import subprocess
import os
import sys
import atexit
import time
import socket
from .exceptions import BackendError
from .assets import AssetManager

class BackendProcess:
    def __init__(self, resource_path, port=12346, show_logs=False):
        self.port = port
        self.show_logs = show_logs
        self.process = None
        self.devnull = None
        
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(pkg_dir)
        
        self.assets = AssetManager(self.root_dir)
        self.binary = self.assets.get_binary_path()
        
        if not self.binary:
            raise BackendError("Binary not found. Run builder.")

        # Just validate and get the root folder. No copying.
        self.work_dir = self.assets.validate_environment(resource_path)

    def start(self):
        if self.is_running(): return

        if self.show_logs:
            print(f"[*] Starting Backend: {self.binary}")
            print(f"[*] CWD: {self.work_dir}")
            out_dest = sys.stdout
            err_dest = sys.stderr
        else:
            self.devnull = open(os.devnull, 'w')
            out_dest = self.devnull
            err_dest = self.devnull # Still pipe stderr to devnull if quiet

        try:
            self.process = subprocess.Popen(
                [self.binary, "--server", "--port", str(self.port)],
                cwd=self.work_dir,
                stdout=out_dest,
                stderr=err_dest,
                text=True
            )
        except Exception as e:
            raise BackendError(f"Failed to launch binary: {e}")

        for _ in range(50):
            return_code = self.process.poll()
            if return_code is not None:
                self.stop()
                # If we crashed and logs were hidden, we can't show them because we sent them to devnull.
                # User must run with show_logs=True to see why.
                raise BackendError(f"Backend crashed immediately (Code {return_code}). Enable show_logs=True to see why.")

            if self.is_running(): 
                atexit.register(self.stop)
                return
            time.sleep(0.1)
        
        self.stop()
        raise BackendError("Backend timed out.")

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        
        if self.devnull:
            self.devnull.close()
            self.devnull = None

    def is_running(self):
        try:
            with socket.create_connection(('127.0.0.1', self.port), timeout=0.1):
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False