"""
Animated Wallpaper — interfaz gráfica principal.
Arrastra un MP4 a la ventana y listo.

Requisitos extra:  pip install customtkinter tkinterdnd2
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

import config as cfg_mod
from gpu_monitor import GPUMonitor
from wallpaper import WallpaperEngine

# ── Paleta de colores (Catppuccin Mocha) ────────────────────────────────────
ACCENT  = "#89b4fa"
BG      = "#1e1e2e"
SURFACE = "#313244"
OVERLAY = "#45475a"
FG      = "#cdd6f4"
SUBTEXT = "#6c7086"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
PEACH   = "#fab387"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Utilidad para parsear rutas del drag-and-drop ───────────────────────────

def _first_dropped_file(data: str) -> str:
    """Extrae la primera ruta de un evento DnD de tkinterdnd2."""
    try:
        # tk.splitlist() maneja el formato Tcl `{ruta con espacios}` correctamente
        import tkinter as tk  # noqa: PLC0415
        parts = tk.Tk().tk.splitlist(data)
        return parts[0] if parts else data.strip()
    except Exception:
        return data.strip().strip("{}")


# ── App principal ─────────────────────────────────────────────────────────────

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    """Ventana principal de Animated Wallpaper."""

    def __init__(self) -> None:
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self._cfg = cfg_mod.load()
        self._engine: Optional[WallpaperEngine] = None
        self._monitor: Optional[GPUMonitor] = None
        self._running = False
        self._gpu_paused = False

        self._build_ui()
        self._restore_saved_video()
        self.after(800, self._auto_start)   # arranca automáticamente si hay video guardado
        self.after(2000, self._poll_gpu)    # inicia el refresco de la barra GPU

    # ── Construcción de la UI ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.title("Animated Wallpaper")
        self.geometry("680x590")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            ico = os.path.join(os.path.dirname(__file__), "icon.ico")
            if os.path.exists(ico):
                self.iconbitmap(ico)
        except Exception:
            pass

        self._build_header()
        self._build_drop_zone()
        self._build_file_row()
        self._build_action_btn()
        ctk.CTkFrame(self, height=1, fg_color=OVERLAY).pack(fill="x", padx=24, pady=(18, 0))
        self._build_gpu_section()
        self._build_options_row()

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=26, pady=(22, 0))

        ctk.CTkLabel(
            hdr,
            text="🎬  Animated Wallpaper",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=ACCENT,
        ).pack(side="left")

        self._badge = ctk.CTkLabel(
            hdr,
            text="  ⏹ Detenido  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=OVERLAY, corner_radius=8,
            text_color=SUBTEXT,
        )
        self._badge.pack(side="right", pady=2)

    def _build_drop_zone(self) -> None:
        self._drop_frame = ctk.CTkFrame(
            self,
            fg_color=SURFACE,
            corner_radius=16,
            border_width=2,
            border_color=OVERLAY,
        )
        self._drop_frame.pack(fill="x", padx=24, pady=(18, 0))

        self._drop_icon_lbl = ctk.CTkLabel(
            self._drop_frame,
            text="📂",
            font=ctk.CTkFont(size=48),
        )
        self._drop_icon_lbl.pack(pady=(26, 6))

        self._drop_title = ctk.CTkLabel(
            self._drop_frame,
            text="Arrastra tu video aquí",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=FG,
        )
        self._drop_title.pack()

        self._drop_sub = ctk.CTkLabel(
            self._drop_frame,
            text="o haz clic para buscar   •   MP4, MKV, AVI, WEBM",
            font=ctk.CTkFont(size=11),
            text_color=SUBTEXT,
        )
        self._drop_sub.pack(pady=(4, 26))

        # Drag & drop
        self._drop_frame.drop_target_register(DND_FILES)
        self._drop_frame.dnd_bind("<<Drop>>",      self._on_drop)
        self._drop_frame.dnd_bind("<<DragEnter>>", self._on_drag_enter)
        self._drop_frame.dnd_bind("<<DragLeave>>", self._on_drag_leave)

        # Click para explorar
        for w in (self._drop_frame, self._drop_icon_lbl, self._drop_title, self._drop_sub):
            w.bind("<Button-1>", lambda e: self._browse())
            w.configure(cursor="hand2")

    def _build_file_row(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=28, pady=(10, 0))

        self._file_lbl = ctk.CTkLabel(
            row,
            text="Sin video seleccionado",
            font=ctk.CTkFont(size=12),
            text_color=SUBTEXT,
        )
        self._file_lbl.pack(side="left")

    def _build_action_btn(self) -> None:
        self._action_btn = ctk.CTkButton(
            self,
            text="▶   Iniciar wallpaper",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=50,
            corner_radius=12,
            fg_color=ACCENT,
            hover_color="#74c7ec",
            text_color="#1e1e2e",
            command=self._toggle,
        )
        self._action_btn.pack(fill="x", padx=24, pady=(14, 0))

    def _build_gpu_section(self) -> None:
        section = ctk.CTkFrame(self, fg_color="transparent")
        section.pack(fill="x", padx=24, pady=(16, 0))

        # Fila: etiqueta + barra + porcentaje + estado
        bar_row = ctk.CTkFrame(section, fg_color="transparent")
        bar_row.pack(fill="x")

        ctk.CTkLabel(
            bar_row, text="GPU",
            font=ctk.CTkFont(size=12),
            text_color=SUBTEXT, width=36,
        ).pack(side="left")

        self._gpu_bar = ctk.CTkProgressBar(
            bar_row, height=14, corner_radius=6,
            fg_color=OVERLAY, progress_color=GREEN,
        )
        self._gpu_bar.set(0)
        self._gpu_bar.pack(side="left", fill="x", expand=True, padx=(6, 8))

        self._gpu_pct = ctk.CTkLabel(
            bar_row, text=" 0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=FG, width=44,
        )
        self._gpu_pct.pack(side="left")

        self._gpu_state = ctk.CTkLabel(
            bar_row, text="",
            font=ctk.CTkFont(size=11),
            text_color=SUBTEXT,
        )
        self._gpu_state.pack(side="left", padx=(6, 0))

        # Slider de umbral
        thr_row = ctk.CTkFrame(section, fg_color="transparent")
        thr_row.pack(fill="x", pady=(12, 0))

        ctk.CTkLabel(
            thr_row, text="Pausa cuando GPU supere:",
            font=ctk.CTkFont(size=12), text_color=SUBTEXT,
        ).pack(side="left")

        self._thr_lbl = ctk.CTkLabel(
            thr_row,
            text=f"{self._cfg.get('gpu_threshold', 25)}%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT, width=42,
        )
        self._thr_lbl.pack(side="right")

        self._thr_slider = ctk.CTkSlider(
            section, from_=5, to=95, number_of_steps=90,
            command=self._on_thr_change,
        )
        self._thr_slider.set(self._cfg.get("gpu_threshold", 25))
        self._thr_slider.pack(fill="x", pady=(6, 0))

    def _build_options_row(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(18, 24))

        self._mute_var = ctk.BooleanVar(value=self._cfg.get("mute", True))
        ctk.CTkCheckBox(
            row, text="Silenciar audio",
            variable=self._mute_var,
            font=ctk.CTkFont(size=12),
            command=self._save_cfg,
        ).pack(side="left", padx=(0, 28))

        self._loop_var = ctk.BooleanVar(value=self._cfg.get("loop", True))
        ctk.CTkCheckBox(
            row, text="Repetir en bucle",
            variable=self._loop_var,
            font=ctk.CTkFont(size=12),
            command=self._save_cfg,
        ).pack(side="left")

    # ── Eventos de drag & drop ───────────────────────────────────────────────

    def _on_drag_enter(self, event) -> None:
        self._drop_frame.configure(border_color=ACCENT)
        self._drop_icon_lbl.configure(text="📥")

    def _on_drag_leave(self, event) -> None:
        if not self._cfg.get("video_path"):
            self._drop_frame.configure(border_color=OVERLAY)
            self._drop_icon_lbl.configure(text="📂")

    def _on_drop(self, event) -> None:
        path = _first_dropped_file(event.data)
        if os.path.isfile(path):
            self._set_video(path)
        self._on_drag_leave(None)

    # ── Selección de video ───────────────────────────────────────────────────

    def _browse(self) -> None:
        from tkinter import filedialog  # noqa: PLC0415
        path = filedialog.askopenfilename(
            title="Selecciona video",
            filetypes=[
                ("Video", "*.mp4 *.mkv *.webm *.avi *.mov"),
                ("Todos", "*.*"),
            ],
        )
        if path:
            self._set_video(path)

    def _set_video(self, path: str) -> None:
        self._cfg["video_path"] = path
        self._save_cfg()

        name = os.path.basename(path)
        short = name if len(name) <= 60 else name[:57] + "…"

        self._file_lbl.configure(text=f"📄  {short}", text_color=FG)
        self._drop_icon_lbl.configure(text="🎬")
        self._drop_title.configure(text=f"✓  {short}")
        self._drop_sub.configure(text="Haz clic o arrastra para cambiar el video")
        self._drop_frame.configure(border_color=ACCENT)

    def _restore_saved_video(self) -> None:
        video = self._cfg.get("video_path", "")
        if video and os.path.exists(video):
            self._set_video(video)

    # ── Control del wallpaper ────────────────────────────────────────────────

    def _auto_start(self) -> None:
        if self._cfg.get("video_path") and os.path.exists(self._cfg["video_path"]):
            self._start()

    def _toggle(self) -> None:
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        video = self._cfg.get("video_path", "")
        if not video or not os.path.exists(video):
            self._show_error("Primero selecciona un archivo de video.")
            return

        self._engine = WallpaperEngine(
            video,
            mute=self._mute_var.get(),
            loop=self._loop_var.get(),
        )
        try:
            self._engine.start()
        except RuntimeError as exc:
            self._show_error(str(exc))
            self._engine = None
            return

        self._monitor = GPUMonitor(
            threshold=int(self._thr_slider.get()),
            interval=self._cfg.get("check_interval", 3),
            on_high=self._on_high_gpu,
            on_low=self._on_low_gpu,
        )
        self._monitor.start()
        self._running = True
        self._gpu_paused = False
        self._set_running_ui()

    def _stop(self) -> None:
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        if self._engine:
            self._engine.stop()
            self._engine = None
        self._running = False
        self._gpu_paused = False
        self._set_stopped_ui()

    # ── Callbacks GPU ────────────────────────────────────────────────────────

    def _on_high_gpu(self) -> None:
        self._gpu_paused = True
        if self._engine:
            self._engine.pause()
        self.after(0, lambda: (
            self._set_badge("  ⏸ Pausado (GPU)  ", PEACH, "#1e1e2e"),
            self._gpu_state.configure(text="⏸ pausado por GPU", text_color=PEACH),
        ))

    def _on_low_gpu(self) -> None:
        self._gpu_paused = False
        if self._engine:
            self._engine.resume()
        self.after(0, lambda: (
            self._set_badge("  ▶ Activo  ", GREEN, "#1e1e2e"),
            self._gpu_state.configure(text=""),
        ))

    def _on_thr_change(self, val: float) -> None:
        v = int(val)
        self._thr_lbl.configure(text=f"{v}%")
        self._cfg["gpu_threshold"] = v
        if self._monitor:
            self._monitor.threshold = v
        self._save_cfg()

    # ── UI state ─────────────────────────────────────────────────────────────

    def _set_running_ui(self) -> None:
        self._action_btn.configure(
            text="⏹   Detener wallpaper",
            fg_color=RED, hover_color="#eba0ac",
            text_color="#1e1e2e",
        )
        self._set_badge("  ▶ Activo  ", GREEN, "#1e1e2e")
        self._gpu_state.configure(text="")

    def _set_stopped_ui(self) -> None:
        self._action_btn.configure(
            text="▶   Iniciar wallpaper",
            fg_color=ACCENT, hover_color="#74c7ec",
            text_color="#1e1e2e",
        )
        self._set_badge("  ⏹ Detenido  ", OVERLAY, SUBTEXT)
        self._gpu_state.configure(text="")
        self._gpu_bar.set(0)
        self._gpu_pct.configure(text=" 0%")
        self._gpu_bar.configure(progress_color=GREEN)

    def _set_badge(self, text: str, bg: str, fg: str) -> None:
        self._badge.configure(text=text, fg_color=bg, text_color=fg)

    def _show_error(self, msg: str) -> None:
        import tkinter.messagebox as mb  # noqa: PLC0415
        mb.showerror("Error", msg, parent=self)

    # ── Barra GPU en tiempo real ─────────────────────────────────────────────

    def _poll_gpu(self) -> None:
        if self._monitor:
            usage = self._monitor.last_usage
            self._gpu_bar.set(usage / 100)
            self._gpu_pct.configure(text=f"{int(usage):3d}%")

            thr = self._cfg.get("gpu_threshold", 25)
            if usage >= thr:
                self._gpu_bar.configure(progress_color=RED)
            elif usage >= thr * 0.7:
                self._gpu_bar.configure(progress_color=YELLOW)
            else:
                self._gpu_bar.configure(progress_color=GREEN)
        self.after(2000, self._poll_gpu)

    # ── Config ───────────────────────────────────────────────────────────────

    def _save_cfg(self) -> None:
        self._cfg["mute"] = self._mute_var.get()
        self._cfg["loop"] = self._loop_var.get()
        cfg_mod.save(self._cfg)

    def _on_close(self) -> None:
        self._stop()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
