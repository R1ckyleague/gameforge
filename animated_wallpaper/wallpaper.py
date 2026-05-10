"""
WallpaperEngine — reproduce un MP4 detrás de los iconos del escritorio.

Backends (en orden de preferencia):
  1. VLC  — si está instalado, usa aceleración por hardware.
  2. OpenCV + GDI — sin dependencias externas, solo pip.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import threading
import time
from typing import Optional

try:
    import win32api
    import win32con
    import win32gui
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

# ── Intento cargar VLC (opcional) ────────────────────────────────────────────

def _find_vlc_dir() -> Optional[str]:
    candidates = [
        r"C:\Program Files\VideoLAN\VLC",
        r"C:\Program Files (x86)\VideoLAN\VLC",
    ]
    try:
        import winreg  # noqa: PLC0415
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (
                r"SOFTWARE\VideoLAN\VLC",
                r"SOFTWARE\WOW6432Node\VideoLAN\VLC",
            ):
                try:
                    key = winreg.OpenKey(hive, sub)
                    path, _ = winreg.QueryValueEx(key, "InstallDir")
                    winreg.CloseKey(key)
                    if path:
                        candidates.insert(0, path)
                except FileNotFoundError:
                    pass
    except Exception:
        pass
    for path in candidates:
        if os.path.isfile(os.path.join(path, "libvlc.dll")):
            return path
    return None


def _try_load_vlc():
    try:
        import vlc  # noqa: PLC0415
        return vlc
    except Exception:
        pass
    vlc_dir = _find_vlc_dir()
    if vlc_dir:
        os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(vlc_dir)
        except Exception:
            pass
        try:
            import vlc  # noqa: PLC0415
            return vlc
        except Exception:
            pass
    return None


_vlc = _try_load_vlc()

# ── Intento cargar OpenCV ────────────────────────────────────────────────────

try:
    import cv2 as _cv2
    import numpy as _np
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

# ── Estructuras GDI para el backend OpenCV ──────────────────────────────────

class _BMIH(ctypes.Structure):
    _fields_ = [
        ("biSize",          ctypes.c_uint32),
        ("biWidth",         ctypes.c_int32),
        ("biHeight",        ctypes.c_int32),
        ("biPlanes",        ctypes.c_uint16),
        ("biBitCount",      ctypes.c_uint16),
        ("biCompression",   ctypes.c_uint32),
        ("biSizeImage",     ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed",       ctypes.c_uint32),
        ("biClrImportant",  ctypes.c_uint32),
    ]

class _BMI(ctypes.Structure):
    _fields_ = [("bmiHeader", _BMIH), ("bmiColors", ctypes.c_uint32 * 3)]


# ── WorkerW helpers ──────────────────────────────────────────────────────────

_CLASS_REGISTERED = False

def _get_workerw() -> Optional[int]:
    progman = win32gui.FindWindow("Progman", None)
    win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
    found: list[int] = []

    def _cb(hwnd: int, _: object) -> None:
        s = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
        if s:
            w = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
            if w:
                found.append(w)

    win32gui.EnumWindows(_cb, 0)
    return found[0] if found else None


def _create_child(parent: int, class_name: str) -> int:
    global _CLASS_REGISTERED
    if not _CLASS_REGISTERED:
        wc = win32gui.WNDCLASS()
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.lpszClassName = class_name
        wc.lpfnWndProc = win32gui.DefWindowProc
        win32gui.RegisterClass(wc)
        _CLASS_REGISTERED = True

    vx = win32api.GetSystemMetrics(76)
    vy = win32api.GetSystemMetrics(77)
    vw = win32api.GetSystemMetrics(78)
    vh = win32api.GetSystemMetrics(79)

    return win32gui.CreateWindowEx(
        0, class_name, "",
        win32con.WS_CHILD | win32con.WS_VISIBLE,
        vx, vy, vw, vh, parent, 0,
        win32api.GetModuleHandle(None), None,
    )


# ── Backend VLC ──────────────────────────────────────────────────────────────

class _VLCBackend:
    def __init__(self, video_path: str, hwnd: int, *, mute: bool, loop: bool) -> None:
        flags = ["--no-osd", "--no-video-title-show", "--no-snapshot-preview", "--quiet"]
        if mute:
            flags.append("--no-audio")
        self._inst = _vlc.Instance(" ".join(flags))
        self._player = self._inst.media_player_new()
        media = self._inst.media_new(video_path)
        if loop:
            media.add_option("input-repeat=65535")
        self._player.set_media(media)
        self._player.set_hwnd(hwnd)
        self._player.play()

    def pause(self) -> None:
        self._player.set_pause(1)

    def resume(self) -> None:
        self._player.set_pause(0)

    def stop(self) -> None:
        self._player.stop()
        self._player.release()
        self._inst.release()


# ── Backend OpenCV + GDI ─────────────────────────────────────────────────────

class _CVBackend:
    def __init__(self, video_path: str, hwnd: int, *, loop: bool) -> None:
        self._hwnd = hwnd
        self._video_path = video_path
        self._loop = loop
        self._paused = False
        self._running = True
        self._thread = threading.Thread(target=self._loop_fn, daemon=True, name="cv-render")
        self._thread.start()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._running = False

    def _loop_fn(self) -> None:
        user32 = ctypes.windll.user32
        gdi32  = ctypes.windll.gdi32

        sw = win32api.GetSystemMetrics(78)
        sh = win32api.GetSystemMetrics(79)

        cap = _cv2.VideoCapture(self._video_path)
        if not cap.isOpened():
            print(f"[wallpaper] No se puede abrir: {self._video_path}")
            return

        fps = cap.get(_cv2.CAP_PROP_FPS) or 30.0
        frame_time = 1.0 / fps

        bmi = _BMI()
        bmi.bmiHeader.biSize        = ctypes.sizeof(_BMIH)
        bmi.bmiHeader.biWidth       = sw
        bmi.bmiHeader.biHeight      = -sh   # top-down
        bmi.bmiHeader.biPlanes      = 1
        bmi.bmiHeader.biBitCount    = 32
        bmi.bmiHeader.biCompression = 0

        while self._running:
            t0 = time.perf_counter()

            if self._paused:
                time.sleep(0.05)
                continue

            ret, frame = cap.read()
            if not ret:
                if self._loop:
                    cap.set(_cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break

            if frame.shape[1] != sw or frame.shape[0] != sh:
                frame = _cv2.resize(frame, (sw, sh), interpolation=_cv2.INTER_LINEAR)

            bgra = _np.ascontiguousarray(_cv2.cvtColor(frame, _cv2.COLOR_BGR2BGRA))

            dc = user32.GetDC(self._hwnd)
            gdi32.SetDIBitsToDevice(
                dc, 0, 0, sw, sh, 0, 0, 0, sh,
                ctypes.c_void_p(bgra.ctypes.data),
                ctypes.byref(bmi),
                0,
            )
            user32.ReleaseDC(self._hwnd, dc)

            wait = frame_time - (time.perf_counter() - t0)
            if wait > 0:
                time.sleep(wait)

        cap.release()


# ── WallpaperEngine pública ───────────────────────────────────────────────────

class WallpaperEngine:
    """
    Reproduce *video_path* como fondo de escritorio.

    Usa VLC si está disponible (hardware), si no usa OpenCV + GDI (solo pip).
    """

    def __init__(self, video_path: str, *, mute: bool = True, loop: bool = True) -> None:
        self.video_path = video_path
        self.mute = mute
        self.loop = loop
        self._backend: Optional[object] = None
        self._hwnd: Optional[int] = None
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None

    @property
    def using_vlc(self) -> bool:
        return _vlc is not None

    def start(self) -> None:
        if not _HAS_WIN32:
            raise RuntimeError(
                "pywin32 no está instalado.\n  pip install pywin32"
            )
        if not self.using_vlc and not _HAS_CV2:
            raise RuntimeError(
                "No se encontró ningún motor de video.\n"
                "Instala OpenCV:  pip install opencv-python\n"
                "O instala VLC (64-bit) desde https://www.videolan.org/"
            )
        self._running = True
        self._thread = threading.Thread(
            target=self._engine_thread, daemon=True, name="wallpaper-engine"
        )
        self._thread.start()

    def pause(self) -> None:
        self._paused = True
        if self._backend:
            self._backend.pause()

    def resume(self) -> None:
        self._paused = False
        if self._backend:
            self._backend.resume()

    def stop(self) -> None:
        self._running = False
        if self._backend:
            self._backend.stop()
            self._backend = None

    def _engine_thread(self) -> None:
        workerw = _get_workerw()
        if not workerw:
            print("[wallpaper] ERROR: No se encontró la ventana WorkerW. "
                  "¿Está corriendo el Explorador de Windows?")
            return

        class_name = "AnimWallpaperVLC" if self.using_vlc else "AnimWallpaperCV"
        self._hwnd = _create_child(workerw, class_name)

        if self.using_vlc:
            print("[wallpaper] Motor: VLC (aceleración por hardware)")
            self._backend = _VLCBackend(
                self.video_path, self._hwnd,
                mute=self.mute, loop=self.loop,
            )
            self._vlc_message_loop()
        else:
            print("[wallpaper] Motor: OpenCV + GDI (sin VLC)")
            self._backend = _CVBackend(
                self.video_path, self._hwnd, loop=self.loop,
            )
            self._cv_wait_loop()

    def _vlc_message_loop(self) -> None:
        user32 = ctypes.windll.user32
        TASKBAR_CREATED = user32.RegisterWindowMessageW("TaskbarCreated")
        msg = ctypes.wintypes.MSG()
        lpmsg = ctypes.byref(msg)
        while self._running:
            if user32.PeekMessageW(lpmsg, 0, 0, 0, 1):
                if msg.message == TASKBAR_CREATED:
                    self._on_explorer_restart()
                user32.TranslateMessage(lpmsg)
                user32.DispatchMessageW(lpmsg)
            else:
                time.sleep(0.02)

    def _cv_wait_loop(self) -> None:
        while self._running:
            time.sleep(0.5)

    def _on_explorer_restart(self) -> None:
        time.sleep(1.5)
        workerw = _get_workerw()
        if workerw and self._backend and self.using_vlc:
            self._hwnd = _create_child(workerw, "AnimWallpaperVLC")
            self._backend._player.set_hwnd(self._hwnd)
            if not self._paused:
                self._backend._player.play()
