#!/usr/bin/env python3
"""Tile images into labelled contact sheets, for surveying snapshots or reviewing a page of rendered boards.

Usage: contact_sheet.py <out.png> <image> [<image> ...] [--columns 6] [--width 260] [--max-height 2000]
Each tile is scaled to --width px and labelled with its file name; tall images are cropped to --max-height
tiles' worth of height. Writes <out>.png, or <out>-2.png, <out>-3.png … when one sheet would pass 6000 px.
Needs Pillow.
"""
import argparse
import os

from PIL import Image, ImageDraw

LABEL = 28
GAP = 12
SHEET_MAX = 6000


def tile(path, width, max_height):
    image = Image.open(path).convert("RGB")
    image = image.resize((width, max(1, round(image.height * width / image.width))))
    return image.crop((0, 0, width, min(image.height, max_height)))


def sheets(tiles, columns, width):
    rows = [tiles[i:i + columns] for i in range(0, len(tiles), columns)]
    pages, current, height = [], [], 0
    for row in rows:
        row_h = max(t.height for _, t in row) + LABEL + GAP
        if current and height + row_h > SHEET_MAX:
            pages.append(current)
            current, height = [], 0
        current.append((row, row_h))
        height += row_h
    if current:
        pages.append(current)
    out = []
    for page in pages:
        sheet = Image.new("RGB", (columns * (width + GAP) + GAP, sum(h for _, h in page) + GAP), "white")
        draw = ImageDraw.Draw(sheet)
        y = GAP
        for row, row_h in page:
            for i, (name, image) in enumerate(row):
                x = GAP + i * (width + GAP)
                draw.text((x, y + 6), name[: width // 6], fill="black")
                sheet.paste(image, (x, y + LABEL))
            y += row_h
        out.append(sheet)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("out")
    parser.add_argument("images", nargs="+")
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--width", type=int, default=260)
    parser.add_argument("--max-height", type=int, default=2000)
    args = parser.parse_args()
    tiles = [(os.path.basename(p), tile(p, args.width, args.max_height)) for p in args.images]
    base, ext = os.path.splitext(args.out)
    for n, sheet in enumerate(sheets(tiles, args.columns, args.width), start=1):
        path = args.out if n == 1 else f"{base}-{n}{ext or '.png'}"
        sheet.save(path)
        print("wrote", path)


if __name__ == "__main__":
    main()
