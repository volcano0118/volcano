"""Build ``assets/kuromi.ico`` from the character artwork.

Usage:  python -m character.icon
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw
from PyQt6.QtGui import QGuiApplication

from character.art import render

ROOT = Path(__file__).resolve().parent.parent
ICON = ROOT / "character" / "assets" / "kuromi.ico"
SOURCE = ROOT / "character" / "assets" / ".icon_source.png"

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build_icon() -> Path:
    """Render the character and wrap it in a pink rounded-square app icon."""
    _ = QGuiApplication.instance() or QGuiApplication(sys.argv)
    ICON.parent.mkdir(parents=True, exist_ok=True)

    render(0, False, None, 4.0).save(str(SOURCE))
    source = Image.open(SOURCE).convert("RGBA")
    SOURCE.unlink(missing_ok=True)

    character = source.crop((0, 0, 800, 1000))
    character = character.resize((int(800 * 850 / 1000), 850), Image.LANCZOS)

    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((20, 20, 1004, 1004), radius=210, fill=(247, 172, 204, 255))
    canvas.alpha_composite(
        character,
        ((1024 - character.width) // 2, (1024 - character.height) // 2),
    )

    canvas.resize((256, 256), Image.LANCZOS).save(ICON, sizes=SIZES)
    return ICON


if __name__ == "__main__":
    print(build_icon())
