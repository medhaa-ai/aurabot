"""Generate AuraBot app icons using Pillow.

Creates:
  frontend/icons/icon.png   — 512x512 master (also used as macOS source)
  frontend/icons/icon.ico   — Windows multi-size (16,24,32,48,64,128,256)
  frontend/icons/icon.icns  — macOS (generated only on macOS via iconutil)
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


def _make_icns(master_png: Path, out: Path) -> None:
    """Generate icon.icns on macOS using iconutil (requires macOS)."""
    import subprocess, tempfile, shutil
    iconset = Path(tempfile.mkdtemp()) / "icon.iconset"
    iconset.mkdir()
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        img = Image.open(master_png).resize((s, s), Image.LANCZOS)
        img.save(iconset / f"icon_{s}x{s}.png")
        if s <= 512:
            img2x = Image.open(master_png).resize((s * 2, s * 2), Image.LANCZOS)
            img2x.save(iconset / f"icon_{s}x{s}@2x.png")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)], check=True)
    shutil.rmtree(iconset.parent)


def main():
    print("Generating AuraBot icons...")

    # Master PNG (512)
    master = _draw_icon(512)
    master_path = ICON_DIR / "icon.png"
    master.save(master_path, "PNG")
    print(f"  icon.png ({master_path})")

    # Windows ICO — draw at 256 then let Pillow downsample to each required size
    ico_base  = _draw_icon(256).convert("RGBA")
    ico_sizes = [(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)]
    ico_base.save(
        ICON_DIR / "icon.ico",
        format="ICO",
        sizes=ico_sizes,
    )
    print(f"  icon.ico  ({ICON_DIR / 'icon.ico'})")

    # macOS ICNS (macOS only — requires iconutil)
    if sys.platform == "darwin":
        try:
            _make_icns(master_path, ICON_DIR / "icon.icns")
            print(f"  icon.icns ({ICON_DIR / 'icon.icns'})")
        except Exception as e:
            print(f"  icon.icns skipped: {e}")
    else:
        print("  icon.icns skipped (run on macOS to generate)")

    # Tray PNG
    tray = _draw_tray(32)
    tray.save(ICON_DIR / "tray.png", "PNG")
    print(f"  tray.png  ({ICON_DIR / 'tray.png'})")

    print("\nDone! Icons saved to frontend/icons/")


if __name__ == "__main__":
    main()
