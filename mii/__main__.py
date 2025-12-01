# mii/__main__.py
import argparse
import sys
from .builder import build_backend

def main():
    parser = argparse.ArgumentParser(prog="miipy")
    subparsers = parser.add_subparsers(dest="command")
    
    # Build Command
    build_parser = subparsers.add_parser("build", help="Compile the C++ backend")
    
    args = parser.parse_args()
    
    if args.command == "build":
        try:
            build_backend()
        except Exception as e:
            print(f"Build failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()