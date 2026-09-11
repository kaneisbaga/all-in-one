@echo off
title Smart AI Studio v4.0 - Launcher
cd /d "%~dp0"

echo ====================================================
echo   Smart AI Studio v4.0 - Starting...
echo ====================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install from https://www.python.org
    pause
    exit /b 1
)

echo [OK] Python found.

:: Auto-install Pillow if missing
python -c "import PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing Pillow...
    pip install Pillow -q
    echo [OK] Pillow installed.
) else (
    echo [OK] Pillow is ready.
)

echo.
echo [OK] Launching Smart AI Studio...
echo.

:: Launch with python (not pythonw) so errors are visible
python smart_ai_studio.py

echo.
echo [INFO] Program has exited.