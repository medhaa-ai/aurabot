"""Generate AuraBot app icons using Pillow.

Creates:
  frontend/icons/icon.png   — 512x512 master
  frontend/icons/icon.ico   — Windows multi-size (16,24,32,48,64,128,256)
  frontend/icons/tray.png   — 32x32 system-tray icon

Usage:
  pip install pillow
  python scripts/make_icons.py
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not installed. Run: pip install pillow")
    sys.exit(1)

ROOT     = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "frontend" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)

# Brand colours
BG_OUTER  = (15,  23,  41,  255)   # #0F1729
BG_INNER  = (26,  37,  64,  255)   # #1A2540
ACCENT    = (167, 199, 231, 255)   # #A7C7E7
ACCENT_DIM= (106, 158, 199, 180)   # #6A9EC7 semi


def _draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s    = size

    # Outer rounded-rect background (approximate with ellipse for simplicity)
    r = s // 5
    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=BG_OUTER)

    # Inner circle glow
    p = s // 8
    draw.ellipse([p, p, s - p, s - p], fill=BG_INNER)

    # Accent ring
    rw = max(1, s // 40)
    rp = s // 6
    draw.ellipse([rp, rp, s - rp, s - rp], outline=ACCENT_DIM, width=rw)

    # Letter "A" — drawn as two lines meeting at the top + crossbar
    cx, cy = s // 2, s // 2
    top_y  = cy - s // 4
    bot_y  = cy + s // 4
    lft_x  = cx - s // 6
    rgt_x  = cx + s // 6
    bar_y  = cy + s // 16
    lw     = max(2, s // 30)

    draw.line([(cx, top_y), (lft_x, bot_y)], fill=ACCENT, width=lw)   # left leg
    draw.line([(cx, top_y), (rgt_x, bot_y)], fill=ACCENT, width=lw)   # right leg
    draw.line([(lft_x + lw * 2, bar_y), (rgt_x - lw * 2, bar_y)],     # crossbar
              fill=ACCENT, width=max(1, lw - 1))

    # Small sparkle dot above the "A"
    dot_r = max(1, s // 36)
    draw.ellipse([cx - dot_r, top_y - dot_r * 3, cx + dot_r, top_y - dot_r],
                 fill=ACCENT)

    return img


def _draw_tray(size: int = 32) -> Image.Image:
    """Minimal tray icon — just the accent 'A' on a dark background."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s    = size

    draw.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 6, fill=BG_OUTER)

    cx, cy = s // 2, s // 2
    top_y  = cy - s // 4
    bot_y  = cy + s // 4
    lft_x  = cx - s // 6
    rgt_x  = cx + s // 6
    bar_y  = cy + s // 16
    lw     = max(1, s // 16)

    draw.line([(cx, top_y), (lft_x, bot_y)], fill=ACCENT, width=lw)
    draw.line([(cx, top_y), (rgt_x, bot_y)], fill=ACCENT, width=lw)
    draw.line([(lft_x + lw, bar_y), (rgt_x - lw, bar_y)], fill=ACCENT, width=max(1, lw - 1))

    return img


def main():
    print("Generating AuraBot icons...")

    # Master PNG (512)
    master = _draw_icon(512)
    master.save(ICON_DIR / "icon.png", "PNG")
    print(f"  icon.png ({ICON_DIR / 'icon.png'})")

    # Windows ICO — multiple sizes embedded
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    frames    = [_draw_icon(sz).convert("RGBA") for sz in ico_sizes]
    frames[0].save(
        ICON_DIR / "icon.ico",
        format="ICO",
        sizes=[(sz, sz) for sz in ico_sizes],
        append_images=frames[1:],
    )
    print(f"  icon.ico  ({ICON_DIR / 'icon.ico'})")

    # Tray PNG
    tray = _draw_tray(32)
    tray.save(ICON_DIR / "tray.png", "PNG")
    print(f"  tray.png  ({ICON_DIR / 'tray.png'})")

    print("\nDone! Icons saved to frontend/icons/")


if __name__ == "__main__":
    main()
