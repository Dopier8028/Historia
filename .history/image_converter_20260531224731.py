#!/usr/bin/env python3
"""
Image to WebP Converter
Convierte imágenes a formato WebP optimizado para web
con renombrado automático img1, img2, etc.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
from pathlib import Path
from PIL import Image
import threading

# ── Intento importar tkinterdnd2 para drag & drop real ──────────────────────
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ════════════════════════════════════════════════════════
#  COLORES Y ESTILOS
# ════════════════════════════════════════════════════════
BG        = "#0f0f13"
SURFACE   = "#1a1a24"
ACCENT    = "#7c3aed"
ACCENT2   = "#a78bfa"
SUCCESS   = "#10b981"
ERROR     = "#ef4444"
TEXT      = "#e2e8f0"
TEXT_DIM  = "#64748b"
BORDER    = "#2d2d44"


class DropZone(tk.Canvas):
    """Zona visual de drop con animación de hover."""

    def __init__(self, master, on_drop_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.on_drop = on_drop_callback
        self._hover = False
        self._draw()
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _draw(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        color = ACCENT2 if self._hover else BORDER
        # Borde punteado manual
        dash = 8
        for x in range(0, w, dash * 2):
            self.create_line(x, 0, min(x + dash, w), 0, fill=color, width=2)
            self.create_line(x, h - 1, min(x + dash, w), h - 1, fill=color, width=2)
        for y in range(0, h, dash * 2):
            self.create_line(0, y, 0, min(y + dash, h), fill=color, width=2)
            self.create_line(w - 1, y, w - 1, min(y + dash, h), fill=color, width=2)
        # Icono
        icon_y = h // 2 - 30
        self.create_text(w // 2, icon_y, text="⬆", font=("Segoe UI", 36),
                         fill=ACCENT2 if self._hover else TEXT_DIM)
        self.create_text(w // 2, icon_y + 52, text="Arrastra tus imágenes aquí",
                         font=("Segoe UI", 13, "bold"), fill=TEXT if self._hover else TEXT_DIM)
        self.create_text(w // 2, icon_y + 76, text="PNG · JPG · JPEG · GIF · BMP · TIFF · WEBP",
                         font=("Segoe UI", 9), fill=TEXT_DIM)

    def _enter(self, _):
        self._hover = True
        self._draw()

    def _leave(self, _):
        self._hover = False
        self._draw()

    def highlight(self, on: bool):
        self._hover = on
        self._draw()


class FileRow(tk.Frame):
    """Fila que muestra el estado de un archivo."""

    def __init__(self, master, filename, **kwargs):
        super().__init__(master, bg=SURFACE, **kwargs)
        self.filename = filename
        self._status_var = tk.StringVar(value="⏳ Esperando…")
        self._color_var = TEXT_DIM

        name_lbl = tk.Label(self, text=filename, bg=SURFACE, fg=TEXT,
                            font=("Segoe UI", 10), anchor="w", width=38)
        name_lbl.pack(side="left", padx=(12, 4), pady=6)

        self._status_lbl = tk.Label(self, textvariable=self._status_var,
                                    bg=SURFACE, fg=TEXT_DIM,
                                    font=("Segoe UI", 10), anchor="e")
        self._status_lbl.pack(side="right", padx=12)

    def set_status(self, text: str, color: str = TEXT):
        self._status_var.set(text)
        self._status_lbl.config(fg=color)


# ════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ════════════════════════════════════════════════════════
class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("WebP Converter")
        self.geometry("600x700")
        self.minsize(520, 560)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._files: list[str] = []          # rutas completas
        self._rows:  list[FileRow] = []
        self._quality = tk.IntVar(value=82)
        self._running = False

        self._build_ui()

        if DND_AVAILABLE:
            self._setup_dnd()

    # ── UI ──────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(24, 0))

        tk.Label(hdr, text="WebP", bg=BG, fg=ACCENT2,
                 font=("Segoe UI", 28, "bold")).pack(side="left")
        tk.Label(hdr, text=" Converter", bg=BG, fg=TEXT,
                 font=("Segoe UI", 28)).pack(side="left")

        tk.Label(self, text="Convierte imágenes a WebP optimizado para web",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 10)).pack(padx=24, pady=(2, 16), anchor="w")

        # Drop zone
        dz_frame = tk.Frame(self, bg=BORDER, padx=1, pady=1)
        dz_frame.pack(fill="x", padx=24)
        self._drop_zone = DropZone(dz_frame, self._on_drop,
                                   bg=SURFACE, width=552, height=160,
                                   highlightthickness=0, cursor="hand2")
        self._drop_zone.pack()
        self._drop_zone.bind("<Button-1>", self._browse_files)

        # Botón manual (fallback o complemento)
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=24, pady=(10, 0))

        browse_btn = tk.Button(btn_frame, text="📂  Seleccionar archivos",
                               bg=SURFACE, fg=TEXT, relief="flat",
                               font=("Segoe UI", 10), padx=16, pady=8,
                               activebackground=BORDER, activeforeground=TEXT,
                               cursor="hand2", command=self._browse_files)
        browse_btn.pack(side="left")

        clear_btn = tk.Button(btn_frame, text="Limpiar lista",
                              bg=BG, fg=TEXT_DIM, relief="flat",
                              font=("Segoe UI", 10), padx=12, pady=8,
                              activebackground=SURFACE, activeforeground=TEXT,
                              cursor="hand2", command=self._clear_list)
        clear_btn.pack(side="left", padx=(8, 0))

        # Calidad
        q_frame = tk.Frame(self, bg=BG)
        q_frame.pack(fill="x", padx=24, pady=(14, 0))
        tk.Label(q_frame, text="Calidad WebP:", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10)).pack(side="left")
        self._q_lbl = tk.Label(q_frame, text="82", bg=BG, fg=ACCENT2,
                                font=("Segoe UI", 10, "bold"), width=3)
        self._q_lbl.pack(side="left", padx=(6, 4))
        slider = ttk.Scale(q_frame, from_=10, to=100, variable=self._quality,
                           orient="horizontal", length=200,
                           command=lambda v: self._q_lbl.config(text=str(int(float(v)))))
        slider.pack(side="left")
        tk.Label(q_frame, text="(10 = pequeño · 100 = sin pérdida)",
                 bg=BG, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))

        # Lista de archivos
        list_outer = tk.Frame(self, bg=BG)
        list_outer.pack(fill="both", expand=True, padx=24, pady=(16, 0))

        tk.Label(list_outer, text="ARCHIVOS", bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")

        container = tk.Frame(list_outer, bg=BORDER, padx=1, pady=1)
        container.pack(fill="both", expand=True, pady=(4, 0))

        canvas = tk.Canvas(container, bg=SURFACE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._list_frame = tk.Frame(canvas, bg=SURFACE)

        self._list_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=self._list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._empty_lbl = tk.Label(self._list_frame,
                                   text="No hay archivos aún…",
                                   bg=SURFACE, fg=TEXT_DIM,
                                   font=("Segoe UI", 10), pady=20)
        self._empty_lbl.pack()

        # Barra de progreso + botón convertir
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=24, pady=(14, 24))

        self._progress = ttk.Progressbar(bottom, mode="determinate", length=400)
        self._progress.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self._convert_btn = tk.Button(
            bottom, text="Convertir  ▶",
            bg=ACCENT, fg="white", relief="flat",
            font=("Segoe UI", 11, "bold"), padx=20, pady=10,
            activebackground=ACCENT2, activeforeground="white",
            cursor="hand2", command=self._start_conversion
        )
        self._convert_btn.pack(side="right")

        # Status bar
        self._status_var = tk.StringVar(value="Listo")
        tk.Label(self, textvariable=self._status_var, bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(pady=(0, 8))

    # ── DnD ─────────────────────────────────────────────
    def _setup_dnd(self):
        self._drop_zone.drop_target_register(DND_FILES)
        self._drop_zone.dnd_bind("<<Drop>>", self._dnd_drop)
        self._drop_zone.dnd_bind("<<DragEnter>>", lambda e: self._drop_zone.highlight(True))
        self._drop_zone.dnd_bind("<<DragLeave>>", lambda e: self._drop_zone.highlight(False))

    def _dnd_drop(self, event):
        self._drop_zone.highlight(False)
        raw = event.data
        # tkinterdnd2 envuelve rutas con espacios en {}
        paths = self.tk.splitlist(raw)
        self._add_files(list(paths))

    # ── Archivos ────────────────────────────────────────
    def _browse_files(self, _event=None):
        from tkinter import filedialog
        types = [
            ("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.tif *.webp"),
            ("Todos los archivos", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="Seleccionar imágenes", filetypes=types)
        if paths:
            self._add_files(list(paths))

    def _add_files(self, paths: list[str]):
        EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp"}
        added = 0
        for p in paths:
            p = p.strip()
            if not p:
                continue
            if Path(p).suffix.lower() not in EXTS:
                continue
            if p in self._files:
                continue
            self._files.append(p)
            row = FileRow(self._list_frame, Path(p).name)
            row.pack(fill="x", pady=1)
            self._rows.append(row)
            added += 1

        if added:
            self._empty_lbl.pack_forget()
            self._status_var.set(f"{len(self._files)} archivo(s) en lista")

    def _clear_list(self):
        if self._running:
            return
        self._files.clear()
        for r in self._rows:
            r.destroy()
        self._rows.clear()
        self._empty_lbl.pack()
        self._progress["value"] = 0
        self._status_var.set("Listo")

    # ── Conversión ──────────────────────────────────────
    def _start_conversion(self):
        if self._running:
            return
        if not self._files:
            messagebox.showwarning("Sin archivos", "Agrega imágenes primero.")
            return
        self._running = True
        self._convert_btn.config(state="disabled", text="Convirtiendo…")
        self._progress["maximum"] = len(self._files)
        self._progress["value"] = 0
        threading.Thread(target=self._convert_all, daemon=True).start()

    def _convert_all(self):
        quality = self._quality.get()
        ok = err = 0

        for i, (path, row) in enumerate(zip(self._files, self._rows), start=1):
            new_name = f"img{i}.webp"
            out_dir   = Path(path).parent
            out_path  = out_dir / new_name

            try:
                img = Image.open(path)
                # RGBA → RGB si es necesario para JPEG-style quality
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(out_path, "WEBP", quality=quality, method=6)

                size_kb = out_path.stat().st_size // 1024
                self.after(0, lambda r=row, s=f"✔ {new_name}  ({size_kb} KB)":
                           r.set_status(s, SUCCESS))
                ok += 1
            except Exception as exc:
                self.after(0, lambda r=row, s=f"✘ {exc}":
                           r.set_status(s, ERROR))
                err += 1

            self.after(0, lambda v=i: self._progress.__setitem__("value", v))

        self.after(0, self._done, ok, err)

    def _done(self, ok: int, err: int):
        self._running = False
        self._convert_btn.config(state="normal", text="Convertir  ▶")
        msg = f"✔ {ok} convertido(s)"
        if err:
            msg += f"  ✘ {err} error(s)"
        self._status_var.set(msg)
        messagebox.showinfo("Listo",
            f"Conversión completa.\n\n"
            f"✅ Éxito: {ok}\n"
            f"❌ Errores: {err}\n\n"
            f"Los archivos se guardaron junto a los originales.")


# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()

    # Aplicar tema ttk oscuro básico
    style = ttk.Style(app)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TScrollbar", background=BORDER, troughcolor=SURFACE,
                    arrowcolor=TEXT_DIM)
    style.configure("Horizontal.TScale", background=BG, troughcolor=BORDER,
                    sliderthickness=16)
    style.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE,
                    bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)

    app.mainloop()
