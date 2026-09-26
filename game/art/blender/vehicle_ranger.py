"""Rebuild the ranger reference vehicle and its articulated Blender scene."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vehicle_fidelity import main as build_vehicle


def main():
    return build_vehicle('ranger')


if __name__ == '__main__':
    main()
