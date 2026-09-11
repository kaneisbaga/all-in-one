@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Open URLs

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_urls.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Execution failed with exit code: %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)
