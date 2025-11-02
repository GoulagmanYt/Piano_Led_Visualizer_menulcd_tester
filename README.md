# Piano LED Visualizer — LCD Menu Tester (Desktop Preview)

A lightweight desktop preview app for the **LCD menu** of Piano‑LED‑Visualizer, reusing the original `menulcd.py` renderer.  
All source comments/docstrings are in **English**.

---

## ✅ Requirements
- **Python 3.10–3.12** (64‑bit recommended)
- **Windows**, **macOS**, or **Linux**
- Access to your **Piano‑LED‑Visualizer** repository (you will select the path on first run)

> **Tip:** Make sure the **`fonts/`** folder is present in the PLV repo (same folder as `visualizer.py`).

---

## ⚙️ One‑time adjustment in PLV (logging path)
In PLV’s `log_setup.py`, adjust the rotating file handler to your local path (Windows example):
```python
file_handler = RotatingFileHandler(r'CUSTOM PATH\Piano-LED-Visualizer-master\visualizer.log', maxBytes=500_000, backupCount=10)
```
Use a raw string (`r''`) or escape backslashes on Windows.
(You will need to put back the original path if you want to test the menu in your Rpi)
---

## 🚀 Quick Start

### Windows (PowerShell)
```powershell
# 1) Create & activate venv
cd <your_extracted_folder>
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Upgrade pip & install deps
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3) Run
python app.py
# (You can choose the PLV path on first launch)
```

### macOS / Linux
```bash
# 1) Create & activate venv
cd <your_extracted_folder>
python3 -m venv .venv
source ./.venv/bin/activate

# 2) Upgrade pip & install deps
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3) Run
python app.py
# (You can choose the PLV path on first launch)
```

---

## 🖥️ Forcing the LCD profile (optional)
You can switch in‑app via the **LCD** menu, or force it from CLI:
```bash
python app.py --lcd 128   # 128×128 (1.44", ST7735)
python app.py --lcd 240   # 240×240 (1.3",  ST7789)
```

---

## 🧭 First‑run behavior
- The app asks you to **select the Piano‑LED‑Visualizer folder** (the one containing `visualizer.py`, `lib/menulcd.py`, `config/`, etc.).
- Your choice is saved in `settings.json` for next runs.

---

## 🛠️ Useful features
- **Hot reload**: Ctrl+R
- **Snapshot** (PNG): Ctrl+S
- **GIF record** (short capture): Ctrl+G
- **Scroll/Page**: Arrow keys, W/S, K/J, PageDown (PageUp not working rn)
- **Select/Back**: Enter/Space, Backspace/Esc
- **Scale**: Toolbar scale selector

---

## ❗ Notes & Troubleshooting
- Desktop warnings like `rpi_ws281x` / `spidev` are **expected** — a null driver is used.
- The **MIDI device monitor** is optional for this preview on desktop.
- If the window is blank or fonts look off, verify the **fonts path** in your PLV repo and the selected PLV folder on first run.

---

## 📂 What’s in this package?
- The desktop preview app (Qt/PySide6)
- Minimal glue to point to your existing PLV repo
