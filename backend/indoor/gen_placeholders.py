"""M0: grey placeholder floor images with a grid (replaced by real plans at M1)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "data" / "floorplans"
OUT.mkdir(parents=True, exist_ok=True)
for n in range(4):
    img = Image.new("RGB", (1200, 800), (200, 200, 200))
    d = ImageDraw.Draw(img)
    for x in range(0, 1200, 100):
        d.line([(x, 0), (x, 800)], fill=(160, 160, 160))
    for y in range(0, 800, 100):
        d.line([(0, y), (1200, y)], fill=(160, 160, 160))
    d.text((20, 20), f"PLACEHOLDER floor {n}", fill=(60, 60, 60))
    img.save(OUT / f"floor_{n}.png")
