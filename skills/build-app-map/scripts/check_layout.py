#!/usr/bin/env python3
"""Cross-check the App Map index, manifest, board files and navigation map before publishing.

Usage: check_layout.py [project dir] [--manifest boards.json]
Defaults: ../project and boards.json next to this script.

Checks that every board file has a canvas.json entry and an `order` slot, every entry has a file, page ids
exist, board sizes match each file's $preview, boards.json lists exactly the screen and Design kit boards (everything
except Main.dc.html) with sources, a valid presentation, matching page id, height and syncedAt; boards and sticky
notes on a page do not overlap; note ids and fill colours are valid; and the navigation map has exactly one
card per board with no two cards overlapping. Exits 1 on any error.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILLS = {"gray", "red", "orange", "green", "teal", "blue", "purple", "pink"}
PRESENTATIONS = {"tab-root", "push", "sheet", "full-screen-cover", "menu", "inline-state", "system", "alert-or-dialog", "popover",
                 "kit"}  # kit: a Design kit board (the shipped design system), not a screen
CARD = re.compile(r'<a href="([^"#/:]+)\.dc\.html" style="position: absolute; left: (\d+)px; top: (\d+)px; width: (\d+)px; height: (\d+)px')


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def preview_size(path):
    src = open(path, encoding="utf-8").read()
    m = re.search(r'"\$preview"\s*:\s*\{\s*"width"\s*:\s*(\d+)\s*,\s*"height"\s*:\s*(\d+)', src)
    return (int(m.group(1)), int(m.group(2))) if m else None


def check(project, manifest_path):
    canvas = json.load(open(os.path.join(project, "canvas.json"), encoding="utf-8"))
    manifest = json.load(open(manifest_path, encoding="utf-8"))["boards"]
    errors = []
    files = {os.path.relpath(os.path.join(d, f), project) for d, _, fs in os.walk(project) for f in fs if f.endswith(".dc.html")}
    boards, order = canvas["boards"], canvas["order"]
    pages = {p["id"] for p in canvas.get("pages", [])}

    errors += [f"file without canvas.json entry: {f}" for f in sorted(files - set(boards))]
    errors += [f"canvas.json entry without file: {b}" for b in sorted(set(boards) - files)]
    errors += [f"missing from order: {b}" for b in sorted(set(boards) - set(order))]
    errors += [f"order lists unknown board: {b}" for b in order if b not in boards]
    if len(order) != len(set(order)):
        errors.append("order has duplicates")
    for name, entry in boards.items():
        if pages and entry.get("page") not in pages:
            errors.append(f"{name}: page '{entry.get('page')}' is not a page id")
        size = preview_size(os.path.join(project, name)) if name in files else None
        if size and size != (entry["w"], entry["h"]):
            errors.append(f"{name}: canvas.json {entry['w']}x{entry['h']} but $preview {size[0]}x{size[1]}")
    screens = {b[:-len(".dc.html")] for b in boards if b != "Main.dc.html"}
    errors += [f"board missing from boards.json: {b}" for b in sorted(screens - set(manifest))]
    errors += [f"boards.json lists a board the canvas does not have: {b}" for b in sorted(set(manifest) - screens)]
    for board in sorted(screens & set(manifest)):
        entry, info = boards[f"{board}.dc.html"], manifest[board]
        if info.get("pageId") != entry.get("page"):
            errors.append(f"{board}: boards.json pageId {info.get('pageId')} != canvas page {entry.get('page')}")
        if info.get("height") != entry["h"]:
            errors.append(f"{board}: boards.json height {info.get('height')} != canvas h {entry['h']}")
        if not info.get("sources"):
            errors.append(f"{board}: boards.json has no sources, so check_drift can never flag it")
        if info.get("presentation") not in PRESENTATIONS:
            errors.append(f"{board}: boards.json presentation '{info.get('presentation')}' is not one of {sorted(PRESENTATIONS)}")
        if not info.get("syncedAt"):
            errors.append(f"{board}: boards.json has no syncedAt")
    by_page = {}
    for name, entry in boards.items():
        by_page.setdefault(entry.get("page"), []).append((name, entry))
    for page, items in by_page.items():
        for i, (a, ea) in enumerate(items):
            for b, eb in items[i + 1:]:
                if overlap((ea["x"], ea["y"], ea["w"], ea["h"]), (eb["x"], eb["y"], eb["w"], eb["h"])):
                    errors.append(f"boards overlap on page {page}: {a} and {b}")
    for note_id, note in canvas.get("notes", {}).items():
        if not note.get("kind") and "w" in note:
            box = (note["x"], note["y"], note["w"], note.get("maxH", note["w"] * 4 // 3))
            for name, entry in by_page.get(note.get("page"), []):
                if overlap(box, (entry["x"], entry["y"], entry["w"], entry["h"])):
                    errors.append(f"sticky note {note_id} overlaps board {name}")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", note_id):
            errors.append(f"bad note id: {note_id}")
        if note.get("page") and pages and note["page"] not in pages:
            errors.append(f"note {note_id}: unknown page {note['page']}")
        if note.get("fill") and note["fill"] not in FILLS:
            errors.append(f"note {note_id}: fill '{note['fill']}' is not one of {sorted(FILLS)}")

    main_path = os.path.join(project, "Main.dc.html")
    if os.path.exists(main_path):
        cards = [(m.group(1), tuple(int(v) for v in m.groups()[1:])) for m in CARD.finditer(open(main_path, encoding="utf-8").read())]
        names = [name for name, _ in cards]
        errors += [f"Main.dc.html has no card for {b}" for b in sorted(screens - set(names))]
        errors += [f"Main.dc.html has a card for unknown board {n}" for n in sorted(set(names) - screens)]
        errors += [f"Main.dc.html has {names.count(n)} cards for {n}" for n in sorted(set(names)) if names.count(n) > 1]
        for i, (a, ra) in enumerate(cards):
            for b, rb in cards[i + 1:]:
                if overlap(ra, rb):
                    errors.append(f"map cards overlap: {a} and {b}")
    else:
        errors.append("no Main.dc.html (the navigation map)")
    return canvas, pages, errors


def main():
    args = sys.argv[1:]
    manifest = os.path.join(HERE, "boards.json")
    if "--manifest" in args:
        i = args.index("--manifest")
        manifest = args[i + 1]
        del args[i:i + 2]
    project = os.path.abspath(args[0] if args else os.path.join(HERE, "..", "project"))
    canvas, pages, errors = check(project, manifest)
    for error in errors:
        print(f"ERROR {error}")
    print(f"{len(canvas['boards'])} boards, {len(canvas.get('notes', {}))} notes, {len(pages)} pages: {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
