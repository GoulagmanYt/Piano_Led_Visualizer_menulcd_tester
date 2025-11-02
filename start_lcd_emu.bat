@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else (
  echo Virtual environment not found: .venv\Scripts\activate.bat
  exit /b 1
)
python.exe app.py
endlocal
