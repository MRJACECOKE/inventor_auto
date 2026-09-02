#!/usr/bin/env python3
"""Generate build/app.ico for the Photo-to-IPT Builder.

Blueprint-blue rounded square with a white machined plate (one rounded corner =
fillet) and a punched hole. Drawn at 4x and downsampled for clean edges; exported
as a multi-size .ico (16/24/32/48/64/128/256).

    python build/make_icon.py        # writes build/app.ico
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "app.ico")

BLUE = (31, 95, 191, 255)      # #1f5fbf  (matches docs/guide.html --accent)
DEEP = (22, 63, 125, 255)      # #163f7d
WHITE = (255, 255, 255, 255)

S = 1024                        # supersample canvas
PAD = int(S * 0.06)


def _rrect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # background tile
    _rrect(d, (PAD, PAD, S - PAD, S - PAD), radius=int(S * 0.17), fill=BLUE)
    # thin inner keyline for depth
    d.rounded_rectangle((PAD, PAD, S - PAD, S - PAD), radius=int(S * 0.17),
                        outline=DEEP, width=int(S * 0.012))

    # the "plate": white rounded-rect, one corner sharper (fillet motif)
    m = int(S * 0.24)
    plate = (m, int(m * 1.15), S - m, S - int(m * 1.15))
    d.rounded_rectangle(plate, radius=int(S * 0.10), fill=WHITE)
    # square off the top-left corner so it reads as a filleted part, not a pill
    d.rectangle((plate[0], plate[1], plate[0] + int(S * 0.14), plate[1] + int(S * 0.14)),
                fill=WHITE)

    # punched hole (background shows through)
    cx, cy = (plate[0] + plate[2]) // 2, (plate[1] + plate[3]) // 2
    r = int(S * 0.115)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=BLUE)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=DEEP, width=int(S * 0.012))

    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [render(s) for s in sizes]
    frames[-1].save(OUT, format="ICO",
                    sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])
    print(f"wrote {OUT}  ({os.path.getsize(OUT)} bytes, sizes {sizes})")


if __name__ == "__main__":
    main()
