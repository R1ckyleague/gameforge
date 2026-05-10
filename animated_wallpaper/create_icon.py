"""Genera icon.ico con múltiples resoluciones para el instalador y la app."""
from PIL import Image, ImageDraw
import os

def make_icon() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames: list[Image.Image] = []

    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        m = max(1, s // 8)
        # Círculo de fondo oscuro
        d.ellipse([m, m, s - m, s - m], fill=(30, 30, 46))
        # Aro de acento azul
        w = max(1, s // 18)
        d.ellipse([m, m, s - m, s - m], outline=(137, 180, 250), width=w)
        # Triángulo de play
        cx, cy, r = s // 2, s // 2, s // 3
        tri = [(cx - r // 2, cy - r), (cx - r // 2, cy + r), (cx + r, cy)]
        d.polygon(tri, fill=(137, 180, 250))

        frames.append(img)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    frames[0].save(
        out, format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"Icono generado: {out}")

if __name__ == "__main__":
    make_icon()
