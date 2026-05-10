"""
WallpaperEngine — plays an MP4 (or any VLC-supported format) behind the
desktop icons on Windows using the "WorkerW trick".

Technique:
  1. Send 0x052C to Progman — this makes Windows create a WorkerW window
     that sits between the desktop wallpaper and the icons.
  2. Create our own child HWND inside that WorkerW.
  3. Embed a VLC media player into that HWND.
"""
import ctypes
import ctypes.wintypes
import threading
import time
from typing import Optional

# Lazy imports so the module can be imported on non-Windows for tests.
try:
    import win32api
    import win32con
    import win32gui
    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False

try:
    import vlc as _vlc
    _HAS_VLC = True
except ImportError:
    _HAS_VLC = False


# ---------------------------------------------------------------------------
# WorkerW helpers
# ---------------------------------------------------------------------------

def _spawn_workerw() -> Optional[int]:
    """
    Ask Progman to spawn the WorkerW layer and return its HWND.
    Returns None if the window cannot be found.
    """
    progman = win32gui.FindWindow("Progman", None)
    # 0x052C — undocumented Progman message that creates the WorkerW child
    win32gui.SendMessageTimeout(
        progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000
    )

    found: list[int] = []

    def _enum_cb(hwnd: int, _: object) -> None:
        shelldll = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
        if shelldll:
            workerw = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
            if workerw:
                found.append(workerw)

    win32gui.EnumWindows(_enum_cb, 0)
    return found[0] if found else None


# ---------------------------------------------------------------------------
# WallpaperEngine
# ---------------------------------------------------------------------------

class WallpaperEngine:
    """
    Plays *video_path* as the desktop wallpaper.

    Call start() once.  Use pause() / resume() to react to GPU load.
    Call stop() for cleanup.
    """

    _CLASS_REGISTERED = False  # WNDCLASS only needs to be registered once

    def __init__(
        self,
        video_path: str,
        *,
        mute: bool = True,
        loop: bool = True,
    ) -> None:
        self.video_path = video_path
        self.mute = mute
        self.loop = loop

        self._instance: Optional[object] = None   # vlc.Instance
        self._player: Optional[object] = None     # vlc.MediaPlayer
        self._hwnd: Optional[int] = None
        self._workerw: Optional[int] = None
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        if not _HAS_WIN32:
            raise RuntimeError(
                "pywin32 is not installed. Run: pip install pywin32"
            )
        if not _HAS_VLC:
            raise RuntimeError(
                "python-vlc is not installed or VLC is missing.\n"
                "Install VLC from https://www.videolan.org/ then:\n"
                "  pip install python-vlc"
            )
        self._running = True
        self._thread = threading.Thread(
            target=self._engine_thread, daemon=True, name="wallpaper-engine"
        )
        self._thread.start()

    def pause(self) -> None:
        if self._player and not self._paused:
            self._player.set_pause(1)
            self._paused = True

    def resume(self) -> None:
        if self._player and self._paused:
            self._player.set_pause(0)
            self._paused = False

    def stop(self) -> None:
        self._running = False
        if self._player:
            self._player.stop()
            self._player.release()
            self._player = None
        if self._instance:
            self._instance.release()
            self._instance = None

    # ----------------------------------------------------------------- private

    def _engine_thread(self) -> None:
        self._workerw = _spawn_workerw()
        if not self._workerw:
            print("[wallpaper] ERROR: Could not find WorkerW. "
                  "Is Windows Explorer running?")
            return

        self._hwnd = self._create_child_window(self._workerw)
        self._start_vlc()
        self._watch_explorer()   # blocks until self._running is False

    def _create_child_window(self, parent: int) -> int:
        """Create a borderless child window inside WorkerW covering all monitors."""
        if not WallpaperEngine._CLASS_REGISTERED:
            wc = win32gui.WNDCLASS()
            wc.hInstance = win32api.GetModuleHandle(None)
            wc.lpszClassName = "AnimWallpaperChild"
            wc.lpfnWndProc = win32gui.DefWindowProc
            win32gui.RegisterClass(wc)
            WallpaperEngine._CLASS_REGISTERED = True

        # Virtual screen spans all monitors
        vx = win32api.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        vy = win32api.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        vw = win32api.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        vh = win32api.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN

        hwnd = win32gui.CreateWindowEx(
            0,
            "AnimWallpaperChild",
            "",
            win32con.WS_CHILD | win32con.WS_VISIBLE,
            vx, vy, vw, vh,
            parent, 0,
            win32api.GetModuleHandle(None),
            None,
        )
        return hwnd

    def _start_vlc(self) -> None:
        flags = [
            "--no-osd",
            "--no-video-title-show",
            "--no-snapshot-preview",
            "--quiet",
        ]
        if self.mute:
            flags.append("--no-audio")

        self._instance = _vlc.Instance(" ".join(flags))
        self._player = self._instance.media_player_new()

        media = self._instance.media_new(self.video_path)
        if self.loop:
            media.add_option("input-repeat=65535")

        self._player.set_media(media)
        self._player.set_hwnd(self._hwnd)
        self._player.play()

    def _watch_explorer(self) -> None:
        """
        Keep the message pump alive and restart the wallpaper if Explorer
        crashes and respawns (TaskbarCreated is broadcast on respawn).
        """
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

    def _on_explorer_restart(self) -> None:
        """Re-attach after Explorer restarts."""
        time.sleep(1.5)  # give Explorer time to finish rebuilding the shell
        new_workerw = _spawn_workerw()
        if new_workerw and self._player:
            self._workerw = new_workerw
            self._hwnd = self._create_child_window(new_workerw)
            self._player.set_hwnd(self._hwnd)
            if not self._paused:
                self._player.play()
