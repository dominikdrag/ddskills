#!/usr/bin/env python3
"""Put a rendered board next to its snapshot, with a 50% overlay, for checking.

Usage: compare.py <board.png> <snapshot.png> <out.png> [--width 390] [--crop-height 844]
Both images are scaled to the board width at 2x. The board is cropped to --crop-height points (the first
screen of a tall board) so it lines up with a one-screen snapshot. Needs Pillow.
"""
import argparse

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("board")
    parser.add_argument("snapshot")
    parser.add_argument("out")
    parser.add_argument("--width", type=int, default=390)
    parser.add_argument("--crop-height", type=int, default=844)
    args = parser.parse_args()
    w = args.width * 2
    board = Image.open(args.board).convert("RGB")
    board = board.resize((w, round(board.height * w / board.width)))
    board = board.crop((0, 0, w, min(board.height, args.crop_height * 2)))
    snap = Image.open(args.snapshot).convert("RGB")
    snap = snap.resize((w, round(snap.height * w / snap.width)))
    h = max(board.height, snap.height)
    over = Image.blend(board.crop((0, 0, w, h)), snap.crop((0, 0, w, h)), 0.5)
    sheet = Image.new("RGB", (w * 3 + 40, h + 30), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (image, label) in enumerate([(board, "board"), (snap, "snapshot"), (over, "overlay 50%")]):
        sheet.paste(image, (i * (w + 20), 30))
        draw.text((i * (w + 20) + 6, 8), label, fill="black")
    sheet.save(args.out)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
