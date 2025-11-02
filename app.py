# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PianoLCDExactPreview - Windows desktop previewer for onlaj/Piano-LED-Visualizer LCD,
using the original lib/menulcd.py renderer (no reimplementation).
"""
from __future__ import annotations
import os
import sys
import time
import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize, Signal, Slot
import argparse
from PySide6.QtGui import QAction, QKeySequence, QGuiApplication, QWheelEvent, QCloseEvent
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog, QLabel, QVBoxLayout,
    QDockWidget, QTextEdit, QToolBar, QComboBox, QMessageBox, QPushButton, QHBoxLayout
)

from lcd_preview.qimage_from_pil import pil_to_qimage
from lcd_preview.bootstrap_repo import Bootstrap
from lcd_preview.menulcd_bridge import MenuLCDBridge, BridgeError
from lcd_preview.menu_controller import MenuController
from lcd_preview.watcher import RepoWatcher

APP_NAME = "PianoLCDExactPreview"
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "previewer.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(APP_NAME)



class SafeLabel(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lbl = QLabel(text, self)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

class LCDViewport(QWidget):
    """Widget that displays the PIL framebuffer via QImage with integer nearest-neighbor upscale."""
    def __init__(self, bridge: MenuLCDBridge, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.bridge = bridge
        self.scale = 2  # default integer scale
        self.fps = 0.0
        self._last_fps_ts = time.time()
        self._frame_counter = 0
        self._flash_reload_until = 0.0  # timestamp for 'reloaded' flash

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000 // 30)  # 30 fps UI refresh is plenty, LCD content updates on demand

    def minimumSizeHint(self):
        w, h = self.bridge.native_size()
        return QSize(w, h)

    def sizeHint(self):
        w, h = self.bridge.native_size()
        return QSize(w * self.scale, h * self.scale)

    def set_scale(self, scale: int):
        if scale < 1:
            scale = 1
        self.scale = int(scale)
        self.updateGeometry()
        self.update()

    def flash_reloaded(self):
        self._flash_reload_until = time.time() + 0.8

    def _tick(self):
        try:
            # Step the bridge (lets MenuLCD render if it has a tick/update)
            self.bridge.step()
        except Exception as e:
            logger.exception("Bridge step failed: %s", e)
        self.update()

        # FPS calc (widget paint FPS; the underlying LCD render may be different)
        self._frame_counter += 1
        now = time.time()
        if now - self._last_fps_ts >= 1.0:
            self.fps = self._frame_counter / (now - self._last_fps_ts)
            self._frame_counter = 0
            self._last_fps_ts = now

    def paintEvent(self, ev):
        painter = None
        try:
            frame = self.bridge.get_frame()  # PIL.Image (native resolution)
            if frame is None:
                return
            # upscale with PIL NEAREST by exact integer factor only
            if self.scale!= 1:
                up = frame.resize((frame.width * self.scale, frame.height * self.scale), resample=0)  # Image.NEAREST
            else:
                up = frame
            qimg = pil_to_qimage(up)
            from PySide6.QtGui import QPainter, QPen, QColor
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setRenderHint(QPainter.TextAntialiasing, False)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

            # center the image
            x = (self.width() - qimg.width()) // 2
            y = (self.height() - qimg.height()) // 2
            painter.drawImage(x, y, qimg)

            # Optional flash border after reload
            if time.time() < self._flash_reload_until:
                pen = QPen(QColor(0, 200, 0))
                pen.setWidth(4)
                painter.setPen(pen)
                painter.drawRect(x, y, qimg.width()-1, qimg.height()-1)
        finally:
            if painter is not None:
                painter.end()


class MainWindow(QMainWindow):
    def __init__(self, lcd_override: str | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        self.bootstrap = Bootstrap(APP_NAME)
        repo_path = self.bootstrap.ensure_repo_path(self)

        self.bridge = None
        self.viewport = None
        try:
            disp = None
            if lcd_override in ('128','1in44'): disp = '1in44'
            elif lcd_override in ('240','1in3'): disp = '1in3'
            else:
                try:
                    from lcd_preview.bootstrap_repo import SETTINGS_FILE
                    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                        _s = json.load(f)
                        if _s.get('display_profile') in ('1in44','1in3'):
                            disp = _s['display_profile']
                except Exception:
                    pass
            self.bridge = MenuLCDBridge(repo_path, logger=logger, display_profile=disp)
            self.viewport = LCDViewport(self.bridge)
            self.setCentralWidget(self.viewport)
            self.log_line(f"Display profile: {getattr(self.bridge,'display_profile',None) or 'default (auto)'}")
            try:
                self.viewport.setFocus(Qt.OtherFocusReason)
            except Exception:
                pass
        except Exception as e:
            self.setCentralWidget(SafeLabel("Initialization du LCD échouée:\n\n" + str(e) + "\n\nVérifiez le dossier du repo, les polices (FreeSansBold.ttf / FreeMonoBold.ttf) et les fichiers config/*.xml, puis utilisez 'Change Repo…' pour réessayer.", self))

        # Status dock with live info/logs
        self.status_dock = QDockWidget("Status", self)
        self.status_panel = QTextEdit(self.status_dock)
        self.status_panel.setReadOnly(True)
        self.status_dock.setWidget(self.status_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.status_dock)

        # Toolbar
        tb = QToolBar("Controls", self)
        self.addToolBar(tb)

        # --- Keyboard handlers bound to the instance (simulate hardware buttons) ---
        def _mk_action(call):
            def fn():
                try:
                    if self.bridge is not None:
                        getattr(self.bridge, call)()
                        if self.viewport is not None:
                            self.viewport.update()
                except Exception as e:
                    logger.error(f"{call} error: %s", e)
            return fn

        # Bind handlers so shortcuts can call them (exist before creating shortcuts)
        self.on_up = _mk_action("action_up")
        self.on_down = _mk_action("action_down")
        self.on_left = _mk_action("action_left")
        self.on_right = _mk_action("action_right")
        self.on_enter = _mk_action("action_enter")
        self.on_back = _mk_action("action_back")
        self.on_home = _mk_action("action_home")

        # --- Application-wide keyboard shortcuts (independent of focus) ---
        def _mk_shortcut(seq, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ApplicationShortcut)
            try: sc.setAutoRepeat(True)
            except Exception: pass
            sc.activated.connect(fn)
            return sc

        self._shortcuts = [
            _mk_shortcut("Up", self.on_up),
            _mk_shortcut("Down", self.on_down),
            _mk_shortcut("Left", self.on_left),
            _mk_shortcut("Right", self.on_right),
            _mk_shortcut("W", self.on_up),
            _mk_shortcut("S", self.on_down),
            _mk_shortcut("A", self.on_left),
            _mk_shortcut("D", self.on_right),
            _mk_shortcut("K", self.on_up),
            _mk_shortcut("J", self.on_down),
            _mk_shortcut("H", self.on_left),
            _mk_shortcut("L", self.on_right),
            _mk_shortcut("PageUp", self.on_up),
            _mk_shortcut("PageDown", self.on_down),
            _mk_shortcut("Return", self.on_enter),
            _mk_shortcut("Enter", self.on_enter),
            _mk_shortcut("Space", self.on_enter),
            _mk_shortcut("Escape", self.on_back),
            _mk_shortcut("Backspace", self.on_back),
            _mk_shortcut("Home", self.on_home),
        ]

        act_reload = QAction("Reload", self)
        act_reload.setShortcut(QKeySequence("Ctrl+R"))
        act_reload.triggered.connect(self.on_reload)
        tb.addAction(act_reload)

        act_snapshot = QAction("Snapshot PNG", self)
        act_snapshot.setShortcut(QKeySequence("Ctrl+S"))
        act_snapshot.triggered.connect(self.on_snapshot)
        tb.addAction(act_snapshot)

        act_record = QAction("Record GIF (5s@10fps)", self)
        act_record.setShortcut(QKeySequence("Ctrl+G"))
        act_record.triggered.connect(self.on_record_gif)
        tb.addAction(act_record)

        act_home = QAction("Home", self)
        act_home.setShortcut(QKeySequence("Esc"))
        act_home.triggered.connect(self.on_home)
        tb.addAction(act_home)

        # --- LCD Actions (must be declared before menu/toolbar usage) ---
        act_lcd_128 = QAction("LCD 128×128 (1in44)", self)
        act_lcd_240 = QAction("LCD 240×240 (1in3)", self)
        # LCD Menu (after actions are defined)
        lcd_menu = self.menuBar().addMenu("LCD")
        lcd_menu.addAction(act_lcd_128)
        lcd_menu.addAction(act_lcd_240)
        act_lcd_128.triggered.connect(lambda: self.set_lcd_profile('1in44'))
        act_lcd_240.triggered.connect(lambda: self.set_lcd_profile('1in3'))
        # Add to toolbar for quick access
        tb.addAction(act_lcd_128)
        tb.addAction(act_lcd_240)


        # Scale selector (1x/2x/3x...)
        self.scale_combo = QComboBox(self)
        self.scale_combo.addItems([f"{i}x" for i in range(1, 9)])
        self.scale_combo.setCurrentIndex(1)  # 2x default
        self.scale_combo.currentIndexChanged.connect(self.on_scale_changed)
        tb.addWidget(QLabel(" Scale: "))
        tb.addWidget(self.scale_combo)

        # Repo switch button
        btn_repo = QPushButton("Change Repo…", self)
        btn_repo.clicked.connect(self.on_change_repo)
        tb.addWidget(btn_repo)

        # Controller for keyboard/mouse to menu events
        self.controller = None
        if self.bridge is not None and self.viewport is not None:
            self.controller = MenuController(self.bridge, logger=logger)
            self.viewport.installEventFilter(self.controller)

        # Watcher for hot-reload
        self.watcher = None
        if self.bridge is not None:
            watch_paths = [
                self.bridge.repo_path / "config" / "menu.xml",
                self.bridge.repo_path / "config" / "settings.xml",
                self.bridge.repo_path / "config" / "default_settings.xml",
                self.bridge.repo_path / "fonts",
                self.bridge.repo_path / "assets",
            ]
            self.watcher = RepoWatcher(watch_paths, on_change=self._on_repo_change, logger=logger, debounce_ms=200)
            self.watcher.start()

        # periodic status refresh
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(500)

        self.refresh_status()

    # ----- UI hooks -----
    @Slot()
    def on_scale_changed(self, idx: int):
        if self.viewport is None:
            return
        scale = idx + 1
        self.viewport.set_scale(scale)

    @Slot()
    def on_reload(self):
        if self.bridge is None:
            return
        try:
            self.bridge.reload()
            if self.viewport:
                self.viewport.flash_reloaded()
            self.log_line("Reloaded MenuLCD.")
        except Exception as e:
            self.log_line(f"Reload failed: {e}")

    @Slot()
    def on_snapshot(self):
        if self.bridge is None:
            return
        try:
            p = self.bridge.snapshot_png()
            self.log_line(f"Snapshot saved: {p}")
            QMessageBox.information(self, "Snapshot", f"Saved to:\n{p}")
        except Exception as e:
            self.log_line(f"Snapshot error: {e}")
            QMessageBox.critical(self, "Snapshot error", str(e))

    @Slot()
    def on_record_gif(self):
        if self.bridge is None:
            return
        try:
            p = self.bridge.record_gif(seconds=5, fps=10)
            self.log_line(f"GIF saved: {p}")
            QMessageBox.information(self, "GIF", f"Saved to:\n{p}")
        except Exception as e:
            self.log_line(f"GIF error: {e}")
            QMessageBox.critical(self, "GIF error", str(e))

    @Slot()
    def on_home(self):
        if self.bridge is None:
            return
        try:
            self.bridge.action_home()
        except Exception as e:
            self.log_line(f"Home action error: {e}")

    @Slot()
    def on_change_repo(self):
        new_path = self.bootstrap.ask_repo_path(self)
        if not new_path:
            return
        try:
            if self.watcher:
                self.watcher.stop()
                self.watcher = None
            if self.bridge is None:
                self.bridge = MenuLCDBridge(new_path, logger=logger)
                self.viewport = LCDViewport(self.bridge)
                self.setCentralWidget(self.viewport)
            try:
                self.viewport.setFocus(Qt.OtherFocusReason)
            except Exception:
                pass
                self.controller = MenuController(self.bridge, logger=logger)
                self.viewport.installEventFilter(self.controller)
            else:
                self.bridge.set_repo(new_path)
                if self.viewport:
                    self.viewport.flash_reloaded()
            watch_paths = [
                self.bridge.repo_path / "config" / "menu.xml",
                self.bridge.repo_path / "config" / "settings.xml",
                self.bridge.repo_path / "config" / "default_settings.xml",
                self.bridge.repo_path / "fonts",
                self.bridge.repo_path / "assets",
            ]
            self.watcher = RepoWatcher(watch_paths, on_change=self._on_repo_change, logger=logger, debounce_ms=200)
            self.watcher.start()
            self.refresh_status()
        except Exception as e:
            QMessageBox.critical(self, "Repo change failed", str(e))

    def _on_repo_change(self, paths):
        self.log_line(f"Detected changes: {', '.join(str(p) for p in paths)}")
        try:
            self.bridge.reload()
            self.viewport.flash_reloaded()
        except Exception as e:
            self.log_line(f"Hot-reload error: {e}")

    def log_line(self, text: str):
        # Guard: status_panel may not be created yet during early init
        if not hasattr(self, 'status_panel') or self.status_panel is None:
            print(text)
            return
        self.status_panel.append(text)

    def refresh_status(self):
        if self.bridge is None:
            text = (f"<b>Repo:</b> {getattr(self.bootstrap, 'settings', {}).get('repo_path','(none)')}<br>"
                    f"<b>Status:</b> Not initialized<br>")
            self.status_panel.setHtml(text)
            return
        size = self.bridge.native_size()
        errors = "; ".join(self.bridge.pop_errors()) or "None"
        hot = (self.watcher.is_running if self.watcher else False)
        text = (
            f"<b>Repo:</b> {self.bridge.repo_path}<br>"
            f"<b>Native size:</b> {size[0]}×{size[1]}  "
            f"<b>Scale:</b> {getattr(self.viewport,'scale',1)}x  "
            f"<b>FPS (paint):</b> {getattr(self.viewport,'fps',0):.1f}<br>"
            f"<b>Hot-reload:</b> {'ON' if hot else 'OFF'}<br>"
            f"<b>Last errors:</b> {errors}<br>"
        )
        self.status_panel.setHtml(text)

    
    def set_lcd_profile(self, profile: str):
        try:
            self.bridge.set_display_profile(profile, reload=True)
            try:
                from lcd_preview.bootstrap_repo import SETTINGS_FILE
                import json
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    s = json.load(f)
            except Exception:
                s = {}
            s['display_profile'] = profile
            from lcd_preview.bootstrap_repo import SETTINGS_FILE
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(s, f, indent=2)
            self.log_line(f"Display profile set to {profile}. Reloaded.")
        except Exception as e:
            self.log_line(f"Error setting display profile: {e}")
def closeEvent(self, ev: QCloseEvent):
        try:
            if self.watcher:
                self.watcher.stop()
        except Exception:
            pass
        super().closeEvent(ev)


def main():
    # Enable High DPI Pixmaps (we're doing integer scaling ourselves, but this avoids odd blurriness on some systems)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    parser = argparse.ArgumentParser()
    parser.add_argument('--lcd', choices=['128','240','1in44','1in3'], help='Force LCD profile (128/1in44 or 240/1in3)')
    args = parser.parse_args()

    app = QApplication(sys.argv[:1])
    win = MainWindow(lcd_override=args.lcd)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()