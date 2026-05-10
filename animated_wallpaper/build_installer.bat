@echo off
setlocal
title Animated Wallpaper — Construir instalador
cd /d "%~dp0"

echo ============================================================
echo  Animated Wallpaper — Constructor de instalador
echo ============================================================
echo.

:: ── Paso 1: verificar Python ──────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python desde python.org
    pause & exit /b 1
)

:: ── Paso 2: instalar dependencias de build ────────────────────────────────
echo [1/4] Instalando dependencias de Python...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet
echo       Listo.

:: ── Paso 3: generar icono ─────────────────────────────────────────────────
echo [2/4] Generando icono...
python create_icon.py
if errorlevel 1 (
    echo ERROR al generar el icono. Asegurate de tener Pillow instalado.
    pause & exit /b 1
)

:: ── Paso 4: compilar con PyInstaller ──────────────────────────────────────
echo [3/4] Compilando ejecutable (puede tardar 1-3 minutos)...
pyinstaller animated_wallpaper.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR en PyInstaller. Revisa los mensajes de arriba.
    pause & exit /b 1
)
echo       Listo. Ejecutable en dist\AnimatedWallpaper\

:: ── Paso 5: crear instalador con Inno Setup ───────────────────────────────
echo [4/4] Creando instalador .exe con Inno Setup...

set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if "%ISCC%"=="" (
    echo.
    echo  Inno Setup no encontrado.
    echo  Descargalo gratis desde: https://jrsoftware.org/isdl.php
    echo  Luego ejecuta este script de nuevo.
    echo.
    echo  El ejecutable sin instalar ya está en:
    echo    dist\AnimatedWallpaper\AnimatedWallpaper.exe
    pause & exit /b 0
)

if not exist output mkdir output
%ISCC% installer.iss
if errorlevel 1 (
    echo ERROR en Inno Setup.
    pause & exit /b 1
)

echo.
echo ============================================================
echo  LISTO! El instalador esta en:
echo    output\AnimatedWallpaper_Setup_v1.0.0.exe
echo.
echo  Ese unico archivo puedes distribuirlo. Los usuarios solo
echo  lo ejecutan y se instala como cualquier programa de Windows.
echo ============================================================
echo.
pause
