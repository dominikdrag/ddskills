---
name: update-app-map
description: Keeps the <App> App Map canvas (every shipped screen<, its dark copies>, the shipped design kit and the navigation map) in sync with main. Use when a change to a screen's look, copy or navigation, or to the design system, lands on main (a commit or a merge), when check_drift.py reports stale boards, or when a design canvas for a screen starts, is chosen, ships or is dropped.
---

# Update the App Map

The [App Map](<canvas url>) shows what ships on `main`: one `.dc.html` board per screen<, `Dark-*` copies of the main screens>, the Design kit page (the design system as shipped) and the navigation map `Main.dc.html`. Repo mirror: `<mirror>/` (paths below are relative to it). Its README has the page list, the design canvas list and the new-screen recipe; `kit/APPMAP-KIT.md` has the drawing rules. Design work never goes into the App Map; it lives in its own canvases. The Design kit page is not design work: it documents the design system as committed on `main` and is synced like any screen.

## When

- A change to a screen's look, copy or navigation, or to the design system, is on `main`: update the map right after it lands. Read sources and snapshots as committed on `main` (`git show main:<path>`, or a clean worktree at `main`), never from a working tree: other sessions keep uncommitted work there.
- `publishPending` in `tools/boards.json` is not empty: publish those first (see "Without the Artifact tool").
- No visible change: run step 1. If nothing is listed, you are done.
- A design canvas starts, is chosen, ships or is dropped: see "Design canvases".

## Update after a code change

1. **Find stale boards.** `python3 tools/check_drift.py` (add `--to <branch>` to preview a branch). It lists boards whose own sources or snapshots changed since their `syncedAt`, shared UI changes, changed views or snapshots no board lists, and files waiting to be published. A light board lists its dark snapshots too, so a dark-only change flags the light board: check its `Dark-*` copy as well. A design system change flags the kit boards that draw it, and names the screens that use it under shared UI. A new design system file is usually a new component: add it to the matching kit board, or a new one (README "Adding or removing a kit board"), and to its `sources`.
2. **Workspace.** Read the whole live canvas into `<scratch>/app-map/`. First `read` `project/canvas.json` from the canvas `url`. Then `read` with `paths` = every `project/…` file in its `boards`, and `out_dir` = `<scratch>/app-map`, so files land in `<scratch>/app-map/project/`. People edit the canvas by hand, so only the live files are current; the editor also rewrites files slightly (closes `<path>` tags, reformats JSON), so compare content, not bytes. If the live files differ from the repo mirror, someone skipped a mirror: copy them into `project/` along with your change.
3. **Rebuild each listed board** from the code on `main` (as committed), following `kit/APPMAP-KIT.md`.
   - Update its draw function in `kit/boards/<area>.py` (or a shared helper in `kit/chrome.py`), build it into scratch with `python3 kit/build_boards.py --out <scratch>/build --only <Name>[,Dark-<Name>]`, and compare the result with the live file. If the live file has hand edits you should keep, carry your change into the live file instead of replacing it.
   - Keep its file name, drawn state and sample data.
   - Code wins for structure, numbers and copy. The board's `snapshot` in `tools/boards.json` guides the look (render and compare with `tools/compare.py`), unless `snapshotIsMock` is true: then use it only for shared styling. Never copy snapshot capture artefacts the kit lists.
   - If the height changes, update the root `height`, `$preview`, the board's `h` in `canvas.json` and its `height` in `boards.json`. Move any board or note below it that would overlap.
   - If what is drawn or not drawn changes, update the board's paragraph in its row note (`s_<page>_<n>` in `canvas.json`).
4. **New or removed screen:** follow the README recipe. It covers the draw function and file, `canvas.json` entry and `order`, row geometry, the map card, `boards.json` and `tools/map.json`. A file that check_drift lists only because it is a state you do not draw goes into that board's `undrawn` list instead.
5. **Navigation changed?** This means a new or removed route, pushed step, sheet, cover, menu, tab or root swap, or an action that leads somewhere new. If so, fix the `href`s on the affected boards and edit the live `Main.dc.html` in place:
   - Cards are absolutely positioned `<a>` elements; copy a neighbour.
   - Every straight arrow or rail segment is its own small `<svg>`. Copy the styles from an existing one.
   - Never write `tools/gen_map.py` output over the live map. Run it only into scratch, for a full re-layout; mirror hand edits into `tools/map.json`.
6. **Check.**
   - Render: `python3 tools/render.py <board> <out.png> --height <height>`, then `python3 tools/compare.py <out.png> <snapshot> <cmp.png>` and look at it.
   - `python3 tools/lint.py <scratch>/app-map/project` and `python3 tools/check_layout.py <scratch>/app-map/project` must both report 0 errors.
7. **Publish only what changed.** Use the Artifact tool:
   - `url` = the canvas, `root` = `<scratch>/app-map`.
   - `file_path` = one changed file's absolute path; `files` = the others, keyed `project/<File>`.
   - Every published path starts with `project/`. A path without it lands outside the map.
   - Include `project/canvas.json` only when the layout or any note text changed, read again right before the call.
   - A new or changed image is a new asset upload (`asset: true`): put its `/_blob/` url in the boards and in `kit/assets.json`.
   - If refused because someone published meanwhile: re-read the files it names, redo your edits on them, and publish again.
8. **Mirror and record.** Copy the published files into `project/`. In `tools/boards.json`, for each rebuilt or checked board, set `sources`, `snapshot`, `snapshots`, `height` and `syncedAt`, the `main` commit you rebuilt from. Once the shared-UI and "no board lists" items are handled, set `scannedThrough` to that commit. Commit as `docs(designs): sync App Map with <change>` after the code commit, so `syncedAt` can name it. Commit only when authorized; otherwise leave the changes uncommitted and say so.

**Without the Artifact tool** (another agent host): you cannot read or publish the live canvas.
- Do steps 1 and 3–6 on the repo copy, then commit it when authorized.
- For every changed file, including `project/canvas.json` and `project/Main.dc.html`, add `{"file": "project/<File>", "builtFrom": "<main commit>"}` to `publishPending`. Leave `syncedAt` unchanged.
- Say "App Map publish pending" in the handoff.

A Claude session publishes pending files before any other update:
- Do step 2.
- Re-apply each pending file's repo change (`git diff` since before it was pending) on top of the live copy, then run step 6.
- Publish.
- Set the boards' `syncedAt` to their `builtFrom`, and clear `publishPending`.

## Design canvases

- New design work gets its own Design canvas, never pages in the App Map.
- **Started:** register it in two places, both read live:
  - the README "Design work" list;
  - the Overview note `s_map_design` in `canvas.json`.

  Give the name, link, status and the screens it would replace. Then put a small "Redesign in draft" pill in the corner of those cards in `Main.dc.html` (so the cards keep their size), and set `"pill"` on those cards in `tools/map.json`.
- **Chosen:** update its status line.
- **Shipped:** rebuild the boards as above, remove the pills, and update both lists.
- **Dropped:** remove the pills and the lines.

## Rules

- Never regenerate `canvas.json` or `Main.dc.html` over the live version; `tools/build_index.py` only wrote the first index. Never publish files you did not change.
- Boards document what ships. Do not redesign while syncing. The Design kit page changes only when a design lands on `main`.
- Keep a `Dark-*` copy in step with its light board in the same update.
- <What is not drawn; the row notes list it.>
