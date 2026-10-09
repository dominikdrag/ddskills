# <App> App Map kit

Rules for recreating every current <App> screen as a `.dc.html` board on the [<App> App Map](<canvas url>). The goal is to match the **real app on `main`** (<UI framework>, <design system name>, <appearances drawn>), not to propose anything new.

- `chrome.py`: tokens and the shared markup helpers. Call `use("light")` or `use("dark")` first; every helper reads the active palette.
- `build_boards.py`: builds any board into a folder: `python3 kit/build_boards.py --out <scratch> --only <Name>`. Draw functions live in `boards/<area>.py`.
- `icons.py` / `ICONS.md`: the stand-ins for the app's icons as inline SVG (when the app uses a symbol set).
- `assets.json`: each uploaded image's `/_blob/<id>` and the repo file it came from.
- `../project/<Reference board>.dc.html`: the reference board. Copy its structure.

Where code and a snapshot disagree, **code wins for structure, numbers and copy; the snapshot wins for the look and positions**. <Which snapshots are older than the code, and where the snapshots live, with their pixel size and scale.>

## 1. File format

- Keep `<script src="./support.js"></script>` exactly. Everything visible goes inside `<x-dc>`; inline `style="…"` only, apart from the helmet (`chrome.page()` writes it).
- Root: `width: <W>px; height: <H>px; position: relative; overflow: hidden` on the screen ground; `$preview` is the same size. A screen that scrolls uses a taller root that shows the whole scroll (`tall`); pinned actions and the tab bar sit at the bottom of the tall root, as if scrolled to the end.
- Close every element, quote attributes; no `innerHTML`, iframes, scripts that build UI, emoji, `data:` URIs or global key handlers. Real `<button>`, `<a href>`, `<input>` with `<label>`; `aria-label` on icon-only controls.
- **Links:** every control that navigates is an `<a href="<Board>.dc.html">` styled as the control. Link to the board that shows the destination; when only another state of it is drawn, link to that. Close and Back link to the board underneath. Controls that open a web page link to the real URL. Dark boards link to the other dark boards.
- No fake status bar, Dynamic Island, keyboard or home indicator: leave the top <status height> and bottom <home height> points empty.
- Copy is literal markup: no `{{holes}}` and no `data-props` beyond `$preview`.

## 2. Tokens

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| <Asset catalog name> | `#……` | `#……` | <where it appears> |

<Opacity rules, disabled states, scrims and system dims.>

## 3. Type

- <Family> (<role>): <token → size/weight list from the typography code>.
- Line boxes: <how the platform's line height maps to CSS, e.g. `line-height: normal` from the font's hhea metrics; how `.lineSpacing` maps>.
- Boards are drawn at the default text size <name it>; larger sizes are not drawn.

## 4. Geometry (<W> × <H>)

| Element | Position |
| --- | --- |
| Status area | 0–<status height>, empty |
| <Navigation bar / header> | <y range, paddings, control sizes> |
| <Content margins> | <values> |
| <Tab bar / pinned actions> | <values> |
| System sheet | top <y>, top radius <r>; the parent dims underneath |

Measure positions from the snapshots at their scale (divide pixels by it). `tools/compare.py` overlays a render on its snapshot; aim for ±2 px on titles, rows and buttons.

## 5. Components (`chrome.py`)

- <helper(signature)>: <the app component it draws>.

## 6. Data and copy

<The fixtures every board shares: names, dates, counts, prices, the fictional "now". Copy comes from the String Catalog / localisation files.>

## 7. Snapshot traps

<What the snapshot audit found, so builders do not rediscover it: text size the suite renders at, capture artefacts not to copy (black tab bars, missing glass, white glyphs), offsets between snapshot and device (sheet y), scenarios hosted without their real chrome, snapshots older than the code.>

## 8. Design kit boards

- One board per group on the Design kit page: Tokens (`c.swatches`), Type (`c.specimen`), <app-specific foundations>, App chrome, then <component groups>. Frame each with `c.kit_board(title, body, caption)`.
- Draw components with the same `chrome.py` helpers the screens use, so a fix reaches both. Show every variant and state the code defines, each labelled with its name (style, size, state).
- Where a kit scenario exists, draw it 1:1 from its snapshot: same order, same sample data. Otherwise lay variants out top to bottom in the code's order.
- Kit boards need no links. They are `tall` when their content passes one screen.

## 9. Checking a board

1. `python3 tools/render.py project/<Board>.dc.html <scratch>/<Board>.png --height <H>`
2. `python3 tools/compare.py <scratch>/<Board>.png <snapshot.png> <scratch>/cmp-<Board>.png`, then look at the comparison image.
3. `python3 tools/lint.py project` must report no errors (external URL warnings are expected).

## 10. Not drawn

<System alerts and permission prompts, purchase sheets, the keyboard, larger text sizes, other devices, and same-layout variants the row notes name.>
