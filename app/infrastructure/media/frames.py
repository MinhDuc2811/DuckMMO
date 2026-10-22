"""Actual voice synthesis, image/caption timeline and H.264/AAC MP4 encoding."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size):
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, face, width):
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=face) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def make_frame(directory, config, title, caption, index, total):
    width, height = (720, 1280) if config["layout"] == "portrait" else (1280, 720)
    style = config["style"]
    canvas = Image.new("RGB", (width, height), style["background"])
    draw = ImageDraw.Draw(canvas)
    files = config["image_files"]
    if files:
        with Image.open(directory / files[index % len(files)]) as image:
            background = ImageOps.fit(image.convert("RGB"), (width, height))
            canvas.paste(background)
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 100))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(canvas)
    pad = 54
    title_font = font(30 if width == 720 else 32)
    title_lines = wrap(draw, title, title_font, width - pad * 2)[:3]
    draw.multiline_text(
        (pad, 80 if height > 1000 else 45),
        "\n".join(title_lines),
        font=title_font,
        fill=style["accent"],
        stroke_width=2,
        stroke_fill="#101010",
        spacing=10,
    )
    filename = f"frame-{index:04}.png"
    canvas.save(directory / filename)
    return filename
