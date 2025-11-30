# MiiPy

**MiiPy** is a Python library for rendering high-quality images of Nintendo Miis. It acts as a user-friendly wrapper around the powerful **FFL-Testing** C++ backend, automating the entire compilation and execution lifecycle.

**This library is designed for developers who need to generate Mii images programmatically without the hassle of manually compiling and managing C++ dependencies.**

## Features

* **Automatic Backend Compilation** **: Compiles the C++ renderer on first use during installation.**
* **Simple and Pythonic API** **: Render Miis with a single, intuitive function call.**
* **Flexible Input** **: Accepts Mii data from **.ffsd** files or raw **bytes** objects.**
* **Highly Customizable Renders** **: Control image size, zoom, Mii expression, and view type (face/body).**
* **Cross-Platform** **: Works on Linux and Windows (macOS is currently unsupported).**
* **Resource Management** **: Automatically starts and stops the backend process, cleaning up temporary files.**

## Prerequisites

Because this library compiles C++ source code on your machine, you **must** have a complete build environment installed and available in your system's PATH.

#### On Windows:

* **Git :** Download and install from [git-scm.com](https://www.google.com/url?sa=E&q=https%3A%2F%2Fgit-scm.com%2Fdownload%2Fwin).
* **CMake :** Download and install from [cmake.org](https://www.google.com/url?sa=E&q=https%3A%2F%2Fcmake.org%2Fdownload%2F).
* **Visual Studio : Install the "Desktop development with C++" workload from the Visual Studio Installer.**

#### On Linux (Debian/Ubuntu):

* **Git** **:**

```
    sudo apt-get update
    sudo apt-get install git
  
```

* **Build Tools & CMake** **:**
* **OpenGL/GLFW Libraries** **:**

```
    sudo apt-get install libglfw3-dev libgl1-mesa-dev
  
```

## Installation (Not yet developed)

**You can install MiiPy directly from PyPI :**

```
    pip install miipy
  
```

**The first time you import the library, it will automatically attempt to clone the required C++ submodules and compile the backend. This may take a few minutes and will only happen once.**

## Usage

### Step 1: Obtain **FFLResHigh.dat**

This library **cannot function** without the official **FFLResHigh.dat** resource file from a Nintendo Wii U. This file is copyrighted and **is not included**. You must acquire it from a legitimate source (e.g., your own system dump) and place it in the **FFL-Testing** folder within your project **before** running the code.

### Step 2: Code Example

**The primary interface is the **MiiPy** class. It is highly recommended to use a **with** statement to ensure the backend process is properly managed and shut down.**

```
from miipy import MiiPy, Expression, ViewType
import os

# The library requires FFLResHigh.dat to be in the FFL-Testing folder.
# This script assumes you've placed it there.
MII_FILE = "path/to/your/mii.ffsd" # A valid 96-byte Mii data file

try:
    # Initialize the renderer. This will auto-build the backend if it's the first run.
    # The constructor finds FFLResHigh.dat inside the FFL-Testing folder.
    with MiiPy() as renderer:

        # --- Example 1: Simple render to a file ---
        print("Rendering standard face...")
        renderer.render(
            source=MII_FILE,
            out="my_mii.png",
            size=512
        )

        # --- Example 2: Change expression and get a PIL Image object ---
        print("Rendering a smiling Mii...")
        img_obj = renderer.render(
            source=MII_FILE,
            expression=Expression.SMILE,
            zoom=800 # Zoom out to see the head better
        )
        img_obj.save("smile.png")

        # --- Example 3: Render the full body ---
        print("Rendering full body...")
        renderer.render(
            source=MII_FILE,
            out="body.png",
            view=ViewType.BODY,
            size=1024 # Higher resolution
        )
  
        # --- Example 4: Render from raw bytes in memory ---
        print("Rendering from in-memory bytes...")
        with open(MII_FILE, "rb") as f:
            mii_data_bytes = f.read()
  
        renderer.render(
            source=mii_data_bytes,
            out="from_bytes.png"
        )

except (FileNotFoundError, RuntimeError) as e:
    print(f"An error occurred: {e}")
  
```

## API Reference

#### MiiPy(port=12346, show_logs=False)

**The main class for interacting with the renderer.**

* **port** **: The TCP port for the backend service. Defaults to **12346**.**
* **show_logs** **: If **True**, all logs from the Python and C++ backend will be printed to the console. Useful for debugging. Defaults to **False**.**

---

#### renderer.render(source, out=None, size=512, zoom=None, expression=Expression.NORMAL, view=ViewType.FACE)

**Renders a single Mii image.**

* **source** **: Required. Can be a file path (**str**) to a **.ffsd** file or a raw **bytes** object of Mii data (must be 96 bytes).**
* **out** **: Optional. The file path where the output PNG will be saved. If **None**, a Pillow **Image** object is returned instead.**
* **size** **: The resolution of the output image (e.g., **512** for a 512x512 image).**
* **zoom** **: Controls the camera's field of view. A higher value "zooms out," making the Mii appear smaller in the frame. Defaults to the **size** value.**
* **expression** **: The Mii's facial expression. Use the **Expression** enum (e.g., **Expression.SMILE**, **Expression.ANGER**).**
* **view** **: The part of the Mii to render. Use the **ViewType** enum (**ViewType.FACE** or **ViewType.BODY**).**

## Troubleshooting

* **FileNotFoundError: FFLResHigh.dat not found** **: You must place **FFLResHigh.dat** inside the **FFL-Testing** directory before running the code.**
* **RuntimeError: Build Failed** **: This means the C++ compilation failed. You are likely missing a prerequisite (CMake, g++, or OpenGL development libraries). Check the build logs in your console for specific error messages.**
* **RuntimeError: Backend failed to start** **:**
* **On Linux, this often happens in a "headless" environment (like a server or Docker container) that lacks a virtual display. Try running your script with **xvfb-run** (**sudo apt install xvfb**).**
* **This can also happen if the **FFLResHigh.dat** file is corrupted, empty, or has incorrect read permissions.**
* **git submodule** errors during installation**** **: Ensure you have Git installed and that your network connection can access GitHub.**

## For Developers

**To work on this project locally, clone the repository with the **--recursive** flag to fetch the C++ submodule:**

```
    git clone --recursive https://github.com/yourusername/miipy
    cd miipy
    pip install -e .
  
```

**You can then trigger a manual rebuild at any time:**

```
    python -m miipy.builder
  
```

## Acknowledgements

This library would not be possible without the incredible work of [Arian Kordi (ariankordi)](https://github.com/ariankordi) and the [FFL-Testing](https://github.com/ariankordi/FFL-Testing) library, which serves as the core rendering engine.

**MiiPy
 is built upon the efforts of many others in the reverse-engineering and
 homebrew communities. Please support their work and follow their
projects.**

## License

This project is licensed under the MIT License - see the LICENSE file for details.

**Disclaimer: The underlying **FFL-Testing** library and the required Nintendo assets (**FFLResHigh.dat**) are subject to their own licenses and terms of use. This project does not distribute any copyrighted Nintendo assets.**
