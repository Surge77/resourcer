"""Generate the resourcer app icon: icon.png (256) and a multi-size icon.ico.

Drawn directly with Pillow (no Qt / no SVG rasterizer) so it runs reliably
headless on Windows. Design: dark rounded tile, rising resource bars, and a
neon cyan->teal->green live pulse with a leading node.

Run:  python tools/gen_icon.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PNG_PATH = ASSETS / "icon.png"
ICO_PATH = ASSETS / "icon.ico"

OUT_SIZE = 256
SS = 4  # supersample factor for smooth antialiased edges
N = OUT_SIZE * SS

ICO_SIZES = (256, 128, 64, 48, 32, 16)

TILE_TOP = (27, 39, 53)       # #1b2735
TILE_BOTTOM = (12, 18, 26)    # #0c121a
BORDER = (58, 74, 94)         # #3a4a5e
ACCENT_STOPS = ((34, 211, 238), (45, 212, 191), (52, 211, 153))  # cyan, teal, green
NODE = (52, 211, 153)

# Pulse polyline in 256-space (matches the SVG path), scaled up by SS.
PULSE = [(44, 150), (82, 150), (100, 150), (116, 110),
         (134, 178), (152, 96), (168, 150), (212, 150)]
# Rising bars: (x, y, w, h) in 256-space.
BARS = [(56, 150, 22, 54), (94, 126, 22, 78), (132, 98, 22, 106), (170, 70, 22, 134)]


def _vertical_gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    ramp = np.linspace(0.0, 1.0, N)[:, None]
    rows = (np.array(top) * (1 - ramp) + np.array(bottom) * ramp).astype(np.uint8)
    return Image.fromarray(np.repeat(rows[:, None, :], N, axis=1), "RGB")


def _diagonal_accent() -> Image.Image:
    """Cyan->teal->green gradient along the pulse's lower-left -> upper-right axis."""
    ys, xs = np.mgrid[0:N, 0:N]
    dx, dy = (216 - 40), (56 - 200)
    t = ((xs - 40 * SS) * dx + (ys - 200 * SS) * dy) / float(dx * dx + dy * dy)
    t = np.clip(t, 0.0, 1.0)
    c0, c1, c2 = (np.array(c, float) for c in ACCENT_STOPS)
    lo = c0 + (c1 - c0) * (t / 0.55)[..., None]
    hi = c1 + (c2 - c1) * ((t - 0.55) / 0.45)[..., None]
    rgb = np.where((t < 0.55)[..., None], lo, hi).astype(np.uint8)
    return Image.fromarray(rgb, "RGB")


def _scaled(seq):
    return [(x * SS, y * SS) for x, y in seq]


def _draw_pulse(mask: ImageDraw.ImageDraw, width: int) -> None:
    pts = _scaled(PULSE)
    mask.line(pts, fill=255, width=width, joint="curve")
    r = width // 2
    for x, y in pts:  # round caps / joins
        mask.ellipse((x - r, y - r, x + r, y + r), fill=255)


def render() -> Image.Image:
    img = _vertical_gradient(TILE_TOP, TILE_BOTTOM).convert("RGBA")

    # Rounded-tile mask, inset to leave a transparent margin like an app tile.
    tile = Image.new("L", (N, N), 0)
    ImageDraw.Draw(tile).rounded_rectangle(
        (8 * SS, 8 * SS, 248 * SS, 248 * SS), radius=56 * SS, fill=255)
    img.putalpha(tile)

    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (8 * SS, 8 * SS, 248 * SS, 248 * SS), radius=56 * SS,
        outline=BORDER + (130,), width=max(1, SS))

    accent = _diagonal_accent()

    # Faint rising bars.
    bars_mask = Image.new("L", (N, N), 0)
    bdraw = ImageDraw.Draw(bars_mask)
    for x, y, w, h in BARS:
        bdraw.rounded_rectangle(
            (x * SS, y * SS, (x + w) * SS, (y + h) * SS), radius=7 * SS, fill=77)  # ~0.30
    img.paste(accent, (0, 0), bars_mask)

    # Pulse halo (wide, faint) then the bright stroke on top.
    halo = Image.new("L", (N, N), 0)
    _draw_pulse(ImageDraw.Draw(halo), width=26 * SS)
    img.paste(accent, (0, 0), halo.point(lambda v: v * 46 // 255))  # ~0.18

    line = Image.new("L", (N, N), 0)
    _draw_pulse(ImageDraw.Draw(line), width=13 * SS)
    img.paste(accent, (0, 0), line)

    # Leading node with a soft ring.
    nx, ny = 212 * SS, 150 * SS
    draw.ellipse((nx - 15 * SS, ny - 15 * SS, nx + 15 * SS, ny + 15 * SS), fill=NODE + (51,))
    draw.ellipse((nx - 11 * SS, ny - 11 * SS, nx + 11 * SS, ny + 11 * SS), fill=NODE + (255,))

    return img.resize((OUT_SIZE, OUT_SIZE), Image.LANCZOS)


def main() -> None:
    icon = render()
    icon.save(PNG_PATH)
    icon.save(ICO_PATH, sizes=[(s, s) for s in ICO_SIZES])
    print(f"wrote {PNG_PATH.name} and {ICO_PATH.name} ({', '.join(map(str, ICO_SIZES))})")


if __name__ == "__main__":
    main()
