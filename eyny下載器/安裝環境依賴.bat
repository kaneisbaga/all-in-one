@echo off
chcp 65001 >nul
title 安裝下載器環境依賴
cd /d "%~dp0"

echo ========================================================
echo       伊莉影片下載器 - 環境依賴自動安裝程式
echo ========================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo 【錯誤】找不到 Python！請確認已安裝 Python 3.10+ 並勾選「Add Python to PATH」。
    echo.
    pause
    exit /b 1
)

echo [1/2] 正在安裝 Python 必要套件 (customtkinter, playwright)...
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo 【錯誤】Python 套件安裝失敗，請檢查網路連線後重試。
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] 正在安裝 Playwright Chromium 瀏覽器核心...
python -m playwright install chromium
if %ERRORLEVEL% neq 0 (
    echo.
    echo 【錯誤】Playwright 核心安裝失敗，請檢查網路連線後重試。
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================================
echo   恭喜！所有環境與依賴已安裝就緒！
echo   現在您可以直接雙擊「啟動下載器.bat」開啟軟體。
echo ========================================================
echo.
pause
