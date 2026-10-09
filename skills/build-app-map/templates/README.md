# <App> App Map

The single canvas of every screen in the **current** <App> app: how each screen looks, and how people move between them. First built on <date> from `main` at `<commit>`. Each board's current sync point is its `syncedAt` in `tools/boards.json`.

- **Live canvas:** [<App> App Map](<canvas url>). It is private to its owner unless shared from its Share menu.
- **This folder** mirrors the canvas files: `project/canvas.json` (layout, pages, notes) and one `project/<Board>.dc.html` per current screen or Design kit board.
- **Design work stays in its own canvases**, so each design session owns its canvas and the App Map shows only what ships. This list is the registry; keep it and the Overview page's "Design work" note (`s_map_design`) in step:
  - None yet.

## What is on the canvas

| Page | What it shows |
| --- | --- |
| Overview | `Main.dc.html`: the navigation map. Every board is a card; click one to open it. <Legend: what each arrow style means.> |
| <Page> | <Its screens and states, in plain words.> |
| Design kit | The design system as it ships on `main`: tokens (light and dark values), type roles and app chrome, then one board per component group (<groups>). Reference boards, not screens. |

Each screen is an editable HTML recreation (`.dc.html`, the Design canvas format), rebuilt from the source and checked against the snapshot tests. Press Play on any screen to click through the app: <which controls are linked>. <What is not drawn: system alerts, purchase sheets, the keyboard, large text; the row notes list them.> Kit boards are drawn the same way from the design system code<, checked against the kit scenario snapshots>. The Design kit page is not design work: it changes only when a design lands on `main`.

## Keeping it current

Keep it current with the `update-app-map` skill (<paths of the skill copies>). <The routing file> routes to it whenever a change to a screen's look, copy or navigation lands on `main`, or a design canvas starts, is chosen, ships or is dropped.

Tools in `tools/` (settings in `tools/config.json`); the examples run from the repo root:

| Tool | Use |
| --- | --- |
| `check_drift.py` | Lists boards whose sources or snapshots changed since their `syncedAt`, shared UI changes, changed views or new snapshots no board lists, and files waiting to be published. `--to <branch>` previews a branch. |
| `boards.json` | One entry per board: `title`, `page`, `pageId`, `row`, `presentation`, `height`, `sources`, `snapshot`, `snapshots`, `snapshotIsMock`, `undrawn`, `syncedAt`, and `tall`, `dark` or `light` where they apply. `presentation` is a screen presentation, or `kit` for a Design kit board. A source ending in `/` covers a whole folder (an asset catalog). Top level: `canvas`, `scannedThrough`, `publishPending`. |
| `render.py` | Renders a board to PNG with headless Chrome at 2x, with the app's own font files and each uploaded image's repo file: `python3 <mirror>/tools/render.py <mirror>/project/<Board>.dc.html out.png --height 844`. `--measure` reports how much taller a board must be to show its whole scroll. |
| `compare.py` | Puts a render next to its snapshot with a 50% overlay: `python3 <mirror>/tools/compare.py out.png <snapshot.png> cmp.png`. |
| `lint.py` | Design canvas format rules and links: `python3 <mirror>/tools/lint.py <project folder>`. Always pass the whole folder. External URLs are expected warnings. |
| `check_layout.py` | Cross-checks `canvas.json`, `boards.json`, the board files and the map: entries, `order`, page ids, sizes against `$preview`, overlaps, manifest fields, and one non-overlapping map card per board. |
| `gen_map.py` + `map.json` | Rebuilds `Main.dc.html` from `map.json` into scratch (`--out`). It drops hand edits, so use it only for a full re-layout, never over the live map; mirror hand edits into `map.json`. |
| `build_index.py` | Wrote the first `canvas.json` and `boards.json`. Kept as the record of the layout rules; never rerun over the live index. |

Builder kit in `kit/`: rules, tokens and geometry in `APPMAP-KIT.md`; `chrome.py` holds the tokens and shared markup; `boards/<area>.py` draws each board; `build_boards.py` rebuilds any board into a scratch folder (`--only Name,Name`); `assets.json` maps uploaded images to repo files.

### Adding or removing a screen

1. **Board:** add an `@c.draw("<Area>-<Screen>")` function in the area's `kit/boards/<area>.py` (copy a neighbour), add its `boards.json` entry, build it into scratch with `--only`, then copy the file to `project/`. Mark it `tall` when it scrolls. Link every navigating control, and link the control on the parent board that opens it (publish the parent too), so Play can reach the new screen. Set `dark` when it gets a dark copy.
2. **`canvas.json`:** add `"<Board>.dc.html": {"x", "y", "w", "h", "title", "page", "is_interactive": true}` and its name in `order`.
   - **Within a row:** boards share a `y` and sit board width + 80 px apart. Move the row's `s_<page>_<n>` sticky note right by the same amount and widen the row title note `t_<page>_<n>` (`maxW`).
   - **Between rows:** the next row's title note starts 120 px below the tallest board in the row above, and its boards start 250 px below that title. If a row grows taller, move every lower row and its notes down.
   - **Notes:** add the board's paragraph to the row note, and update the parent board's paragraph.
3. **Map:** copy a neighbouring card `<a>` in `Main.dc.html`, add its arrow or rail segment, grow the band if needed, move everything below it down by the same amount, and render the map to check. Mirror it in `tools/map.json`.
4. **`boards.json`:** fill every field; `presentation` is one of `tab-root`, `push`, `sheet`, `full-screen-cover`, `menu`, `popover`, `alert-or-dialog`, `inline-state` or `system`; `syncedAt` is the `main` commit you built it from.
5. **Check:** run `lint.py` and `check_layout.py` on the whole project folder.

To remove a screen, delete it from all four places.

### Adding or removing a kit board

1. **Board:** add an `@c.draw("Kit-<Group>")` function in `kit/boards/kit.py` built from `chrome.py` (`c.kit_board`, `c.swatches`, `c.specimen` and the component helpers), showing every variant and state the code defines. Kit boards need no links. Draw a kit scenario 1:1 from its snapshot.
2. **`canvas.json`:** an entry on the Design kit page, its name in `order`, and its paragraph in the row note `s_<kit page>_<n>`. The row geometry is the same as on screen pages.
3. **Map:** a card in the Design kit band of `Main.dc.html` (no arrows), mirrored in the band's `grid` in `tools/map.json`.
4. **`boards.json`:** `presentation` `kit`, the design system `sources` it draws (a folder ends in `/`), its kit snapshot as `snapshot` (or `null`) and every variant in `snapshots`.

To remove a kit board, delete it from all four places.
