@echo off
REM One-click launcher - Windows (double-click)
cd /d "%~dp0"

set "PY="
for %%C in (py python python3) do (
  if not defined PY (
    %%C -c "import sys;raise SystemExit(0 if sys.version_info>=(3,8) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=%%C"
  )
)
if not defined PY (
  echo Python 3.8+ was not found.
  echo Install it from python.org - tick "Add Python to PATH" - then double-click this again.
  pause
  exit /b 1
)

%PY% -c "import PIL" >nul 2>&1
if errorlevel 1 (
  echo First run: installing Pillow ^(image library^)...
  %PY% -m pip install --quiet Pillow
  if errorlevel 1 (
    echo Could not install Pillow. Try:  %PY% -m pip install Pillow
    pause
    exit /b 1
  )
)

echo Starting CardForge Studio at http://127.0.0.1:8570
start "" http://127.0.0.1:8570
%PY% cardforge\studio.py
echo.
echo CardForge stopped.
pause
