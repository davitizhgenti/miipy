# mii/client.py
import socket
import io
from .exceptions import RenderError

try:
    from PIL import Image
except ImportError:
    raise ImportError("Pillow library not found. Run 'pip install pillow'")

class FFLClient:
    def __init__(self, port=12346):
        self.host = "127.0.0.1"
        self.port = port

    def render_image(self, payload: bytes) -> Image.Image:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                s.sendall(payload)

                header = self._recv_exact(s, 18)
                width = header[12] + (header[13] << 8)
                height = header[14] + (header[15] << 8)
                
                body_size = width * height * 4
                raw_pixels = self._recv_exact(s, body_size)
                
                # Optimized decode
                img = Image.frombytes('RGBA', (width, height), bytes(raw_pixels), 'raw', 'BGRA')
                return img.transpose(Image.FLIP_TOP_BOTTOM)

        except Exception as e:
            raise RenderError(f"Render failed: {e}")

    def _recv_exact(self, sock, size):
        buf = bytearray()
        while len(buf) < size:
            chunk = sock.recv(4096)
            if not chunk: raise RenderError("Connection closed.")
            buf.extend(chunk)
        return buf