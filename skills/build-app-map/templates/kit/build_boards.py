#!/usr/bin/env python3
"""Build App Map boards from the kit into a folder.

Board files are the source of truth once published (people edit them on the canvas): build into scratch and
compare with the live file; never write over the live canvas blindly.

Usage: python3 kit/build_boards.py --out <dir> [--only Name,Name] [--list] [--manifest <boards.json | inventory.json>]
Default manifest: ../tools/boards.json. During the first build pass the scratch inventory.json instead.

Draw functions live in kit/boards/<area>.py, one module per area: `@c.draw("Name")` returns the markup inside the
board root (see chrome.py). Boards marked `tall` are measured with headless Chrome (tools/render.py --measure) and
grown to show their whole scroll. A Dark-<Name> copy renders its light board's function in the dark palette, with
links pointed at the other dark copies.
"""
import argparse
import importlib
import json
import os
import pkgutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, HERE)
sys.path.insert(0, TOOLS)

import chrome as c  # noqa: E402


def load_boards(path):
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data["boards"], list):
        from build_index import expand  # inventory.json: add the Dark-* copies the index will list
        return expand(data)
    return [dict(entry, name=name) for name, entry in data["boards"].items()]


def load_draw_modules():
    folder = os.path.join(HERE, "boards")
    for module in sorted(m.name for m in pkgutil.iter_modules([folder])):
        importlib.import_module(f"boards.{module}")


def render(board, height, dark_names):
    light = board.get("light")
    c.use("dark" if light else "light")
    markup = c.page(board["title"], height, c.DRAW[light or board["name"]]())
    if light:
        for name in dark_names:
            markup = markup.replace(f'href="{name}.dc.html"', f'href="Dark-{name}.dc.html"')
    return markup


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", default="")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--manifest", default=os.path.join(TOOLS, "boards.json"))
    args = parser.parse_args()
    boards = load_boards(args.manifest)
    if args.list:
        for b in boards:
            print(b["name"], b.get("pageId") or b.get("page"), b["row"], sep="\t")
        return 0
    load_draw_modules()
    only = set(filter(None, args.only.split(",")))
    dark_names = [b["light"] for b in boards if b.get("light")]
    os.makedirs(args.out, exist_ok=True)
    missing = []
    for b in boards:
        if only and b["name"] not in only:
            continue
        if (b.get("light") or b["name"]) not in c.DRAW:
            missing.append(b["name"])
            continue
        path = os.path.join(args.out, f"{b['name']}.dc.html")
        height = c.HEIGHT
        open(path, "w", encoding="utf-8").write(render(b, height, dark_names))
        if b.get("tall"):
            from render import measure
            extra = measure(path, os.path.join(TOOLS, "config.json")) or 0
            if extra:
                height += extra
                open(path, "w", encoding="utf-8").write(render(b, height, dark_names))
        print(b["name"], height)
    for name in missing:
        print(f"no draw function for {name}", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
