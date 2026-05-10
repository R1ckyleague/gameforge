"""Persistent configuration stored in ~\.animated_wallpaper.json"""
import json
import os

_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".animated_wallpaper.json")

DEFAULTS: dict = {
    "video_path": "",
    "gpu_threshold": 25,      # % — pause wallpaper above this
    "check_interval": 3,      # seconds between GPU polls
    "mute": True,
    "loop": True,
    "autostart": False,
}


def load() -> dict:
    cfg = DEFAULTS.copy()
    try:
        if os.path.exists(_CONFIG_FILE):
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save(cfg: dict) -> None:
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
