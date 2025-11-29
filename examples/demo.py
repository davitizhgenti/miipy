import os
import sys
from mii import MiiPy, Expression

def main():
    """
    This demo shows how to use the MiiPy library.
    It will automatically build the backend on the first run.
    """
    # --- PRE-REQUISITE ---
    # The user must place 'FFLResHigh.dat' inside the 'FFL-Testing' folder.
    mii_file_path = "./mii_016.ffsd"
    if not os.path.exists(mii_file_path):
        print(f"❌ Mii file not found at '{mii_file_path}'")
        return

    try:
        # Initialize MiiPy. No resource path is needed.
        # The library will build itself if the executable is missing.
        print("[*] Initializing MiiPy...")
        with MiiPy() as renderer:
            
            print("[-] Rendering a standard face...")
            renderer.render(mii_file_path, "output_face.png")
            print("    -> Saved to output_face.png")

            print("[-] Rendering a smile...")
            renderer.render(mii_file_path, "output_smile.png", expression=Expression.SMILE)
            print("    -> Saved to output_smile.png")

        print("\n✅ Demo finished successfully!")

    except Exception as e:
        print(f"\n❌ An error occurred: {e}")

if __name__ == "__main__":
    main()