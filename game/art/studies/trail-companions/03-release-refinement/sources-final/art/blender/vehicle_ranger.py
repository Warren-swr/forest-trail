"""Rebuild the release-based Kestrel refinement and articulated Blender scene."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vehicle_release_refinement import main as build_vehicle


def main():
    return build_vehicle('ranger')


if __name__ == '__main__':
    main()
