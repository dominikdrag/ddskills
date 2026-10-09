#!/usr/bin/env python3
"""Write the first canvas.json and boards.json of an App Map from inventory.json and the built board files.

Usage: build_index.py <inventory.json> --project <project dir> --manifest <boards.json> [--force] [--now RFC3339]

Run once, when the canvas is first built. After that people move boards and notes on the canvas, so
canvas.json is edited in place: the script refuses to overwrite an existing canvas.json without --force.

inventory.json:
{
  "title": "<App> App Map",
  "canvas": "https://claude.ai/artifact/<id>",          // the canvas link, once created
  "syncedAt": "<main commit the boards were built from>",
  "builtOn": "6 October 2026",
  "map": {"file": "Main.dc.html", "width": 1768, "height": 3735, "page": "map", "pageName": "Overview"},
  "howTo": "<optional text for the how-to note on the Overview page>",
  "designWork": "<optional text for the design-work note>",
  "maxPerRow": 8,
  "pages": [{"id": "start", "name": "Launch & first use"}, {"id": "kit", "name": "Design kit"}],
  "darkPage": {"id": "dark", "name": "Dark appearance", "row": "Dark appearance"},   // only when boards have dark copies
  "boards": [
    {"name": "Launch-Loading", "title": "Launch", "page": "start", "row": "Launch and first use",
     "presentation": "inline-state", "sources": ["<repo path>"], "snapshot": null, "snapshots": [],
     "snapshotIsMock": false, "undrawn": [], "tall": false,
     "note": "Launch\\nWhere it opens from, what its controls lead to, states not drawn.",
     "dark": false, "darkSnapshot": null, "darkSnapshots": []},
    {"name": "Kit-Tokens", "title": "Tokens", "page": "kit", "row": "Foundations", "presentation": "kit",
     "sources": ["<design system folder>/Colors.xcassets/", "<token file>"], "snapshot": null, "tall": true,
     "note": "Tokens\nEvery colour token, light and dark side by side, with its role."}
  ]
}

Design kit boards are boards with "presentation": "kit" on the kit page; a source ending in / covers a folder.
A board with "dark": true gets a copy named Dark-<name> on the dark page (title "<title> (dark)", `light`
naming the original); expand() adds them after the light boards, and kit/build_boards.py uses the same list.

Layout: boards in inventory order, one row per (page, row) in first-seen order, `width` px boards 80 px
apart; a row longer than maxPerRow wraps into a continued row. The row title note sits 250 px above its
row; the row's sticky note (every board's `note`, in order) sits after its last board; the next row's
boards start 120 px below the tallest board plus 250 px for its title. Heights come from each file's $preview.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

GAP_X, ROW_GAP, TITLE_ABOVE, NOTE_W = 80, 120, 250, 420
PREVIEW = re.compile(r'"\$preview"\s*:\s*\{\s*"width"\s*:\s*(\d+)\s*,\s*"height"\s*:\s*(\d+)')
ABOUT = ("One entry per App Map board. sources/snapshots: what the board was rebuilt from; snapshot: the one snapshot "
         "matching the drawn state (null when none draws it); snapshotIsMock: the snapshot uses mock UI, so use it only for "
         "shared styling; undrawn: files that are known states we do not draw (check_drift ignores them); syncedAt: the main "
         "commit the board was last rebuilt from or checked against; light: on a Dark-* copy, the light board it copies. "
         "scannedThrough: the main commit up to which new-screen candidates were handled. publishPending: files updated in "
         "the repo but not yet published to the canvas.")


def size_of(project, name):
    src = open(os.path.join(project, f"{name}.dc.html"), encoding="utf-8").read()
    m = PREVIEW.search(src)
    if not m:
        raise ValueError(f"{name}.dc.html has no $preview")
    return int(m.group(1)), int(m.group(2))


def expand(inventory):
    """The inventory's boards in order, then a Dark-<name> copy of every board marked dark."""
    boards = [dict(b) for b in inventory["boards"]]
    dark = inventory.get("darkPage") or {"id": "dark", "name": "Dark appearance", "row": "Dark appearance"}
    for b in inventory["boards"]:
        if not b.get("dark"):
            continue
        boards.append({
            "name": f"Dark-{b['name']}", "title": f"{b['title']} (dark)", "page": dark["id"], "row": dark.get("row", dark["name"]),
            "presentation": b["presentation"], "sources": b["sources"], "snapshot": b.get("darkSnapshot"),
            "snapshots": b.get("darkSnapshots", []), "snapshotIsMock": bool(b.get("snapshotIsMock")), "undrawn": [],
            "tall": bool(b.get("tall")), "light": b["name"], "syncedAt": b.get("syncedAt"),
            "note": f"{b['title']} (dark)\nThe light board {b['name']} in dark appearance; links go to the other dark boards where one exists."})
    return boards


