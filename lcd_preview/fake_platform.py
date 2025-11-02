"""
Utilities to coerce the visualizer to use null/simulated drivers on non-RPi.
If the upstream code branches on platform/system checks, we can tweak env vars.
"""
import os

def apply():
    # Generic hints often used by projects
    os.environ.setdefault("PLATFORM", "SIMULATED")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    # Nothing else is strictly necessary; our RPi.GPIO stub will already prevent HW access.