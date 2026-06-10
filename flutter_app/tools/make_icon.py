"""Generate a 1024x1024 app icon — Southbrook walnut square with 'SK' wordmark.

Run once from the flutter_app/ dir:
  python3 tools/make_icon.py
Output: assets/icon/icon.png + assets/icon/icon_foreground.png
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
WALNUT = (30, 58, 95)         # SouthbrookColors.walnut
LINEN = (245, 239, 230)       # SouthbrookColors.linen

out_dir = Path(__file__).resolve().parent.parent / "assets" / "icon"
out_dir.mkdir(parents=True, exist_ok=True)

# Square (legacy / iOS)
icon = Image.new("RGBA", (SIZE, SIZE), WALNUT)
draw = ImageDraw.Draw(icon)

# Try a few common bundled fonts; fall back to default if none work.
font = None
for candidate in [
    "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]:
    if Path(candidate).exists():
        try:
            font = ImageFont.truetype(candidate, 460)
            break
        except OSError:
            pass
if font is None:
    font = ImageFont.load_default()

text = "SK"
bbox = draw.textbbox((0, 0), text, font=font)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]
draw.text(
    ((SIZE - text_w) / 2 - bbox[0],
     (SIZE - text_h) / 2 - bbox[1] - 30),
    text,
    fill=LINEN,
    font=font,
)
icon.save(out_dir / "icon.png", "PNG")

# Adaptive foreground (Android 8+) — same content on transparent so the
# Android system places it on a circle/squircle background of our choice.
fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
fg_draw = ImageDraw.Draw(fg)
# Inset content into the 66% safe zone Android adaptive icons require.
inset = int(SIZE * 0.18)
inner = SIZE - 2 * inset
inner_img = Image.new("RGBA", (inner, inner), WALNUT)
inner_draw = ImageDraw.Draw(inner_img)
inner_font = ImageFont.truetype(font.path, int(font.size * inner / SIZE)) \
    if hasattr(font, "path") else font
ib = inner_draw.textbbox((0, 0), text, font=inner_font)
inner_draw.text(
    ((inner - (ib[2] - ib[0])) / 2 - ib[0],
     (inner - (ib[3] - ib[1])) / 2 - ib[1] - 20),
    text,
    fill=LINEN,
    font=inner_font,
)
fg.paste(inner_img, (inset, inset), inner_img)
fg.save(out_dir / "icon_foreground.png", "PNG")

print(f"wrote {out_dir/'icon.png'}")
print(f"wrote {out_dir/'icon_foreground.png'}")
