import os
import sys

# Import all necessary components from the library
from mii import (
    MiiPy,
    ViewType,
    Expression,
    ClothesColor,
    PantsColor
)

# CONFIGURATION
# The demo assumes this Mii file is in the project's root directory.
MII_FILE = "mii_016.ffsd"
# The library itself will automatically find FFLResHigh.dat inside the FFL-Testing folder.

def main():
    """
    This demo showcases the main features of the MiiPy library,
    from simple rendering to more advanced customization.
    """
    # 1. Pre-flight Checks
    if not os.path.exists(MII_FILE):
        print(f"Error: Example Mii file not found at '{MII_FILE}'")
        print("   Please place a valid .ffsd file in the project root.")
        return

    print("[*] Initializing MiiPy (this might build the backend on first run)...")

    try:
        # 2. Initialize the Library
        # Using a 'with' block ensures the C++ backend is started and stopped safely.
        # 'show_logs=False' is the default for a clean user experience.
        with MiiPy(show_logs=False) as renderer:

            # EXAMPLE 1: Standard Face Render
            print("\n[-] Rendering a standard face...")
            renderer.render(
                source=MII_FILE,
                out="1_face_standard.png",
                size=512  # Render at 512x512 pixels
            )
            print("    -> Saved to 1_face_standard.png")

            # EXAMPLE 2: Full Body with Custom Colors & Rotation
            print("\n[-] Rendering a full body with custom colors...")
            renderer.render(
                source=MII_FILE,
                out="2_body_custom.png",
                size=512,
                view=ViewType.ALL_BODY,    # Tell the renderer to draw the full body
                zoom=1200,                 # Zoom out to ensure the full body fits in the frame
                clothes_color=ClothesColor.BLUE,
                pants_color=PantsColor.GRAY,
                model_rot=(0, 30, 0)       # Rotate the Mii 30 degrees to the side
            )
            print("    -> Saved to 2_body_custom.png")

            # EXAMPLE 3: Advanced Action Shot
            print("\n[-] Rendering an action shot with a different expression and camera angle...")
            renderer.render(
                source=MII_FILE,
                out="3_action_shot.png",
                size=512,
                view=ViewType.ALL_BODY,
                zoom=1400,
                expression=Expression.SURPRISE_OPEN_MOUTH,
                camera_rot=(15, 20, -5), # Tilt the camera down, to the side, and roll slightly
                model_rot=(0, -45, 10)   # Make the Mii face away and lean
            )
            print("    -> Saved to 3_action_shot.png")

            # EXAMPLE 4: Rendering from Bytes in Memory
            print("\n[-] Rendering from an in-memory bytes object...")
            
            # Simulate loading data from a database or network request
            with open(MII_FILE, "rb") as f:
                mii_data_bytes = f.read()
            
            # The render function accepts the bytes object directly
            image_object = renderer.render(
                source=mii_data_bytes,
                expression=Expression.LIKE
            )
            
            # You can save the returned PIL Image object yourself
            image_object.save("4_from_bytes.png")
            print("    -> Saved to 4_from_bytes.png")

        print("\n Demo finished successfully! Check the output PNG files in your project root.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()