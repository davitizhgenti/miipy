# MiiPy

MiiPy is a Python library that produces clear and sharp images of Nintendo Miis. It wraps the FFL-Testing C++ backend and hides the strain of building and running native code. It lets you focus on the task, not the tools.

## Features

- **Automatic Backend Build**: The renderer builds itself on first use.  
- **Clean Python API**: A single call renders a Mii.  
- **Flexible Input**: Accepts `.ffsd` files or raw 96-byte data.  
- **Rich Rendering Options**: Control size, zoom, expression, and view.  
- **Cross-Platform**: Works on Linux and Windows.  
- **Managed Resources**: The backend starts and stops on its own and cleans up temporary files.

## Prerequisites

The backend is native code, so you need a working C++ build setup.

### Windows

- Git  
- CMake  
- Visual Studio with the “Desktop development with C++” workload  

### Linux (Debian/Ubuntu)

```sh
sudo apt-get update
sudo apt-get install git build-essential cmake libglfw3-dev libgl1-mesa-dev
````

## Installation

> **Note:** Not yet published to PyPI.

```sh
pip install miipy
```

The first import clones the C++ sources and builds the backend. This runs once.

## Usage

### Step 1: Required Resource File

You must supply **FFLResHigh.dat**, obtained from a legitimate Wii U dump.
Place it inside the `FFL-Testing` folder before running any code.

### Step 2: Basic Example

```python
from mii import MiiPy, Expression, ViewType
import os

MII_FILE = "path/to/your/mii.ffsd"

try:
    with MiiPy() as renderer:
        # Simple face render
        renderer.render(
            source=MII_FILE,
            out="my_mii.png",
            size=512
        )

        # Smiling expression returned as PIL Image
        img_obj = renderer.render(
            source=MII_FILE,
            expression=Expression.SMILE,
            zoom=800
        )
        img_obj.save("smile.png")

        # Full body render (needs strong zoom-out)
        renderer.render(
            source=MII_FILE,
            out="body.png",
            view=ViewType.ALL_BODY,
            size=512,
            zoom=1200
        )

        # Render from raw bytes
        with open(MII_FILE, "rb") as f:
            data_bytes = f.read()

        renderer.render(
            source=data_bytes,
            out="from_bytes.png"
        )

except (FileNotFoundError, RuntimeError) as e:
    print(f"An error occurred: {e}")
```

## API Reference

### `MiiPy(port=12346, show_logs=False)`

Main class for rendering Miis.

* **port**: TCP port for the backend.
* **show_logs**: Print backend logs.

### `renderer.render(source, out=None, size=512, **kwargs)`

Render a single image.

* **source**: Path to a `.ffsd` file or raw 96-byte data.
* **out**: Output PNG path. If `None`, returns a Pillow Image.
* **size**: Final image resolution.
* **kwargs**: Extra render controls. Common options:

  * `zoom`: Field-of-view control. Higher values pull the camera back.
  * `expression`: A facial expression (`Expression.SMILE`, etc.).
  * `view`: Which part to render (`ViewType.ALL_BODY`, etc.).
  * `clothes_color`: Shirt color (`ClothesColor.BLUE`).
  * `model_rot`: A rotation tuple `(X, Y, Z)`.

## Troubleshooting

* **Build failure**: Missing compilers or libraries. Check prerequisites.
* **Backend fails to start**:

  * Ensure `FFLResHigh.dat` exists in `FFL-Testing`.
  * Check file permissions or corruption.
  * Headless Linux may require `xvfb-run`.
* **Git submodule errors**: Verify Git and network access.

## For Developers

Clone with the C++ submodule:

```sh
git clone --recursive https://github.com/yourusername/miipy
cd miipy
pip install -e .
```

Rebuild manually:

```sh
python -m mii.builder
```

Do a full reset and rebuild:

```sh
python -m mii.builder --reset --resource path/to/FFLResHigh.dat
```

## Acknowledgements

This project builds on the FFL-Testing work by Arian Kordi and the wider homebrew and reverse-engineering community.

## License

Released under the MIT License.

**Note:** Nintendo assets such as `FFLResHigh.dat` are not included and remain under their original licenses.
