from __future__ import annotations
import importlib
import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
import imageio.v2 as imageio

from .stubs_gpio import install_as_rpi
from .fake_platform import apply as apply_fake_platform

SNAP_DIR = Path(__file__).resolve().parent.parent / "Snapshots"


def _install_mido_stub():
    """
    Provide a minimal 'mido' stub so upstream code can import and call it
    without requiring any backend (rtmidi/portmidi/pygame).
    Covers: open_input/open_output, Message, MidiFile, MetaMessage, bpm/tempo helpers.
    """
    import types, sys as _sys
    if "mido" in _sys.modules:
        return  # already loaded; assume workable
    m = types.ModuleType("mido")

    # Basic messages
    class Message:
        def __init__(self, *a, **k): pass
        def copy(self, **kw): return self

    class MetaMessage(Message):
        def __init__(self, *a, **k): super().__init__(*a, **k)

    # Very small MidiFile shim
    class MidiTrack(list):
        def __init__(self, *a, **k): super().__init__()

    class MidiFile:
        def __init__(self, filename=None, **kwargs):
            self.filename = filename
            self.tracks = []
            self.ticks_per_beat = 480
            # Don't actually parse; tool doesn't need MIDI audio
            if filename:
                # keep empty tracks; pretend loaded
                pass
        def save(self, filename):
            # no-op
            self.filename = filename
        def __iter__(self):
            return iter(self.tracks)

    class _Port:
        def __init__(self, name=""):
            self.name = name
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): self.close()
        def close(self): pass
        def send(self, msg): pass
        def receive(self, block=False): return None
        def callback(self, *a, **k): pass
        def poll(self): return None

    def get_input_names(): return []
    def get_output_names(): return []
    def open_input(name=None, virtual=None, callback=None): return _Port(name or "input")
    def open_output(name=None, virtual=None): return _Port(name or "output")

    # Common helpers some code imports
    def bpm2tempo(bpm): 
        try: return int(60_000_000 / float(bpm))
        except Exception: return 500000
    def tempo2bpm(tempo):
        try: return 60_000_000 / float(tempo)
        except Exception: return 120.0
    def merge_tracks(tracks): 
        # return a shallow merged list
        out = []
        for t in tracks: out.extend(list(t))
        return out
    def tick2second(tick, ticks_per_beat, tempo):
        return (tick / float(ticks_per_beat)) * (tempo / 1_000_000.0)
    def second2tick(second, ticks_per_beat, tempo):
        return int(second * 1_000_000.0 * ticks_per_beat / float(tempo))

    m.get_input_names = get_input_names
    m.get_output_names = get_output_names
    m.open_input = open_input
    m.open_output = open_output
    m.Message = Message
    m.MetaMessage = MetaMessage
    m.MidiFile = MidiFile
    m.MidiTrack = MidiTrack
    m.bpm2tempo = bpm2tempo
    m.tempo2bpm = tempo2bpm
    m.merge_tracks = merge_tracks
    m.tick2second = tick2second
    m.second2tick = second2tick

    _sys.modules["mido"] = m



class BridgeError(Exception):
    pass



