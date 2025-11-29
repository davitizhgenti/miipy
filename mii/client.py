import socket
import io
from .protocol import RenderRequest

try:
    from PIL import Image
except ImportError:
    raise ImportError("Pillow library not found. Run 'pip install pillow'")

class FFLClient:
    def __init__(self, port=12346):
        self.host = "127.0.0.1"
        self.port = port

    def render_image(self, request: RenderRequest) -> Image.Image:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                s.sendall(request.pack())

                response = bytearray()
                while True:
                    chunk = s.recv(4096)
                    if not chunk: break
                    response.extend(chunk)
                
                if not response:
                    raise ValueError("Server returned empty response.")

                with io.BytesIO(response) as stream:
                    img = Image.open(stream)
                    img.load()
                    
                    # The server outputs BGRA. We need to convert it to RGBA.
                    # We split the channels and re-merge them in the correct order.
                    b, g, r, a = img.split()
                    img = Image.merge("RGBA", (r, g, b, a))
                    
                    # OpenGL renders Bottom-Up. Flip it vertically to correct the orientation.
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                    
                    return img

        except ConnectionRefusedError:
            raise ConnectionError("Connection refused. Is the backend running?")
        except Exception as e:
            raise RuntimeError(f"Failed to process image from server: {e}")