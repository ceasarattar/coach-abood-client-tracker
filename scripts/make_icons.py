"""
Generate the PWA app icons (static/icons/*.png) — a branded "CA" mark on a
blue gradient, matching the sidebar brand badge. Re-run any time to refresh.

    python scripts/make_icons.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
OUT_DIR = os.path.join(_ROOT, "static", "icons")

# Brand colours (approx of the app's --accent gradient on a dark surface).
TOP = (92, 176, 237)      # accent-bright
BOTTOM = (53, 122, 196)   # accent
INK = (255, 255, 255)


def _font(size: int):
    for path in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BOTTOM)
    px = img.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(TOP[0] + (BOTTOM[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOTTOM[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOTTOM[2] - TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def _draw_text(img: Image.Image, text: str, scale: float) -> None:
    size = img.size[0]
    draw = ImageDraw.Draw(img)
    font = _font(int(size * scale))
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
              text, font=font, fill=INK)


def rounded(size: int, radius_frac: float, text_scale: float) -> Image.Image:
    """Gradient rounded-square icon (transparent corners) with centred 'CA'."""
    base = _gradient(size).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * radius_frac), fill=255)
    base.putalpha(mask)
    _draw_text(base, "CA", text_scale)
    return base


def maskable(size: int) -> Image.Image:
    """Full-bleed gradient (no transparent corners) so OS masks crop safely."""
    img = _gradient(size).convert("RGBA")
    _draw_text(img, "CA", 0.42)   # smaller text -> inside the safe zone
    return img


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rounded(192, 0.22, 0.5).save(os.path.join(OUT_DIR, "icon-192.png"))
    rounded(512, 0.22, 0.5).save(os.path.join(OUT_DIR, "icon-512.png"))
    maskable(512).save(os.path.join(OUT_DIR, "icon-maskable-512.png"))
    print(f"Wrote icons to {os.path.relpath(OUT_DIR, _ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
