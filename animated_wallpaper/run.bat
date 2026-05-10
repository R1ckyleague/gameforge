@echo off
cd /d "%~dp0"
rem Abre la interfaz grafica sin ventana de consola
pythonw app.py 2>nul
if errorlevel 1 (
    echo Algo fallo. Abriendo en modo debug...
    call debug.bat
)
