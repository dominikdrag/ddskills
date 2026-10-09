# Inventory: every screen, state and route

The inventory decides what the App Map shows. Read everything from the pinned export (`<root>/src`), never from a working tree that other sessions may be changing.

## Where screens come from

- **Navigation code.** Start at the app's root view and follow every way in and out. For SwiftUI: the `App` and root views, tab views and their tab enum, route or destination enums, `NavigationStack` paths and `.navigationDestination`, `NavigationLink`, `.sheet`, `.fullScreenCover`, `.popover`, `.confirmationDialog`, `.alert`, `Menu`, swipe actions, root swaps on state (onboarding → main, locked → unlocked), and the reducers, coordinators or view models that drive them. For other stacks, the router configuration and screen registry play the same part.
- **Snapshot tests.** List every reference image. Look at all of them on contact sheets (`scripts/contact_sheet.py`), filtering out variants the map does not draw (larger text, small phone, and dark unless dark copies are drawn). Each base snapshot is either a board's drawn state, another state of a board (`snapshots`), or a known state you do not draw (`undrawn`).
- **Real captures** settle what snapshots cannot: store screenshots, fastlane captures, marketing captures. When a state has no snapshot and its look is uncertain, capture it on a simulator (with a simulator-claiming skill such as `manage-apple-simulators` when installed) or draw it from code and say so in its note.
- **Copy and sample data.** Copy from the string catalogs or localisation files; sample data from the snapshot scenarios or preview fixtures, so boards and snapshots show the same people, items and numbers. Version and build numbers are sample data too.

## What becomes a board

- One board per screen, plus one per visually distinct state: empty, first use, loading, filled, error, limit reached, menu open, sheet up, purchase pending.
- A state that only changes a sentence or a status line shares its screen's board: name it in the row note.
- System UI the app does not draw (permission prompts, alerts, purchase sheets, the keyboard, share sheets) is not a board: name it in the note of the board that triggers it.
- A screen taller than one phone screen is one `tall` board showing the whole scroll.
- Dark copies (`Dark-<Name>`) are for the main screens only, when the app ships a dark appearance; mark the light board `"dark": true`.

## Names, titles and presentation

- File names: `<Area>-<Screen>[-<State>]`, PascalCase segments, area prefix first (`Today-Main`, `People-List-Empty`, `Offer-Plans`). Merge duplicates the survey finds from two directions (a details screen reached from two tabs is one board).
- Titles: the screen's own heading in plain words, with the state in parentheses: "Did we hear you right?", "Plans (no products loaded)".
- `presentation`: `tab-root`, `push`, `sheet`, `full-screen-cover`, `menu`, `popover`, `alert-or-dialog`, `inline-state` or `system`.
- `sources`: every file that draws the board or decides its content (view, its subviews specific to it, view model, route). Shared design-system files go in config `shared`, not in each board.

## The Design kit page

The last page shows the app's design system as it ships on `main`: reference boards, not screens. It documents the code; a proposed design language stays on its own design canvas until it lands, and then these boards are rebuilt.

- **Foundations row:** `Kit-Tokens` (every colour token as a swatch with its name, role and value, light and dark side by side; spacing, radii and shadows when the code defines them), `Kit-Type` (every type role as a specimen line with font, size, weight and line height), app-specific foundations (for example person or category colours), and `Kit-Chrome` (navigation bar, tab bar, toolbars, sheets and menus as the app draws them).
- **Component rows:** one board per component group the design system defines, in the code's own grouping: buttons, controls (toggles, pickers, segmented controls, fields), status (chips, tags, badges, counts), feedback (toasts, banners, empty states), cards and rows, and the app's signature components. Each shows every variant and state the code has (sizes, disabled, pressed or selected), labelled with the component's name.
- **Sources:** the design-system files each board draws; a source ending in `/` covers a whole folder (an asset catalog). When the snapshot suite has a component gallery or kit scenarios, draw one board per scenario 1:1 from its snapshot and list it as the board's `snapshot`; otherwise draw from code, using the screen snapshots for the look.
- **Fields:** `"presentation": "kit"`, the kit page id, names `Kit-<Group>`. Kit boards need no links; they get a card each in a `grid` band at the bottom of `map.json`, with no arrows.
- **Scope:** draw what is shared. A component used by one screen only belongs on that screen's board.

## Pages, rows and notes

- 5–9 pages by area, in the order a person meets them; the Overview (the navigation map) is first, then the screen pages, the dark page when drawn, and the Design kit page last.
- One row per flow or screen family, in the order of the flow; at most 8 boards (`build_index.py` wraps longer rows).
- Each board's `note` starts with its title line, then 1–3 sentences: where it opens from, what its controls lead to, and the states or system UI not drawn.

## The navigation map (`map.json`)

- One band per area or flow. A band's columns are the main path, left to right; each arrow is labelled with what moves you there and styled by presentation (`push`, `sheet` for sheets and menus, `cover` for full-screen covers and root swaps, `tab`).
- Other states of a step hang off its rail with a short "when it shows" label.
- Every board gets exactly one card. A board reached from several places gets its card where its main path is, with "Also from: …" in its sub lines.

## Coverage check

Run `check_drift.py --coverage` against the pinned commit (the command is in the skill's step 2). Every view file and base snapshot must be claimed by some board's `sources`, `snapshot`, `snapshots` or `undrawn`, kit scenario snapshots included; shared design-system files are covered by config `shared`. Add what is left to the right board, or put a target that is not on the map (previews, a watch app, test support) in config `ignored`.

## Snapshot audit

Before the kit is written, check the snapshots once and record what you find in the kit's "Snapshot traps":

- the text size the suite renders at (it may differ from the device default);
- capture artefacts that are not the app (a black tab bar, missing glass or blur, white toolbar glyphs);
- offsets between a snapshot and the device (sheet content a few points lower);
- scenarios hosted without their real chrome (no back button or tab bar);
- snapshots older than the code: compare `git log -1 --format=%cs` of the image and of its view; where they disagree, code wins for copy and structure.
