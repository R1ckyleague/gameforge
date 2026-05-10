# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — empaqueta Animated Wallpaper en un ejecutable.
Ejecutar desde la carpeta animated_wallpaper/:
    pyinstaller animated_wallpaper.spec --clean
"""
import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# ── Datos de paquetes que necesitan archivos externos ────────────────────────
datas = []
datas += collect_data_files("customtkinter")   # temas, fuentes, imágenes
datas += collect_data_files("tkinterdnd2")     # binarios Tcl/Tk de DnD
datas += collect_data_files("cv2")             # (por si OpenCV tiene extras)

# ── Imports ocultos que PyInstaller no detecta automáticamente ───────────────
hidden = [
    # pywin32
    "win32api", "win32con", "win32gui", "win32pdh",
    "pywintypes", "pythoncom",
    # tkinter (suele estar oculto)
    "tkinter", "tkinter.filedialog", "tkinter.messagebox", "tkinter.ttk",
    # numpy (usado por OpenCV)
    "numpy", "numpy.core", "numpy.core._multiarray_umath",
    # nuestros módulos
    "config", "gpu_monitor", "wallpaper", "settings_gui",
]

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=collect_dynamic_libs("win32"),   # DLLs de pywin32
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "pandas"],   # excluir lo innecesario
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnimatedWallpaper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,        # sin ventana de consola negra
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AnimatedWallpaper",
)
