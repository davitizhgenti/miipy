# mii/__init__.py
import os
import logging
from PIL import Image

from .process import BackendProcess
from .client import FFLClient
from .models import RenderSettings
from .assets import AssetManager

# Re-export enums for user convenience
from .constants import *

# Configure a logger for the library
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("miipy")

class MiiPy:
    def __init__(self, port=12346, auto_start=True, show_logs=False):
        # 1. Setup paths and assets
        package_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(package_dir)
        assets = AssetManager(root_dir)

        # 2. Auto-Build if binary is missing
        if not assets.get_binary_path():
            logger.warning("Backend executable not found. Attempting to build automatically...")
            from .builder import build_backend
            build_backend()

        # 3. Verify resource file exists
        resource_path = assets.get_resource_path()
        if not resource_path:
            raise FileNotFoundError("FFLResHigh.dat not found in FFL-Testing/ or project root.")

        # 4. Initialize components
        self.process = BackendProcess(resource_path, port, show_logs)
        self.client = FFLClient(port=port)
        
        if auto_start:
            self.process.start()

    def render(self, source, out=None, size=512, **kwargs):
        # Load Mii data
        if isinstance(source, str):
            with open(source, "rb") as f: mii_data = f.read(96)
        else: mii_data = source

        settings = RenderSettings()
        
        # Map user-friendly arguments to internal settings
        # The 'zoom' kwarg controls the virtual render resolution for camera distance
        render_res = int(kwargs.pop('zoom', size))
        settings.resolution = render_res
        settings.tex_resolution = render_res
        
        # Apply all other keyword arguments
        for k, v in kwargs.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
            else:
                logger.warning(f"Ignoring unknown parameter '{k}'")
        
        # Get the raw image from the backend
        img = self.client.render_image(settings.pack(mii_data))
        
        # Resize if we used the zoom feature
        if img.width != size:
            img = img.resize((size, size), resample=Image.Resampling.LANCZOS)
        
        if out:
            img.save(out)
        
        return img

    def animate(self, source, size=512, **kwargs):
        if isinstance(source, str):
            with open(source, "rb") as f: mii_data = f.read(96)
        else: mii_data = source

        settings = RenderSettings()
        
        # Apply initial settings for the animation context
        for k, v in kwargs.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
        
        return AnimationContext(self.client, settings, mii_data, size)

    def close(self):
        self.process.stop()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

class AnimationContext:
    def __init__(self, client, settings, mii_data, output_size):
        self.client = client
        self.settings = settings
        self.data = mii_data
        self.output_size = output_size

    def frame(self, **changes):
        # Update settings for this specific frame
        for k, v in changes.items():
            # Handle zoom alias within animation frames
            if k == 'zoom':
                render_res = int(v)
                self.settings.resolution = render_res
                self.settings.tex_resolution = render_res
            elif hasattr(self.settings, k):
                setattr(self.settings, k, v)
        
        img = self.client.render_image(self.settings.pack(self.data))
        
        # Resize to the final output size if necessary
        if img.width != self.output_size:
            img = img.resize((self.output_size, self.output_size), resample=Image.Resampling.LANCZOS)
            
        return img