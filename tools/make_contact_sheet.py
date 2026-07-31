from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    paths = sorted(
        [p for p in source.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}],
        key=lambda p: (len(p.stem), p.stem),
    )
    thumb_w, thumb_h, label_h, cols = 360, 220, 28, 3
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for i, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w - 12, thumb_h - 12))
        x = (i % cols) * thumb_w + (thumb_w - image.width) // 2
        y = (i // cols) * (thumb_h + label_h) + (thumb_h - image.height) // 2
        sheet.paste(image, (x, y))
        draw.text(((i % cols) * thumb_w + 8, (i // cols) * (thumb_h + label_h) + thumb_h + 4),
                  path.name, fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    print(output)


if __name__ == "__main__":
    main()
