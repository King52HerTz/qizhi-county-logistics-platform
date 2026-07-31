from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path("E:/wuliu_project/docs/assets/project-document")
SOURCE = ROOT / "24-system-er-image2-source.png"
OUTPUT = ROOT / "24-system-er-image2.png"


def font(size: int):
    for candidate in (
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
    ):
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size, index=0)
    return ImageFont.load_default()


image = Image.open(SOURCE).convert("RGB")
draw = ImageDraw.Draw(image)

# Image generation connected audit_logs to driver_assignments. Remove only
# that erroneous connector and preserve the generated entity-card artwork.
draw.rectangle((244, 748, 722, 812), fill="white")

green = "#164F31"
amber = "#B97700"
line_width = 3

# Correct relationship: users 1 -- N driver_assignments, routed around cards.
points = [(235, 452), (270, 452), (270, 620), (680, 620), (680, 800), (724, 800)]
draw.line(points, fill=green, width=line_width, joint="curve")

# Crow-foot-like end marker at driver_assignments.
draw.line([(724, 800), (710, 792)], fill=green, width=line_width)
draw.line([(724, 800), (710, 808)], fill=green, width=line_width)

draw.text((244, 423), "1", font=font(19), fill=green)
draw.text((690, 772), "N", font=font(19), fill=green)
draw.text((446, 580), "驾驶", font=font(22), fill=amber)

image.save(OUTPUT, quality=96)
print(OUTPUT)
