"""
Minimal-but-compatible stub for RPi.GPIO so upstream code (LCD_Config, etc.) can run on desktop.
Implements common API: setmode, setwarnings, setup, input, output, add_event_detect, PWM, cleanup...
"""
from __future__ import annotations
import sys
import types
from typing import Callable, Dict, List, Optional

# Mode constants
BCM = 11
BOARD = 10

# Direction
IN = 0
OUT = 1

# Pull-up/down
PUD_UP = 2
PUD_DOWN = 3
PUD_OFF = 4

# Edge detect
RISING = 5
FALLING = 6
BOTH = 7

# Levels
HIGH = 1
LOW = 0

_callbacks: Dict[int, Callable] = {}
_channel_edges: Dict[int, int] = {}
_mode = BCM
_warnings = False

# Track pin states for OUT pins (purely informational for debugging)
_pin_state: Dict[int, int] = {}
_pin_dir: Dict[int, int] = {}

def setmode(mode):
    global _mode
    _mode = mode

def getmode():
    return _mode

def setwarnings(flag: bool):
    global _warnings
    _warnings = bool(flag)

def setup(channel: int, mode: int, pull_up_down: Optional[int]=None, initial: Optional[int]=None):
    _pin_dir[channel] = mode
    if initial is not None:
        _pin_state[channel] = initial

def input(channel: int) -> int:
    # For simulation, return LOW unless previously set HIGH
    return _pin_state.get(channel, LOW)

def output(channel: int, value: int):
    _pin_state[channel] = HIGH if value else LOW

def add_event_detect(channel: int, edge: int, callback: Callable, bouncetime: Optional[int]=None):
    _callbacks[channel] = callback
    _channel_edges[channel] = edge

def remove_event_detect(channel: int):
    _callbacks.pop(channel, None)
    _channel_edges.pop(channel, None)

class _PWM:
    def __init__(self, channel: int, freq: float):
        self.channel = channel
        self.freq = freq
        self.duty = 0.0
        self.running = False
    def start(self, duty: float):
        self.duty = duty
        self.running = True
    def ChangeDutyCycle(self, duty: float):
        self.duty = duty
    def stop(self):
        self.running = False

def PWM(channel: int, freq: float) -> _PWM:
    return _PWM(channel, freq)

def cleanup(channel: Optional[int]=None):
    if channel is None:
        _callbacks.clear()
        _channel_edges.clear()
        _pin_state.clear()
        _pin_dir.clear()
    else:
        _callbacks.pop(channel, None)
        _channel_edges.pop(channel, None)
        _pin_state.pop(channel, None)
        _pin_dir.pop(channel, None)

def simulate_edge(channel: int):
    """Invoke the callback associated with a given channel as if an edge occurred."""
    cb = _callbacks.get(channel)
    if cb:
        try:
            cb(channel)  # many GPIO callbacks expect the channel arg
        except TypeError:
            cb()  # fallback: callback without arg

def registered_channels() -> List[int]:
    return list(_callbacks.keys())

# ---- Installer: make 'import RPi.GPIO as GPIO' succeed ----
def install_as_rpi():
    if "RPi" not in sys.modules:
        pkg = types.ModuleType("RPi")
        sys.modules["RPi"] = pkg
    sys.modules["RPi.GPIO"] = sys.modules[__name__]