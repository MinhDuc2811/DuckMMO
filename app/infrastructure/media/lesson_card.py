"""Static white lesson card over an image or a decoded video frame."""

from PIL import Image, ImageDraw, ImageOps

from app.contracts.errors import VideoFailure
from app.infrastructure.media.frames import font, wrap


def lesson_card_frame(size, style, scene, image, fit="crop"):
    width, height = size
    canvas = Image.new("RGB", size, style["background"])
    if image is not None:
        if fit == "pad":
            background = ImageOps.contain(image, size)
            canvas.paste(
                background, ((width - background.width) // 2, (height - background.height) // 2)
            )
        else:
            canvas.paste(ImageOps.fit(image, size))
    draw = ImageDraw.Draw(canvas)
    unit = min(width, height)
    left, top = round(width * 0.07), round(height * 0.17)
    card_width = round(width * (0.93 - style.get("card_safe_right", 0.07)))
    padding = round(unit * 0.045)
    available_width = card_width - 2 * padding
    available_height = round(height * 0.58)
    title_font = font(max(12, round(unit * 0.032)))
    title_lines = wrap(draw, scene["title"], title_font, available_width)
    title_step = round(title_font.size * 1.5)
    title_height = len(title_lines) * title_step
    text = scene.get("text", "")
    minimum = max(12, round(unit * 0.03))
    for font_size in range(max(minimum, round(unit * 0.052)), minimum - 1, -1):
        body_font = font(font_size)
        lines = wrap(draw, text, body_font, available_width)
        step = round(font_size * 1.5)
        card_height = 2 * padding + title_height + padding + len(lines) * step
        if card_height <= available_height and all(
            draw.textlength(line, font=body_font) <= available_width for line in lines
        ):
            break
    else:
        raise VideoFailure(
            "Nội dung quá dài cho khung trắng. Hãy rút gọn hoặc chia thành nhiều cảnh."
        )
    if any(draw.textlength(line, font=title_font) > available_width for line in title_lines):
        raise VideoFailure("Tiêu đề quá dài cho khung trắng. Hãy rút gọn tiêu đề.")
    card_height = max(round(height * 0.20), card_height)
    radius = max(5, round(unit * 0.018))
    shadow = Image.new("RGBA", size)
    shadow_draw = ImageDraw.Draw(shadow)
    offset = max(2, round(unit * 0.009))
    shadow_draw.rounded_rectangle(
        (left + offset, top + offset, left + card_width + offset, top + card_height + offset),
        radius=radius,
        fill=(0, 0, 0, 115),
    )
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (left, top, left + card_width, top + card_height),
        radius=radius,
        fill="white",
        outline="#e4e7e5",
        width=max(1, round(unit * 0.002)),
    )
    cursor = top + padding
    for line in title_lines:
        draw.text((left + padding, cursor), line, font=title_font, fill=style["accent"])
        cursor += title_step
    cursor += padding
    for line in lines:
        draw.text((left + padding, cursor), line, font=body_font, fill="#15201c")
        cursor += step
    return canvas
