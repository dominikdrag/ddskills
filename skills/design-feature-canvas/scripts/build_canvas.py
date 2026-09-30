#!/usr/bin/env python3
"""Write a feature canvas index (project/canvas.json) from rows.json.

Usage: build_canvas.py ROWS_JSON PROJECT_DIR [--existing CANVAS_JSON] [--now RFC3339]

rows.json:
{
  "title": "Paid feature designs",
  "overview": {"file": "Main.dc.html", "width": 1280, "height": 1120, "page": "overview", "pageName": "Overview"},
  "notDesigned": "optional; the overview artboard shows it, the script ignores it",
  "pages": [
    {"id": "lead", "name": "Remember their life", "fill": "green",
     "rows": [
       {"key": "gifts", "title": "Gift ideas · remember what you gave", "sticky": "Lead · 11/15 · M …",
        "artboards": [{"file": "Gifts-Overview.dc.html", "title": "G01 · Anna · gift ideas", "height": 1400, "links": true}]}
     ]}
  ]
}

Layout: 390 px artboards 80 px apart; a title note 250 px above each row; the verdict sticky
(440 px wide) after the last artboard; the next row starts 380 px below the row's tallest artboard.
The script fails when an artboard file is missing, a .dc.html in PROJECT_DIR is not listed,
an artboard's height differs from its $preview, or an href names a missing artboard.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

PHONE_WIDTH = 390
COLUMN = PHONE_WIDTH + 80
TITLE_OFFSET = 250
ROW_GAP = 380
STICKY_WIDTH = 440
STICKY_MAX_HEIGHT = 844
FILLS = {"gray", "red", "orange", "green", "teal", "blue", "purple", "pink"}
PREVIEW = re.compile(r"\"\$preview\"\s*:\s*\{\s*\"width\"\s*:\s*(\d+)\s*,\s*\"height\"\s*:\s*(\d+)")
HREF = re.compile(r"href=\"([^\"#][^\"]*\.dc\.html)\"")


def build(rows: Dict[str, Any], project: Path, existing: Dict[str, Any] | None, now: str) -> Dict[str, Any]:
    overview = rows["overview"]
    overview_page = overview.get("page", "overview")
    pages = [{"id": overview_page, "name": overview.get("pageName", "Overview")}]
    boards: Dict[str, Dict[str, Any]] = {
        overview["file"]: {"x": 0, "y": 0, "w": overview["width"], "h": overview["height"], "title": "Overview", "page": overview_page}
    }
    order: List[str] = [overview["file"]]
    notes: Dict[str, Dict[str, Any]] = {}
    for page in rows["pages"]:
        pages.append({"id": page["id"], "name": page["name"]})
        fill = page.get("fill", "green")
        if fill not in FILLS:
            raise ValueError(f"page {page['id']}: fill {fill!r} is not one of {sorted(FILLS)}")
        y = 0
        for row in page["rows"]:
            artboards = row["artboards"]
            if not artboards:
                raise ValueError(f"row {row['key']} has no artboards")
            for index, board in enumerate(artboards):
                entry = {"x": index * COLUMN, "y": y, "w": PHONE_WIDTH, "h": int(board["height"]), "title": board["title"], "page": page["id"]}
                if board.get("links"):
                    entry["is_interactive"] = True
                if board["file"] in boards:
                    raise ValueError(f"{board['file']} is listed twice")
                boards[board["file"]] = entry
                order.append(board["file"])
            count = len(artboards)
            notes[f"t_{row['key']}"] = {"x": 0, "y": y - TITLE_OFFSET, "text": row["title"], "kind": "title1", "maxW": count * COLUMN + STICKY_WIDTH, "page": page["id"]}
            if row.get("sticky"):
                notes[f"s_{row['key']}"] = {"x": count * COLUMN, "y": y, "w": STICKY_WIDTH, "maxH": STICKY_MAX_HEIGHT, "text": row["sticky"], "fill": fill, "size": "s", "page": page["id"]}
            y += max(int(board["height"]) for board in artboards) + ROW_GAP
    if existing:
        # Keep what people added in the editor: extra artboards, their own notes, and per-board keys such as guides.
        for name, entry in existing.get("boards", {}).items():
            if name in boards:
                for key, value in entry.items():
                    boards[name].setdefault(key, value)
            else:
                boards[name] = entry
                order.append(name)
        for key, note in existing.get("notes", {}).items():
            notes.setdefault(key, note)
        known = {page["id"] for page in pages}
        pages += [page for page in existing.get("pages", []) if page["id"] not in known]
    canvas: Dict[str, Any] = dict(existing or {})
    canvas.update({
        "v": 3,
        "title": canvas.get("title") or rows["title"],
        "launch": {"view": "canvas", "page": overview_page},
        "pages": pages,
        "boards": boards,
        "order": order,
        "notes": notes,
    })
    canvas.setdefault("designSystems", [])
    if "createdOnFiles" not in canvas and "convertedFrom" not in canvas:
        canvas["createdOnFiles"] = {"v": 1, "at": now}
    return canvas


def check(canvas: Dict[str, Any], project: Path) -> List[str]:
    problems: List[str] = []
    listed = set(canvas["boards"])
    present = {path.name for path in project.glob("*.dc.html")}
    for name in sorted(listed - present):
        problems.append(f"listed but missing: {name}")
    for name in sorted(present - listed):
        problems.append(f"present but not listed (it would still show on the canvas): {name}")
    for name in sorted(listed & present):
        src = (project / name).read_text(encoding="utf-8")
        match = PREVIEW.search(src)
        board = canvas["boards"][name]
        if match and (int(match.group(1)), int(match.group(2))) != (board["w"], board["h"]):
            problems.append(f"{name}: $preview {match.group(1)}x{match.group(2)} differs from index {board['w']}x{board['h']}")
        for target in HREF.findall(src):
            if target not in present:
                problems.append(f"{name}: link to missing artboard {target}")
    return problems


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("rows")
    parser.add_argument("project")
    parser.add_argument("--existing", help="an existing canvas.json whose other keys to keep")
    parser.add_argument("--now", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    args = parser.parse_args(argv)
    project = Path(args.project)
    rows = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    existing = json.loads(Path(args.existing).read_text(encoding="utf-8")) if args.existing else None
    try:
        canvas = build(rows, project, existing, args.now)
    except (KeyError, ValueError) as error:
        print(f"rows.json: {error}")
        return 1
    problems = check(canvas, project)
    for problem in problems:
        print(f"problem: {problem}")
    if problems:
        return 1
    (project / "canvas.json").write_text(json.dumps(canvas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {project / 'canvas.json'}: {len(canvas['boards'])} artboards, {len(canvas['notes'])} notes, {len(canvas['pages'])} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
