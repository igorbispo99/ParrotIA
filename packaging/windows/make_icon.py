"""Render the brand's vector-style parrot badge as PNG and multi-size ICO."""

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    assets = Path(__file__).resolve().parents[2] / "src/parrotia/assets"
    assets.mkdir(parents=True, exist_ok=True)
    scale = 4
    image = Image.new("RGBA", (256 * scale, 256 * scale))
    draw = ImageDraw.Draw(image)

    def ellipse(bounds, color):
        draw.ellipse(tuple(int(v * scale) for v in bounds), fill=color)

    def polygon(points, color):
        draw.polygon([(int(x * scale), int(y * scale)) for x, y in points], fill=color)

    draw.rounded_rectangle(
        (8 * scale, 8 * scale, 248 * scale, 248 * scale),
        radius=60 * scale,
        fill="#0B2B2C",
    )
    ellipse((32, 30, 224, 222), "#0E7C7B")
    # Green crown, golden cheek, white face and navy hooked beak.
    ellipse((57, 43, 190, 181), "#1FAE6B")
    polygon([(64, 112), (58, 212), (127, 174), (164, 128)], "#1FAE6B")
    polygon([(68, 158), (53, 215), (113, 184), (149, 143)], "#2D7DD2")
    ellipse((87, 68, 195, 173), "#F4B740")
    ellipse((103, 64, 187, 145), "#F3FBFA")
    ellipse((145, 79, 165, 99), "#0B2B2C")
    ellipse((151, 82, 157, 88), "#FFFFFF")
    ellipse((168, 98, 215, 155), "#0B2B2C")
    polygon([(191, 122), (214, 122), (208, 160), (189, 177), (197, 143)], "#0B2B2C")
    polygon([(172, 103), (189, 104), (199, 120), (177, 119)], "#2D7DD2")
    # Three bright transcript lines anchor the badge at small icon sizes.
    for x, y, width in [(119, 183, 64), (110, 199, 73), (119, 215, 46)]:
        draw.rounded_rectangle(
            (x * scale, y * scale, (x + width) * scale, (y + 7) * scale),
            radius=3 * scale,
            fill="#F3FBFA",
        )
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image.save(assets / "parrotia.png")
    image.save(
        assets / "parrotia.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
    )


if __name__ == "__main__":
    main()
