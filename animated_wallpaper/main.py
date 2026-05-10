"""
Animated Wallpaper — entry point.

Starts a system-tray icon that lets the user open settings and quit.
Plays the configured MP4 as the desktop wallpaper and automatically
pauses / resumes it based on GPU load.
"""
import os
import sys
import threading
from typing import Optional

# ── stdlib-only import at module level; heavy deps imported lazily ──────────

import config as cfg_mod
from gpu_monitor import GPUMonitor
from wallpaper import WallpaperEngine

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_cfg: dict = cfg_mod.load()
_engine: Optional[WallpaperEngine] = None
_monitor: Optional[GPUMonitor] = None
_paused_by_gpu = False


# ---------------------------------------------------------------------------
# GPU callbacks
# ---------------------------------------------------------------------------

def _on_high_gpu() -> None:
    global _engine, _paused_by_gpu
    if _engine and not _paused_by_gpu:
        _paused_by_gpu = True
        _engine.pause()
        print("[gpu] Load high — wallpaper paused.")


def _on_low_gpu() -> None:
    global _engine, _paused_by_gpu
    if _engine and _paused_by_gpu:
        _paused_by_gpu = False
        _engine.resume()
        print("[gpu] Load normal — wallpaper resumed.")


# ---------------------------------------------------------------------------
# Engine lifecycle
# ---------------------------------------------------------------------------

def _start_engine() -> None:
    global _engine, _monitor, _cfg, _paused_by_gpu

    video = _cfg.get("video_path", "")
    if not video or not os.path.exists(video):
        print("[main] No video configured. Open Settings to choose a file.")
        return

    _engine = WallpaperEngine(
        video,
        mute=_cfg.get("mute", True),
        loop=_cfg.get("loop", True),
    )
    try:
        _engine.start()
    except RuntimeError as exc:
        print(f"[main] ERROR: {exc}")
        _engine = None
        return

    _monitor = GPUMonitor(
        threshold=_cfg.get("gpu_threshold", 25),
        interval=_cfg.get("check_interval", 3),
        on_high=_on_high_gpu,
        on_low=_on_low_gpu,
    )
    _monitor.start()
    _paused_by_gpu = False
    print(
        f"[main] Started — GPU threshold: {_monitor.threshold}%, "
        f"interval: {_monitor.interval}s"
    )


def _stop_engine() -> None:
    global _engine, _monitor
    if _monitor:
        _monitor.stop()
        _monitor = None
    if _engine:
        _engine.stop()
        _engine = None
    print("[main] Wallpaper stopped.")


def _restart_engine() -> None:
    _stop_engine()
    _start_engine()


# ---------------------------------------------------------------------------
# Tray icon helpers
# ---------------------------------------------------------------------------

def _make_tray_image() -> "Image.Image":
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Dark circle background
    d.ellipse([2, 2, 61, 61], fill=(30, 30, 46))
    # Thin accent ring
    d.ellipse([2, 2, 61, 61], outline=(137, 180, 250), width=3)
    # Play triangle
    d.polygon([(22, 17), (22, 47), (50, 32)], fill=(137, 180, 250))
    return img


def _open_settings_async() -> None:
    import settings_gui  # noqa: PLC0415

    def _on_apply() -> None:
        global _cfg
        _cfg = cfg_mod.load()
        _restart_engine()

    threading.Thread(
        target=lambda: settings_gui.open_settings(_cfg, on_apply=_on_apply),
        daemon=True,
        name="settings-gui",
    ).start()


def _quit_app(icon: "pystray.Icon") -> None:
    _stop_engine()
    icon.stop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not _HAS_TRAY:
        print(
            "ERROR: pystray and Pillow are required.\n"
            "  pip install pystray Pillow"
        )
        sys.exit(1)

    # Start the wallpaper engine in the background immediately
    threading.Thread(target=_start_engine, daemon=True, name="engine-start").start()

    icon_img = _make_tray_image()

    menu = pystray.Menu(
        pystray.MenuItem("Animated Wallpaper", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings…",  lambda icon, item: _open_settings_async()),
        pystray.MenuItem("Restart",    lambda icon, item: threading.Thread(
            target=_restart_engine, daemon=True).start()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit",       lambda icon, item: _quit_app(icon)),
    )

    icon = pystray.Icon(
        "AnimatedWallpaper",
        icon_img,
        "Animated Wallpaper",
        menu,
    )
    icon.run()


if __name__ == "__main__":
    main()
