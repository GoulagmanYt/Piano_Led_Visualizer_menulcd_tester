from __future__ import annotations
import json
import sys
import os
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QFileDialog, QMessageBox

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "settings.json"


class Bootstrap:
    def __init__(self, app_name: str):
        self.app_name = app_name
        self.settings = {}
        if SETTINGS_FILE.exists():
            try:
                self.settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.settings = {}

    def ensure_repo_path(self, parent) -> Path:
        p = self.settings.get("repo_path")
        if p and Path(p).exists():
            return Path(p)
        return self.ask_repo_path(parent)

    def ask_repo_path(self, parent) -> Optional[Path]:
        dlg = QFileDialog(parent, "Select the local clone of onlaj/Piano-LED-Visualizer")
        dlg.setFileMode(QFileDialog.Directory)
        if dlg.exec():
            sel = dlg.selectedFiles()[0]
            repo_path = Path(sel)
            self._validate_repo(repo_path, parent)
            self.settings["repo_path"] = str(repo_path)
            SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
            return repo_path
        return None

    def _validate_repo(self, repo_path: Path, parent):
        required = [
            repo_path / "visualizer.py",
            repo_path / "lib" / "menulcd.py",
            repo_path / "config",
        ]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            QMessageBox.critical(parent, "Invalid repository",
                                 "These required paths are missing:\n\n" + "\n".join(missing))
            raise RuntimeError("Missing required repo files")
        # Add repo to sys.path for imports
        if str(repo_path) not in sys.path:
            sys.path.insert(0, str(repo_path))
