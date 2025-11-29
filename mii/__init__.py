import os
from .server import FFLBackend
from .client import FFLClient
from .protocol import RenderRequest
from .builder import build_backend
from .constants import ViewType, Expression, Color

class MiiPy:
    def __init__(self, port=12346, auto_start=True, show_logs=False):
        """
        Initializes the Mii Renderer, automatically building the backend if needed.
        
        PRE-REQUISITE: 'FFLResHigh.dat' must be placed in the 'FFL-Testing' directory.
        """
        # PATH DETECTION
        package_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(package_dir)
        
        # Define the required path for the resource file
        resource_path = os.path.join(root_dir, "FFL-Testing", "FFLResHigh.dat")
        
        # Define the path for the binary
        bin_name = "ffl_testing_2.exe" if os.name == 'nt' else "ffl_testing_2"
        binary_path = os.path.join(root_dir, "FFL-Testing", "build", bin_name)

        # AUTO-BUILD LOGIC
        if not os.path.exists(binary_path):
            print("⚠️ Backend executable not found. Attempting to build automatically...")
            try:
                build_backend()
            except Exception as e:
                raise RuntimeError(f"Auto-build failed: {e}")
        
        # INITIALIZATION
        # Pass the internally constructed resource_path to FFLBackend
        self.server = FFLBackend(resource_path=resource_path, port=port, show_logs=show_logs)
        if auto_start:
            self.server.start()
        
        self.client = FFLClient(port=port)

    def render(self, source, out=None, size=512, zoom=None, expression=Expression.NORMAL, view=ViewType.FACE):
        if isinstance(source, bytes):
            data = source
        elif os.path.exists(source):
            with open(source, "rb") as f:
                data = f.read(96)
        else:
            raise ValueError("Invalid Mii Source")

        req = RenderRequest(data)
        req.resolution = size
        req.zoom = zoom if zoom else size
        req.expression = expression
        req.view_type = view
        
        img = self.client.render_image(req)
        
        if out:
            img.save(out)
        
        return img

    def close(self):
        self.server.stop()

    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()

    @staticmethod
    def build():
        """Manually triggers the C++ backend compilation."""
        print("Manual Backend Build Triggered")
        try:
            from .builder import build_backend
            build_backend()
        except Exception as e:
            print(f"❌ Manual build failed: {e}")