from __future__ import annotations
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QWheelEvent
from typing import Optional
import logging

class MenuController(QObject):
    """Only handles mouse wheel to simulate encoder; key handling is done by application-wide QShortcuts."""
    def __init__(self, bridge, logger: Optional[logging.Logger] = None):
        super().__init__()
        self.bridge = bridge
        self.logger = logger or logging.getLogger("MenuController")
        self.errors = []

    def eventFilter(self, obj, ev):

        """Global key/wheel handler to drive MenuLCD regardless of widget focus."""

        try:

            # Let our shortcuts win for arrows & enter/back

            if ev.type() == QEvent.ShortcutOverride:

                if hasattr(ev, "key") and ev.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,

                                                      Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape, Qt.Key_Backspace,

                                                      Qt.Key_Home):

                    print("[KEY] ShortcutOverride -> accept")

                    ev.accept()

                    return True

    

            # Key presses

            if ev.type() == QEvent.KeyPress:

                k = ev.key() if hasattr(ev, "key") else None

                if k == Qt.Key_Up:

                    print("[KEY] UP -> action_up()"); self.bridge.action_up(); return True

                if k == Qt.Key_Down:

                    print("[KEY] DOWN -> action_down()"); self.bridge.action_down(); return True

                if k == Qt.Key_Left:

                    print("[KEY] LEFT -> action_left()"); self.bridge.action_left(); return True

                if k == Qt.Key_Right:

                    print("[KEY] RIGHT -> action_right()"); self.bridge.action_right(); return True

                if k in (Qt.Key_Return, Qt.Key_Enter):

                    print("[KEY] ENTER -> action_enter()"); self.bridge.action_enter(); return True

                if k in (Qt.Key_Escape, Qt.Key_Backspace):

                    print("[KEY] BACK -> action_back()"); self.bridge.action_back(); return True

                if k == Qt.Key_Home:

                    print("[KEY] HOME -> action_home()"); self.bridge.action_home(); return True

    

            # Mouse wheel -> encoder (±1 step)

            if ev.type() == QEvent.Wheel:

                delta = 0

                try:

                    delta = ev.angleDelta().y()

                except Exception:

                    pass

                if delta != 0:

                    step = 1 if delta > 0 else -1

                    print(f"[KEY] WHEEL {{delta}} -> encoder {{step}}")

                    try:

                        self.bridge.action_encoder(step)

                    except Exception:

                        # Fallback through repeated up/down if encoder not present

                        if step > 0: self.bridge.action_down()

                        else: self.bridge.action_up()

                    return True

    

        except Exception as e:

            print(f"[KEY][ERR] eventFilter: {{e}}")

        return False

    def _on_wheel(self, ev: QWheelEvent) -> bool:
        try:
            delta = ev.angleDelta().y()
            if delta > 0:
                self.bridge.action_up()
            elif delta < 0:
                self.bridge.action_down()
            return True
        except Exception as e:
            self._push_error(f"Wheel error: {e}")
            return False

    def _push_error(self, msg: str):
        self.errors.append(str(msg))
        self.logger.error(msg)