def pages_of(inventory):
    pages = list(inventory["pages"])
    if any(b.get("dark") for b in inventory["boards"]):
        dark = inventory.get("darkPage") or {"id": "dark", "name": "Dark appearance"}
        if dark["id"] not in {p["id"] for p in pages}:
            # Before the Design kit page, which stays last; after the screen pages otherwise.
            kit_pages = {b["page"] for b in inventory["boards"] if b["presentation"] == "kit"}
            at = next((i for i, p in enumerate(pages) if p["id"] in kit_pages), len(pages))
            pages.insert(at, {"id": dark["id"], "name": dark["name"]})
    return pages


def rows_of(inventory):
    """[(page id, row title, [boards])] in first-seen order, long rows wrapped."""
    rows, seen = [], {}
    for board in expand(inventory):
        key = (board["page"], board["row"])
        if key not in seen:
            seen[key] = len(rows)
            rows.append((board["page"], board["row"], []))
        rows[seen[key]][2].append(board)
    limit = inventory.get("maxPerRow", 8)
    wrapped = []
    for page, title, items in rows:
        for start in range(0, len(items), limit):
            wrapped.append((page, title if start == 0 else f"{title}, continued", items[start:start + limit]))
    return wrapped


def build(inventory, project, now):
    all_boards = expand(inventory)
    page_ids = [p["id"] for p in pages_of(inventory)]
    page_names = {p["id"]: p["name"] for p in pages_of(inventory)}
    m = inventory["map"]
    map_page = m.get("page", "map")
    names = [b["name"] for b in all_boards]
    if len(names) != len(set(names)):
        raise ValueError("a board name is listed twice")
    for board in all_boards:
        if board["page"] not in page_names:
            raise ValueError(f"{board['name']}: page {board['page']!r} is not in pages")
        if not board.get("sources"):
            raise ValueError(f"{board['name']}: no sources")
    sizes = {name: size_of(project, name) for name in names}

    boards = {m["file"]: {"x": 0, "y": 0, "w": m["width"], "h": m["height"], "title": "Navigation map", "page": map_page,
                          "is_interactive": True}}
    order = [m["file"]]
    notes = {}
    y_by_page, n_by_page = {}, {}
    for page, title, items in rows_of(inventory):
        y = y_by_page.get(page, 0)
        n = n_by_page.get(page, 0)
        tallest = max(sizes[b["name"]][1] for b in items)
        x = 0
        for board in items:
            w, h = sizes[board["name"]]
            boards[f"{board['name']}.dc.html"] = {"x": x, "y": y, "w": w, "h": h, "title": board["title"], "page": page,
                                                  "is_interactive": True}
            order.append(f"{board['name']}.dc.html")
            x += w + GAP_X
        notes[f"t_{page}_{n}"] = {"x": 0, "y": y - TITLE_ABOVE, "text": title, "kind": "title1", "maxW": x - GAP_X, "w": 240,
                                  "page": page}
        text = "\n\n".join(b.get("note") or b["title"] for b in items)
        notes[f"s_{page}_{n}"] = {"x": x, "y": y, "w": NOTE_W, "maxH": max(tallest, 844), "fill": "gray", "page": page, "text": text}
        y_by_page[page] = y + tallest + ROW_GAP + TITLE_ABOVE
        n_by_page[page] = n + 1

    side = m["width"] + 120
    title = inventory["title"]
    notes["s_map_howto"] = {"x": side, "y": 0, "w": 520, "maxH": 1100, "fill": "blue", "page": map_page, "text": inventory.get("howTo") or (
        "HOW TO USE THIS MAP\n\n"
        f"Every screen in the current app, built from main at {inventory['syncedAt']}"
        + (f" ({inventory['builtOn']})" if inventory.get("builtOn") else "") + ". Each board's sync point is its syncedAt in "
        "the repo's App Map boards.json.\n\n"
        "• Click a card on the map, or use the page list, to open a screen.\n"
        "• Press Play on any screen to click through the app: its buttons and back controls are linked.\n"
        "• Each page has one note per row: where each screen opens from, what its controls lead to, and the states not drawn.\n"
        "• Boards are editable HTML recreations of the shipped screens, checked against the snapshot tests.\n"
        + ("• The Design kit page shows the design system as it ships: tokens, type, app chrome and components.\n"
           if any(b["presentation"] == "kit" for b in all_boards) else "") +
        "• Keep it current with the update-app-map skill after a screen change lands on main.")}
    notes["s_map_design"] = {"x": side, "y": 1180, "w": 520, "maxH": 600, "fill": "orange", "page": map_page, "text": inventory.get("designWork") or (
        "DESIGN WORK (separate canvases; the App Map README is the registry)\n\nNone yet.\n\n"
        "New design work gets its own Design canvas; screens it would replace get a \"Redesign in draft\" pill on the map.")}

    pages = [{"id": map_page, "name": m.get("pageName", "Overview")}] + [{"id": i, "name": page_names[i]} for i in page_ids if i != map_page]
    canvas = {"v": 3, "createdOnFiles": {"v": 1, "at": now}, "title": title, "launch": {"view": "canvas", "page": map_page},
              "pages": pages, "boards": boards, "order": order, "notes": notes, "designSystems": []}

    manifest = {"_about": ABOUT, "canvas": inventory.get("canvas", ""), "scannedThrough": inventory["syncedAt"], "publishPending": [],
                "boards": {}}
    for board in all_boards:
        entry = {"title": board["title"], "page": page_names[board["page"]], "pageId": board["page"], "row": board["row"],
                 "presentation": board["presentation"], "height": sizes[board["name"]][1], "sources": board["sources"],
                 "snapshot": board.get("snapshot"), "snapshots": board.get("snapshots", []),
                 "snapshotIsMock": bool(board.get("snapshotIsMock")), "undrawn": board.get("undrawn", []),
                 "syncedAt": board.get("syncedAt") or inventory["syncedAt"]}
        for key in ("tall", "dark"):
            if board.get(key):
                entry[key] = True
        if board.get("light"):
            entry["light"] = board["light"]
        manifest["boards"][board["name"]] = entry
    return canvas, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("inventory")
    parser.add_argument("--project", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--force", action="store_true", help="overwrite an existing canvas.json")
    parser.add_argument("--now", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    args = parser.parse_args()
    target = os.path.join(args.project, "canvas.json")
    if os.path.exists(target) and not args.force:
        print(f"refusing to overwrite {target}: edit the live index in place (or pass --force for a first build)")
        return 1
    inventory = json.load(open(args.inventory, encoding="utf-8"))
    try:
        canvas, manifest = build(inventory, args.project, args.now)
    except (KeyError, ValueError, FileNotFoundError) as error:
        print(f"inventory: {error}")
        return 1
    with open(target, "w", encoding="utf-8") as f:
        json.dump(canvas, f, indent=1, ensure_ascii=False)
        f.write("\n")
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {target} ({len(canvas['boards'])} boards, {len(canvas['notes'])} notes, {len(canvas['pages'])} pages) and {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