class MenuLCDBridge:
    """
    Thin wrapper around lib/menulcd.py from the original repo.
    - No reimplementation of rendering: we only fetch the PIL framebuffer.
    - Builds the upstream graph similar to visualizer.py: ArgumentParser -> ComponentInitializer.
    """
    def __init__(self, repo_path: Path, logger: Optional[logging.Logger] = None, display_profile: str | None = None):
        self.logger = logger or logging.getLogger("MenuLCDBridge")
        self.errors: List[str] = []
        self.repo_path = Path(repo_path)
        self.menulcd_module = None
        self.instance = None
        self._native_size = (320, 240)
        self._last_frame: Optional[Image.Image] = None
        self._created_ts = 0.0

        # Optional override: '1in44' (128x128) or '1in3' (240x240)
        self.display_profile = display_profile

        install_as_rpi()
        apply_fake_platform()
        
        self._import_and_create()

    # --------- Public API ---------
    def native_size(self) -> Tuple[int, int]:
        return self._native_size

    def get_frame(self) -> Optional[Image.Image]:
        try:
            frame = self._extract_frame(self.instance)
            if frame is not None:
                self._last_frame = frame
            return self._last_frame
        except Exception as e:
            self._push_error(f"get_frame failed: {e}")
            return self._last_frame

    def step(self):
        if not self.instance:
            return
        # Try common methods on MenuLCD itself
        for name in ("render","draw","update","tick","loop","paint","display","refresh","render_menu","renderMenu"):
            meth = getattr(self.instance, name, None)
            if callable(meth):
                try:
                    meth()
                    return
                except Exception as e:
                    self._push_error(f"{name}() error: {e}")
        # Try on nested LCD object
        lcd = getattr(self.instance, "LCD", None)
        if lcd is not None:
            for lname in ("display","refresh","show","update","LCD_Display","LCD_Show"):
                lm = getattr(lcd, lname, None)
                if callable(lm):
                    try:
                        lm()
                        return
                    except Exception as e:
                        self._push_error(f"LCD.{lname}() error: {e}")
    
    def reload(self):
        self.logger.info("Reloading MenuLCD...")
        try:
            self._import_and_create()
        except Exception as e:
            self._push_error(f"Reload failed: {e}")
            raise

    def set_repo(self, new_repo: Path):
        self.repo_path = Path(new_repo)
        self.reload()

    # ----- Actions -----
    def action_up(self): print('[BRIDGE] fallback to: ' + r'"button_up","on_up","nav_up","up"'); self._call_if_exists(("button_up","on_up","nav_up","up"))
    def action_down(self): print('[BRIDGE] fallback to: ' + r'"button_down","on_down","nav_down","down"'); self._call_if_exists(("button_down","on_down","nav_down","down"))
    def action_left(self): print('[BRIDGE] fallback to: ' + r'"button_left","on_left","nav_left","left"'); self._call_if_exists(("button_left","on_left","nav_left","left"))
    def action_right(self): print('[BRIDGE] fallback to: ' + r'"button_right","on_right","nav_right","right"'); self._call_if_exists(("button_right","on_right","nav_right","right"))
    def action_enter(self): print('[BRIDGE] fallback to: ' + r'"button_enter","on_enter","select","enter","ok"'); self._call_if_exists(("button_enter","on_enter","select","enter","ok"))
    def action_back(self): print('[BRIDGE] fallback to: ' + r'"button_back","on_back","back","cancel"'); self._call_if_exists(("button_back","on_back","back","cancel"))
    def action_home(self):
        print('[BRIDGE] action_home')
        if self._call_if_exists(('home','go_home','to_root','menu_home'), swallow=True):
            return
        for _ in range(5):
            self.action_back()
    def action_encoder(self, delta):
        print('[BRIDGE] action_encoder delta=' + str(delta))
        if self._call_if_exists(('encoder','on_encoder','rotate','on_rotate'), args=(delta,), swallow=True):
            return
        if delta > 0:
            for _ in range(abs(delta)):
                self.action_down()
        elif delta < 0:
            for _ in range(abs(delta)):
                self.action_up()
    def snapshot_png(self) -> Path:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        p = SNAP_DIR / f"snapshot_{ts}.png"
        frame = self.get_frame()
        if frame is None:
            raise BridgeError("No frame to save.")
        frame.save(p)
        return p

    def record_gif(self, seconds=5, fps=10) -> Path:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        p = SNAP_DIR / f"record_{ts}.gif"
        frames: List[Image.Image] = []
        interval = 1.0 / fps
        t0 = time.time()
        while time.time() - t0 < seconds:
            self.step()
            fr = self.get_frame()
            if fr:
                frames.append(fr.copy())
            time.sleep(max(0.0, interval - 0.001))
        if not frames:
            raise BridgeError("No frames captured for GIF.")
        imageio.mimsave(p, frames, duration=1.0/fps, palettesize=256)
        return p

    def pop_errors(self) -> List[str]:
        out = self.errors[:]
        self.errors.clear()
        return out

    # --------- Internals ---------
    def _import_and_create(self):
        _install_mido_stub()  # ensure 'mido' is available with a stub

        # Put repo on sys.path and switch CWD so 'config/*.xml' relative paths resolve
        r = str(self.repo_path)
        if r not in sys.path:
            sys.path.insert(0, r)
        old_cwd = os.getcwd()
        os.chdir(r)
        try:
            lib_path = self.repo_path / "lib" / "menulcd.py"
            if not lib_path.exists():
                raise BridgeError(f"Missing file: {lib_path}")

            # 1) Load argument parser
            arg_parser = self._reload("lib.argument_parser")
            # Guard sys.argv so upstream parser doesn't choke on our extra CLI flags (e.g., --lcd)
            _saved_argv = sys.argv[:]
            sys.argv = [sys.argv[0]]
            try:
                Parser = getattr(arg_parser, "ArgumentParser", None)
                if Parser is None:
                    raise BridgeError("lib.argument_parser.ArgumentParser not found")
            finally:
                sys.argv = _saved_argv

            # 2) Patch platform BEFORE binding in component_initializer
            plat_mod = self._reload("lib.platform")
            try:
                _HotspotOrig = getattr(plat_mod, "Hotspot", None)
                class _HotspotNoop:
                    def __init__(self, platform):
                        self.platform = platform
                    def start(self): pass
                    def stop(self): pass
                if _HotspotOrig is not None:
                    setattr(plat_mod, "Hotspot", _HotspotNoop)
            except Exception:
                pass

            # 3) Now (re)load component_initializer so it binds to the patched Hotspot
            comp_init = self._reload("lib.component_initializer")

            # 4) Load menulcd (not strictly required here, but keeps parity)
            self.menulcd_module = self._reload("lib.menulcd")

            # Build args with desktop-friendly defaults
            args = Parser().args
            args.appmode = "app"
            args.leddriver = "emu"
            args.webinterface = "false"
            # Optional display override
            if self.display_profile in ('1in44', '1in3'):
                args.display = self.display_profile

            # Fonts: try repo/fonts or env override
            candidate_dirs = [
                str(self.repo_path / "fonts"),
                str(self.repo_path / "Fonts"),
                os.environ.get("PIANO_LED_FONTDIR", ""),
            ]
            for d in candidate_dirs:
                if not d:
                    continue
                f1 = Path(d)/"FreeSansBold.ttf"
                f2 = Path(d)/"FreeMonoBold.ttf"
                if f1.exists() and f2.exists():
                    args.fontdir = d
                    break

            CI = getattr(comp_init, "ComponentInitializer", None)
            if CI is None:
                raise BridgeError("lib.component_initializer.ComponentInitializer not found")
            try:
                ci = CI(args)
            except Exception as e:
                msg = str(e)
                if "FreeSansBold.ttf" in msg or "FreeMonoBold.ttf" in msg:
                    self._push_error("Missing fonts FreeSansBold.ttf / FreeMonoBold.ttf. "
                                     "Place them in <repo>/fonts or set PIANO_LED_FONTDIR.")
                raise

            self.instance = ci.menu

            # Determine native size
            self.step()
            img = self._extract_frame(self.instance)
            if img:
                self._native_size = (img.width, img.height)

            self._created_ts = time.time()
        finally:
            os.chdir(old_cwd)

    def _reload(self, name: str):
        if name in sys.modules:
            return importlib.reload(sys.modules[name])
        return importlib.import_module(name)

    def _extract_frame(self, inst) -> Optional[Image.Image]:
        for name in ("get_frame", "get_framebuffer", "framebuffer", "image", "frame"):
            obj = getattr(inst, name, None)
            if callable(obj):
                try:
                    img = obj()
                    if isinstance(img, Image.Image):
                        return img
                except Exception:
                    pass
            else:
                if isinstance(obj, Image.Image):
                    return obj
        for _, v in vars(inst).items():
            if isinstance(v, Image.Image):
                return v
        # Nested LCD object scan
        lcd = getattr(inst, "LCD", None)
        if lcd is not None:
            # direct attributes
            for name in ("frame","image","framebuffer","newimage","buffer"):
                obj = getattr(lcd, name, None)
                if isinstance(obj, Image.Image):
                    return obj
            for _, v in vars(lcd).items():
                if isinstance(v, Image.Image):
                    return v
        return None

    def _call_if_exists(self, candidates: tuple, args: tuple = (), swallow: bool=False) -> bool:
        for name in candidates:
            f = getattr(self.instance, name, None)
            if callable(f):
                try:
                    f(*args)
                    return True
                except Exception as e:
                    self._push_error(f"{name} error: {e}")
                    if not swallow:
                        raise
        handler = getattr(self.instance, "handle_key", None)
        if callable(handler) and candidates:
            try:
                handler(candidates[0])
                return True
            except Exception as e:
                self._push_error(f"handle_key error: {e}")
                if not swallow:
                    raise
        return False

    def _push_error(self, msg: str):
        self.errors.append(str(msg))
        self.logger.error(msg)

    def action_up(self):
        print('[BRIDGE] action_up -> change_pointer(-1)')
        f = getattr(self.instance, 'change_pointer', None)
        if callable(f):
            try:
                f(-1)
                return
            except Exception as e:
                self._push_error(f'change_pointer(-1) error: {e}')
        self._call_if_exists(('button_up','on_up','nav_up','up'))

    def action_down(self):
        print('[BRIDGE] action_down -> change_pointer(+1)')
        f = getattr(self.instance, 'change_pointer', None)
        if callable(f):
            try:
                f(1)
                return
            except Exception as e:
                self._push_error(f'change_pointer(1) error: {e}')
        self._call_if_exists(('button_down','on_down','nav_down','down'))

    def action_left(self):
        print('[BRIDGE] action_left -> change_value("LEFT")')
        f = getattr(self.instance, 'change_value', None)
        if callable(f):
            try:
                f('LEFT')
                return
            except Exception as e:
                self._push_error(f"change_value('LEFT') error: {e}")
        self._call_if_exists(('button_left','on_left','nav_left','left'))

    def action_right(self):
        print('[BRIDGE] action_right -> change_value("RIGHT")')
        f = getattr(self.instance, 'change_value', None)
        if callable(f):
            try:
                f('RIGHT')
                return
            except Exception as e:
                self._push_error(f"change_value('RIGHT') error: {e}")
        self._call_if_exists(('button_right','on_right','nav_right','right'))

    def action_enter(self):
        print('[BRIDGE] action_enter -> enter_menu()')
        f = getattr(self.instance, 'enter_menu', None)
        if callable(f):
            try:
                f()
                return
            except Exception as e:
                self._push_error(f'enter_menu() error: {e}')
        self._call_if_exists(('button_enter','on_enter','select','enter','ok'))

    def action_back(self):
        print('[BRIDGE] action_back -> go_back()')
        f = getattr(self.instance, 'go_back', None)
        if callable(f):
            try:
                f()
                return
            except Exception as e:
                self._push_error(f'go_back() error: {e}')
        self._call_if_exists(('button_back','on_back','back','cancel'))


    def set_display_profile(self, profile: str | None, reload: bool = True):
        """Set display profile to '1in44' or '1in3' (None to auto/default)."""
        if profile not in (None, '1in44', '1in3'):
            raise BridgeError("Invalid display profile (expected '1in44' or '1in3' or None)")
        self.display_profile = profile
        if reload:
            self.reload()
