@echo off
cd /d "%~dp0"
rem Intenta con pythonw (sin consola); si falla, abre debug.bat
pythonw main.py 2>nul
if errorlevel 1 (
    echo pythonw fallo. Abriendo modo debug...
    call debug.bat
)
