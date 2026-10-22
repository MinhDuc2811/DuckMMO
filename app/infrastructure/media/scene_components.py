"""Reusable raster scene layers. Same time-based components power GIF and final export."""

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageOps

from app.infrastructure.media.frames import font, wrap


@lru_cache(maxsize=24)
def face(size):
    return font(size)


def card(canvas, image, box, accent, angle=0):
    x, y, width, height = (round(v) for v in box)
    layer = Image.new("RGB", (width, height), "#ffffff")
    if image is not None:
        layer.paste(ImageOps.fit(image, (width - 10, height - 16)), (5, 5))
    else:
        draw = ImageDraw.Draw(layer)
        draw.rectangle((5, 5, width - 6, height - 12), fill=accent)
        draw.ellipse((width * 0.15, height * 0.15, width * 0.85, height * 0.75), fill="#243650")
    if angle:
        rotated = layer.convert("RGBA").rotate(
            angle, resample=Image.Resampling.BICUBIC, expand=True
        )
        canvas.paste(rotated, (x, y), rotated)
    else:
        canvas.paste(layer, (x, y))


def title_layer(canvas, title, accent, reveal, layout):
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size
    size = max(14, round(w * (0.075 if layout == "full" else 0.055)))
    f = face(size)
    lines = wrap(draw, title, f, w * 0.84)[:4]
    y = h * 0.10 + (1 - reveal) * h * 0.025
    for line in lines:
        box = draw.textbbox((0, 0), line, font=f)
        draw.rectangle(
            (w * 0.065, y, min(w * 0.95, w * 0.09 + box[2]), y + size * 1.45), fill="#111827"
        )
        draw.text((w * 0.08, y), line, font=f, fill=accent)
        y += size * 1.5


def progress_layer(canvas, accent, fraction, index, total):
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size
    draw.rectangle((w * 0.06, h * 0.91, w * 0.94, h * 0.916), fill="#62697a")
    draw.rectangle((w * 0.06, h * 0.91, w * (0.06 + 0.88 * fraction), h * 0.916), fill=accent)
    draw.text(
        (w * 0.06, h * 0.93),
        f"{index + 1:02} / {total:02}",
        font=face(max(10, round(w * 0.027))),
        fill=accent,
    )


def scene_frame(size, style, scene, t, options, image=None):
    """Four independent layouts plus reusable title/card/rule/progress/decorative layers."""
    w, h = size
    duration = scene["duration"]
    phase = max(0, min(1, t / duration))
    reveal = 1 - (1 - min(1, t / 0.55)) ** 3
    strength = {"gentle": 0.35, "medium": 0.7, "strong": 1}[options["intensity"]]
    drift = math.sin(t * 1.4 + scene["index"]) * w * 0.025 * strength
    canvas = Image.new("RGB", size, style["background"])
    draw = ImageDraw.Draw(canvas)
    accent = style["accent"]
    draw.ellipse(
        (w * 0.55 + drift, -h * 0.1, w * 1.2 + drift, h * 0.4),
        outline=accent,
        width=max(1, round(w * 0.008)),
    )
    layout = scene["layout"]
    if layout == "full":
        if image is not None:
            if options.get("video_fit") == "pad":
                crop = ImageOps.contain(image, (w, h))
                canvas.paste(crop, ((w - crop.width) // 2, (h - crop.height) // 2))
            else:
                crop = ImageOps.fit(image, (round(w * 1.1), round(h * 1.1)))
                canvas.paste(crop, (-round(w * 0.05 + drift), -round(h * 0.05)))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((w * 0.06, h * 0.39, w * (0.06 + 0.88 * reveal), h * 0.405), fill=accent)
    elif layout == "collage":
        card(
            canvas,
            image,
            (w * 0.08 + drift, h * 0.33 + (1 - reveal) * h * 0.08, w * 0.57, h * 0.36),
            accent,
            5 * strength,
        )
        card(canvas, image, (w * 0.42 - drift, h * 0.47, w * 0.44, h * 0.28), accent, -7 * strength)
    elif layout == "panels":
        gap = w * 0.025
        card(canvas, image, (w * 0.06, h * 0.34, w * 0.88, h * 0.23), accent)
        card(canvas, image, (w * 0.06 + drift, h * 0.60, w * 0.43 - gap, h * 0.19), accent)
        card(canvas, image, (w * 0.51 - drift, h * 0.60, w * 0.43, h * 0.19), accent)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (w * 0.42, h * 0.52, w * 0.9, h * 0.605),
            radius=w * 0.025,
            fill="white",
            outline=accent,
            width=3,
        )
        draw.text((w * 0.46, h * 0.54), "…", font=face(max(12, round(w * 0.06))), fill="#111827")
    else:
        if image is not None:
            card(canvas, image, (w * 0.60 + drift, h * 0.35, w * 0.3, h * 0.25), accent)
        draw = ImageDraw.Draw(canvas)
        draw.text((w * 0.08, h * 0.32), "“", font=face(round(w * 0.24)), fill=accent)
        draw.line(
            (w * 0.10, h * 0.69, w * (0.10 + 0.72 * reveal), h * 0.69),
            fill=accent,
            width=max(2, round(w * 0.008)),
        )
    if layout in ("full", "quote") and scene.get("text"):
        draw = ImageDraw.Draw(canvas)
        text_font = face(max(12, round(w * 0.052)))
        text_width = w * 0.76 if layout == "full" else w * 0.46
        lines = wrap(draw, scene["text"], text_font, text_width)[:3]
        for line_index, line in enumerate(lines):
            y = h * 0.48 + line_index * w * 0.075 + (1 - reveal) * h * 0.04
            draw.text(
                (w * 0.10, y),
                line,
                font=text_font,
                fill="white",
                stroke_width=max(1, round(w * 0.003)),
                stroke_fill="#111827",
            )
    title_layer(canvas, scene["title"], accent, reveal, layout)
    progress_layer(canvas, accent, phase, scene["index"], scene["total"])
    return canvas
