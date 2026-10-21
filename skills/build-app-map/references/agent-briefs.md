# Agent briefs

Briefs for the agents an App Map build can use. Fill the placeholders. Keep the tool limits as written: background agents cannot answer permission prompts, so a browser, computer-use or connector call stalls the run. The Artifact tool's `read` action runs in a background agent without stalling (a single `path`, or a `paths` list with `out_dir`), so reading the live canvas may be delegated. Publishing stays with the main session, and so does the plain read a publish to an existing canvas needs (SKILL.md step 11). Keep agents inside this session; a background workflow does not survive the session ending.

## Environment notes for every brief

```text
Environment: macOS, Python 3.9 or newer with Pillow; no fontTools. In Python 3.9 an f-string expression cannot contain a backslash: build such strings first. macOS has no `timeout` command. Quote globs in zsh. Run the tools from <repo> as the working directory. Headless Chrome may not exit by itself; the tools in <root>/tools stop it for you.
```

## Area surveyor (inventory, read-only)

```text
You survey one area of the <App> app for its App Map: <area> (<entry points>).

Read only from the pinned export <root>/src (commit <commit>). Follow <skill-dir>/references/inventory.md. Trace every way into and out of each screen in this area: rows, toolbar buttons, sheets, covers, menus, alerts, swipes and root swaps. Look at the snapshots for this area on a contact sheet (python3 <root>/tools/contact_sheet.py).

Tools: file read and search, and the shell only for listing files, git log/show on <repo>, and the contact sheet script. No browser, simulator, computer-use, web or connector tools; the Artifact tool only to read. Write nothing outside <root>/survey/<area>/.

Return JSON: {"area": "<area>", "boards": [<inventory.json board entries: name, title, page, row, presentation, sources, snapshot, snapshots, undrawn, tall, dark, note>], "edges": [{"from": "<board>", "to": "<board>", "label": "<what moves you>", "kind": "push|sheet|cover|tab|state"}], "copy": {"<board>": "<the screen's copy in order, verbatim>"}, "sampleData": "<fixtures the snapshots use>", "uncertain": ["<what code and snapshots leave open>"]}
```

## Area builder (boards)

```text
You draw one area of the <App> App Map: <area>, boards <list of names>.

Read first: <root>/kit/APPMAP-KIT.md, <root>/kit/chrome.py, the calibration boards' draw functions in <root>/kit/boards/, and your area's entries in <root>/inventory.json. Read code only from <root>/src. Use chrome.py helpers for every shared element; when one is missing or wrong, draw it locally in your module and report it as a kit proposal instead of editing chrome.py.

Write only <root>/kit/boards/<area>.py, through its draft <root>/drafts/<area>.py. For each board: write its @c.draw function, build it (python3 <root>/kit/build_boards.py --manifest <root>/inventory.json --out <root>/project --only <Name>), render it (python3 <root>/tools/render.py <root>/project/<Name>.dc.html <root>/renders/<Name>.png --height <H>), compare it with its snapshot (python3 <root>/tools/compare.py …) and fix it until titles, rows and buttons sit within 2 px. Link every control that navigates. Then run python3 <root>/tools/lint.py --pending-ok <root>/project and fix every error.

Other agents build at the same time, and build_boards.py imports every module in <root>/kit/boards/, so a half-written module breaks every build. Make each change in the draft (copy your module there first when it exists), check it (python3 -m py_compile <root>/drafts/<area>.py), then move it into place (mv <root>/drafts/<area>.py <root>/kit/boards/<area>.py). When a build fails with an import error from another area's module, wait 10 seconds and retry.

Tools: file read/write/search, and the shell only for the draft, build, render, compare and lint commands above. No browser, simulator, computer-use, web, connector or git-write tools; the Artifact tool only to read. The main session publishes.

Reply in at most 15 lines: boards built with heights, boards without a snapshot and what you drew them from, kit proposals (helper, problem, fix), and anything uncertain.
```

## Fresh reviewer (one area, after the build)

```text
You review boards you did not draw: the <area> boards of the <App> App Map. Be skeptical: assume each board has at least one mismatch until you have looked.

For each board in <list>: render it, compare it with its snapshot side by side and as an overlay, and read its source at <root>/src. Check region by region: copy (verbatim against the string catalog), order of elements, sizes and spacing, colours, icons, which state is drawn, and that every navigating control links to the right board. Fix what is wrong in <root>/kit/boards/<area>.py through its draft, rebuild, re-render and re-check. Changes needed in chrome.py go in your reply, not the file.

Tools and the draft rule for module changes: as for the builder.

Reply in at most 15 lines: per board, fixed / fine / left open (with why), and kit proposals.
```
