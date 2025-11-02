from __future__ import annotations
import time
from threading import Event, Thread
from pathlib import Path
from typing import Callable, Iterable, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import logging


class _Handler(FileSystemEventHandler):
    def __init__(self, on_event: Callable[[Path], None], logger: logging.Logger):
        self.on_event = on_event
        self.logger = logger

    def on_any_event(self, event: FileSystemEvent):
        try:
            p = Path(event.src_path)
            self.on_event(p)
        except Exception as e:
            self.logger.error("Watcher event error: %s", e)


class RepoWatcher:
    def __init__(self, paths: Iterable[Path], on_change: Callable[[List[Path]], None], logger: Optional[logging.Logger] = None, debounce_ms=200):
        self.paths = list(paths)
        self.on_change = on_change
        self.logger = logger or logging.getLogger("RepoWatcher")
        self.debounce = debounce_ms / 1000.0
        self._obs: Optional[Observer] = None
        self._changed: List[Path] = []
        self._stop = Event()
        self._thr: Optional[Thread] = None
        self.is_running = False

    def start(self):
        if self.is_running:
            return
        self._stop.clear()
        self._changed.clear()
        obs = Observer()
        handler = _Handler(self._on_event, self.logger)
        for p in self.paths:
            p = Path(p)
            if p.exists():
                if p.is_dir():
                    obs.schedule(handler, str(p), recursive=True)
                else:
                    obs.schedule(handler, str(p.parent), recursive=False)
        obs.start()
        self._obs = obs
        self._thr = Thread(target=self._debounce_loop, daemon=True)
        self._thr.start()
        self.is_running = True

    def stop(self):
        if not self.is_running:
            return
        self._stop.set()
        if self._obs:
            self._obs.stop()
            self._obs.join(timeout=2.0)
            self._obs = None
        if self._thr:
            self._thr.join(timeout=2.0)
            self._thr = None
        self.is_running = False

    def _on_event(self, p: Path):
        self._changed.append(p)

    def _debounce_loop(self):
        last_flush = time.time()
        while not self._stop.is_set():
            time.sleep(0.05)
            now = time.time()
            if self._changed and (now - last_flush) >= self.debounce:
                changed = list({c for c in self._changed})
                self._changed.clear()
                last_flush = now
                try:
                    self.on_change(changed)
                except Exception as e:
                    self.logger.error("Watcher callback error: %s", e)
