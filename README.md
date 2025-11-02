# Piano LED Visualizer — LCD Menu Tester (English)

A small desktop preview app for the LCD menu (reusing the original `menulcd.py` renderer).
This distribution contains English-only comments/docstrings.

## Requirements
- Python 3.10–3.12 (64-bit recommended)
- Windows, macOS, or Linux
- Path to the original Piano-LED-Visualizer repository (prompted on first run)
- Paste the font folder in the PLV master folder (same folder as visualizer.py)
- Change in PLV the path in log_setup.py

## Changes to do for log_setup.py
```powershell
file_handler = RotatingFileHandler('CUSTOM PATH\Piano-LED-Visualizer-master/visualizer.log', maxBytes=500000, backupCount=10)
```

## Virtual environment
### Windows (PowerShell)
```powershell
cd "/mnt/data/plv_menulcd_tester_english"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux
```bash
cd "/mnt/data/plv_menulcd_tester_english"
python3 -m venv .venv
source ./.venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run
```bash
python app.py
# or force LCD profile (you can change it in the app anyway):
python app.py --lcd 128   # 128×128 (1.44", ST7735)
python app.py --lcd 240   # 240×240 (1.3",  ST7789)
```

## Notes
- Warnings like `rpi_ws281x` / `spidev` are expected on desktop (null driver).
- The MIDI device monitor is optional for this preview.
- Snapshots and hot-reload are available from the toolbar/shortcuts.
