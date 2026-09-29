# mii/__main__.py
import argparse
import logging
import sys

from .builder import build_backend
from .exceptions import BuildError


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="python -m mii")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Compile the C++ backend")
    build_parser.add_argument("--reset", action="store_true",
                              help="Reset git submodule to clean state before building")
    build_parser.add_argument("--resource", type=str,
                              help="Path to your FFLResHigh.dat file (will be copied)")

    args = parser.parse_args()

    if args.command == "build":
        try:
            build_backend(reset=args.reset, resource=args.resource)
        except BuildError as e:
            print(f"Build failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
