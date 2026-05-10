"""Settings window built with tkinter (no extra dependencies)."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

import config as cfg_mod

# --------------------------------------------------------------------------
# Colour palette (Catppuccin Mocha)
# --------------------------------------------------------------------------
BG     = "#1e1e2e"
SURFACE= "#313244"
FG     = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN  = "#a6e3a1"
RED    = "#f38ba8"


def _apply_theme() -> None:
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame",       background=BG)
    style.configure("TLabelframe",  background=BG, foreground=FG,
                    font=("Segoe UI", 10))
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                    font=("Segoe UI", 10, "bold"))
    style.configure("TLabel",       background=BG, foreground=FG,
                    font=("Segoe UI", 10))
    style.configure("TCheckbutton", background=BG, foreground=FG,
                    font=("Segoe UI", 10))
    style.configure("TScale",       background=BG, troughcolor=SURFACE)
    style.configure("Accent.TButton", background=ACCENT, foreground="#1e1e2e",
                    font=("Segoe UI", 10, "bold"))
    style.configure("TButton",      background=SURFACE, foreground=FG,
                    font=("Segoe UI", 10))
    style.map("TButton",
              background=[("active", ACCENT)],
              foreground=[("active", "#1e1e2e")])
    style.map("Accent.TButton",
              background=[("active", "#74c7ec")],
              foreground=[("active", "#1e1e2e")])
    style.map("TCheckbutton",
              background=[("active", BG)])


# --------------------------------------------------------------------------
# Autostart registry helper (Windows only)
# --------------------------------------------------------------------------

def _set_autostart(enabled: bool) -> None:
    try:
        import winreg  # noqa: PLC0415
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            exe = sys.executable
            script = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "main.py")
            )
            winreg.SetValueEx(
                key, "AnimatedWallpaper", 0, winreg.REG_SZ,
                f'"{exe}" "{script}"',
            )
        else:
            try:
                winreg.DeleteValue(key, "AnimatedWallpaper")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as exc:
        messagebox.showerror("Autostart error", str(exc))


# --------------------------------------------------------------------------
# Main settings window
# --------------------------------------------------------------------------

def open_settings(
    cfg: dict,
    *,
    on_apply: Optional[Callable] = None,
) -> None:
    """Open the settings window.  Blocks until closed."""
    win = tk.Tk()
    win.title("Animated Wallpaper – Settings")
    win.geometry("520x420")
    win.resizable(False, False)
    win.configure(bg=BG)
    _apply_theme()

    # Try to set a nice icon (silently ignore if file missing)
    try:
        ico = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(ico):
            win.iconbitmap(ico)
    except Exception:
        pass

    pad = {"padx": 18, "pady": 5}

    # ── Video file ────────────────────────────────────────────────────────
    lf_video = ttk.LabelFrame(win, text=" Video ")
    lf_video.pack(fill="x", padx=16, pady=(14, 4))

    path_var = tk.StringVar(value=cfg.get("video_path", ""))

    row = ttk.Frame(lf_video)
    row.pack(fill="x", padx=10, pady=8)

    entry = tk.Entry(
        row, textvariable=path_var,
        bg=SURFACE, fg=FG, insertbackground=FG,
        relief="flat", font=("Segoe UI", 10),
    )
    entry.pack(side="left", fill="x", expand=True, ipady=6)

    def browse() -> None:
        f = filedialog.askopenfilename(
            title="Select video file",
            filetypes=[
                ("Video files", "*.mp4 *.webm *.mkv *.avi *.mov"),
                ("All files",   "*.*"),
            ],
        )
        if f:
            path_var.set(f)

    ttk.Button(row, text="Browse…", command=browse).pack(
        side="left", padx=(8, 0)
    )

    # ── GPU ──────────────────────────────────────────────────────────────
    lf_gpu = ttk.LabelFrame(win, text=" GPU detection ")
    lf_gpu.pack(fill="x", padx=16, pady=4)

    # threshold
    thr_row = ttk.Frame(lf_gpu)
    thr_row.pack(fill="x", padx=10, pady=(8, 2))
    ttk.Label(thr_row, text="Pause when GPU load exceeds").pack(side="left")
    thr_var = tk.IntVar(value=cfg.get("gpu_threshold", 25))
    thr_lbl = ttk.Label(thr_row, text=f"{thr_var.get():3d}%",
                         foreground=ACCENT, width=5)
    thr_lbl.pack(side="right")

    def _on_thr(v: str) -> None:
        thr_lbl.config(text=f"{int(float(v)):3d}%")

    ttk.Scale(lf_gpu, from_=5, to=95, variable=thr_var,
              orient="horizontal", command=_on_thr).pack(
        fill="x", padx=10, pady=(0, 6)
    )

    # interval
    int_row = ttk.Frame(lf_gpu)
    int_row.pack(fill="x", padx=10, pady=(4, 2))
    ttk.Label(int_row, text="GPU check interval").pack(side="left")
    int_var = tk.IntVar(value=cfg.get("check_interval", 3))
    int_lbl = ttk.Label(int_row, text=f"{int_var.get()}s",
                         foreground=ACCENT, width=5)
    int_lbl.pack(side="right")

    def _on_int(v: str) -> None:
        int_lbl.config(text=f"{int(float(v))}s")

    ttk.Scale(lf_gpu, from_=1, to=15, variable=int_var,
              orient="horizontal", command=_on_int).pack(
        fill="x", padx=10, pady=(0, 8)
    )

    # ── Playback options ─────────────────────────────────────────────────
    lf_play = ttk.LabelFrame(win, text=" Playback ")
    lf_play.pack(fill="x", padx=16, pady=4)

    mute_var = tk.BooleanVar(value=cfg.get("mute", True))
    loop_var = tk.BooleanVar(value=cfg.get("loop", True))
    auto_var = tk.BooleanVar(value=cfg.get("autostart", False))

    ttk.Checkbutton(lf_play, text="Mute wallpaper audio",
                    variable=mute_var).pack(anchor="w", padx=10, pady=3)
    ttk.Checkbutton(lf_play, text="Loop video",
                    variable=loop_var).pack(anchor="w", padx=10, pady=3)
    ttk.Checkbutton(lf_play, text="Start with Windows",
                    variable=auto_var).pack(anchor="w", padx=10, pady=(3, 8))

    # ── Status bar ───────────────────────────────────────────────────────
    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(win, textvariable=status_var, bg=BG, fg=GREEN,
                           font=("Segoe UI", 9), anchor="w")
    status_lbl.pack(fill="x", padx=18)

    # ── Buttons ──────────────────────────────────────────────────────────
    btn_row = ttk.Frame(win)
    btn_row.pack(fill="x", padx=16, pady=12)

    def apply() -> None:
        video = path_var.get().strip()
        if not video or not os.path.exists(video):
            messagebox.showerror("Invalid file",
                                 "Please select a valid video file.")
            return

        cfg["video_path"]    = video
        cfg["gpu_threshold"] = thr_var.get()
        cfg["check_interval"]= int_var.get()
        cfg["mute"]          = mute_var.get()
        cfg["loop"]          = loop_var.get()
        cfg["autostart"]     = auto_var.get()

        cfg_mod.save(cfg)
        _set_autostart(auto_var.get())

        status_var.set("✓ Settings saved.")
        if on_apply:
            threading.Thread(target=on_apply, daemon=True).start()

        win.after(1500, win.destroy)

    ttk.Button(btn_row, text="Cancel",
               command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(btn_row, text="Save & Apply", style="Accent.TButton",
               command=apply).pack(side="right")

    win.mainloop()
