"""Genera los íconos PNG de la PWA (192 y 512 px) con el mismo dibujo que ``public/icon.svg``.

Chrome exige íconos PNG de 192 y 512 px para que la app sea instalable. Uso:
    uv run --with pillow python scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parents[1] / "frontend" / "public"


def draw(size: int) -> Image.Image:
    k = size / 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=96 * k, fill="#0b5cad")
    d.rounded_rectangle([112 * k, 120 * k, 400 * k, 160 * k], radius=12 * k, fill="#ffffff")
    d.rounded_rectangle([112 * k, 200 * k, 400 * k, 228 * k], radius=10 * k, fill="#d9e6f3")
    d.rounded_rectangle([112 * k, 252 * k, 400 * k, 280 * k], radius=10 * k, fill="#ffe27a")
    d.rounded_rectangle([112 * k, 304 * k, 312 * k, 332 * k], radius=10 * k, fill="#d9e6f3")
    d.polygon([(352 * k, 352 * k), (408 * k, 388 * k), (352 * k, 424 * k)], fill="#ffffff")
    return img


if __name__ == "__main__":
    for s in (192, 512):
        draw(s).save(PUBLIC / f"icon-{s}.png", optimize=True)
        print(f"icon-{s}.png")
