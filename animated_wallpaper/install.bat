@echo off
setlocal
title Animated Wallpaper — Installer

echo ============================================================
echo  Animated Wallpaper — dependency installer
echo ============================================================
echo.
echo  Before continuing, make sure VLC is installed:
echo    https://www.videolan.org/vlc/
echo.
pause

echo.
echo [1/2] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/2] Installing Python packages...
python -m pip install -r "%~dp0requirements.txt"

echo.
echo ============================================================
echo  Done!  Run  run.bat  to start the wallpaper.
echo ============================================================
pause
