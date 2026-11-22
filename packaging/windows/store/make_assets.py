"""Generate Microsoft Store listing images from the repository's own artwork.

The Store wants screenshots of at least 1366x768 and square logos. The checked-in
docs/screenshot.png is a smaller Linux capture, so this script crops away the
window frame and stray edge pixels and places the application window on a plain
background at 1920x1080. The icon source is 256x256, so larger logos are scaled up
and will look soft; replace them with art made from a vector original when one exists.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "assets"
SCREENSHOT = ROOT / "docs/screenshot.png"
ICON = ROOT / "src/parrotia/assets/parrotia.png"
# Crop box (left, top, right, bottom) of the application content inside screenshot.png:
# removes the X11 title bar at the top, the window's edge columns, and a few stray
# terminal pixels at the bottom.
CONTENT_BOX = (3, 30, 859, 842)


def background_colour(image: Image.Image) -> tuple[int, int, int]:
    """The window's own dark teal, sampled from a quiet pixel inside the content."""
    return image.convert("RGB").getpixel((5, 400))


def screenshot(destination: Path, size: tuple[int, int] = (1920, 1080)) -> None:
    with Image.open(SCREENSHOT) as source:
        content = source.convert("RGB").crop(CONTENT_BOX)
        canvas = Image.new("RGB", size, background_colour(source))
    height = int(size[1] * 0.94)
    width = round(content.width * height / content.height)
    content = content.resize((width, height), Image.Resampling.LANCZOS)
    canvas.paste(content, ((size[0] - width) // 2, (size[1] - height) // 2))
    canvas.save(destination)


def logo(destination: Path, side: int, icon_share: float = 0.72) -> None:
    with Image.open(ICON) as source:
        icon = source.convert("RGBA")
    # The icon's own tile colour, so the tile merges with the background.
    tile = icon.getpixel((18, icon.height // 2))
    assert tile[3] == 255, "expected an opaque tile pixel"
    canvas = Image.new("RGBA", (side, side), tile)
    edge = round(side * icon_share)
    icon = icon.resize((edge, edge), Image.Resampling.LANCZOS)
    canvas.alpha_composite(icon, ((side - edge) // 2, (side - edge) // 2))
    canvas.convert("RGB").save(destination)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    screenshot(OUT / "screenshot-1920x1080.png")
    logo(OUT / "logo-300x300.png", 300)
    logo(OUT / "logo-1080x1080.png", 1080)
    for path in sorted(OUT.glob("*.png")):
        with Image.open(path) as image:
            print(path.name, image.size)


if __name__ == "__main__":
    main()
