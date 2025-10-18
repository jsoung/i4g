#!/usr/bin/env python3
"""
synthesize_chat_screenshots.py
------------------------------
Generate synthetic chat-style screenshots (PNG) from JSONL text data.

Input  : JSONL file with {"text": "..."} or {"metadata": {...}, "text": "..."}
Output : ./chat_screens/ folder with chat_0001.png, chat_0002.png, ...

Usage:
    python tests/adhoc/synthesize_chat_screenshots.py --input data/bundles/ucirvine_sms.jsonl --limit 20
"""

import argparse
import json
import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# -------- CONFIG --------
BG_COLOR = (245, 245, 245)  # chat background
USER_COLORS = [(220, 248, 198), (255, 255, 255)]  # bubbles (sent, received)
TEXT_COLOR = (0, 0, 0)
FONT_SIZE = 22
IMG_WIDTH = 1080
MAX_BUBBLES = 8  # messages per screenshot


def load_font():
    """Try to load a readable system font."""
    try:
        return ImageFont.truetype("Arial.ttf", FONT_SIZE)
    except:
        return ImageFont.load_default()


def draw_bubble(draw, xy, text, font, bubble_color, max_width):
    """Draw a single chat bubble and return its bottom Y coordinate."""
    x, y = xy
    lines = textwrap.wrap(text, width=int(max_width / (FONT_SIZE * 0.5)))
    text_height = len(lines) * (FONT_SIZE + 4)
    text_width = max(font.getlength(line) for line in lines)
    pad = 20
    bubble = (x, y, x + text_width + pad * 2, y + text_height + pad)
    draw.rounded_rectangle(bubble, radius=20, fill=bubble_color)
    ty = y + pad / 2
    for line in lines:
        draw.text((x + pad, ty), line, font=font, fill=TEXT_COLOR)
        ty += FONT_SIZE + 4
    return bubble[3] + 10  # new y position


def create_chat_image(messages, out_path):
    """Render list of messages to a chat-style PNG."""
    font = load_font()
    img = Image.new("RGB", (IMG_WIDTH, 1800), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = 40
    for i, msg in enumerate(messages):
        sender_side = i % 2
        text = msg.get("text") or msg.get("message") or ""
        if not text:
            continue
        if sender_side == 0:  # left bubble
            x = 60
        else:  # right bubble
            text_width = font.getlength(text)
            x = IMG_WIDTH - 60 - min(text_width + 80, IMG_WIDTH // 2)
        y = draw_bubble(draw, (x, y), text, font, USER_COLORS[sender_side], IMG_WIDTH // 2)
        if y > 1700:
            break  # stop before overflow

    img = img.crop((0, 0, IMG_WIDTH, min(y + 60, 1800)))
    img.save(out_path)


def main(input_file, limit):
    output_dir = Path("chat_screens")
    output_dir.mkdir(exist_ok=True)
    with open(input_file, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f.readlines() if l.strip()]
    print(f"Loaded {len(lines)} records")

    # group messages randomly into chats of 3–8 lines
    idx = 0
    n = 0
    while idx < len(lines) and n < limit:
        num_msgs = random.randint(3, MAX_BUBBLES)
        chat_msgs = lines[idx : idx + num_msgs]
        out_path = output_dir / f"chat_{n+1:04d}.png"
        create_chat_image(chat_msgs, out_path)
        idx += num_msgs
        n += 1
    print(f"✅ Generated {n} chat screenshots in {output_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to JSONL file (e.g., ucirvine_sms.jsonl)")
    parser.add_argument("--limit", type=int, default=20, help="Number of screenshots to generate")
    args = parser.parse_args()
    main(args.input, args.limit)
