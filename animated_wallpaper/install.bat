@echo off
setlocal
title Animated Wallpaper — Instalador

echo ============================================================
echo  Animated Wallpaper — Instalador de dependencias
echo ============================================================
echo.
echo  NO necesitas instalar VLC ni ningun programa extra.
echo  Solo necesitas Python instalado (python.org).
echo.
pause

echo.
echo [1/2] Actualizando pip...
python -m pip install --upgrade pip

echo.
echo [2/2] Instalando paquetes...
python -m pip install -r "%~dp0requirements.txt"

echo.
echo ============================================================
echo  Listo! Ejecuta run.bat para abrir el programa.
echo ============================================================
pause
