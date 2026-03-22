from __future__ import annotations

from io import BytesIO
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageFont
import requests

from tablebot.config import SOURCE_CODE_PRO_FONT
from tablebot.constants.colors import VR_BACKGROUND_COLOR, VR_TEXT_COLOR


def text_to_image(
    text: str,
    font_path: str = SOURCE_CODE_PRO_FONT,
    font_size: int = 20,
    padding: int = 20,
    bg_color: str = VR_BACKGROUND_COLOR,
    fg_color: str = VR_TEXT_COLOR,
) -> Image.Image:
    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        font = ImageFont.load_default()

    lines = text.splitlines() or [""]
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bboxes = [draw.textbbox((0, 0), line or " ", font=font) for line in lines]
    max_width = max(x1 - x0 for x0, y0, x1, y1 in bboxes)
    line_height = max(y1 - y0 for x0, y0, x1, y1 in bboxes)

    image = Image.new("RGB", (max_width + padding * 2, line_height * len(lines) + padding * 2), color=bg_color)
    draw = ImageDraw.Draw(image)
    y = padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill=fg_color)
        y += line_height
    return image


def image_to_file(image: Image.Image, filename: str) -> tuple[BytesIO, str]:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer, filename


def get_table_image(
    table_text: str,
    timeout: int = 5,
) -> tuple[Image.Image, str]:
    table_text_url = quote(table_text, safe="")
    image_url = f"https://gb.hlorenzi.com/table.png?data={table_text_url}"
    edit_url = f"https://gb.hlorenzi.com/table?data={table_text_url}"

    try:
        response = requests.get(image_url, timeout=timeout)
    except requests.exceptions.Timeout:
        return text_to_image("Retrieving image from Lorenzi took longer than expected.\nTry again in a moment, and remember /tt still works."), edit_url
    except requests.exceptions.RequestException as exc:
        return text_to_image(f"Failed to retrieve image. An error occurred:\n{exc}"), edit_url

    if response.status_code == 200:
        return Image.open(BytesIO(response.content)).convert("RGB"), edit_url

    return text_to_image(f"Failed to retrieve image. Lorenzi status code: {response.status_code}"), edit_url
