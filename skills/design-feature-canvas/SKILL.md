---
name: design-feature-canvas
description: "Turn a list of proposed features for an existing app into a Claude Design feature canvas: phone artboards grouped by page, one row per feature, verdict notes and a linked overview. Use when the user wants mockups or design propositions for feature ideas, a shortlist, a roadmap or a paid tier in Claude Design; not for building screens in code or tweaking one existing design."
---

# Design Feature Canvas

A **feature canvas** shows proposed features of one existing app on a single Claude Design canvas: one page per group, one row of phone artboards per feature, a verdict sticky at the end of each row, and an overview artboard that links to every row. The app's shipped look is the design system; the content comes from an agreed feature list.

The canvas is the deliverable. Draw artboards directly in the Design type's `.dc.html` format; intermediate HTML mockups only double the work.

Resolve this skill's installed directory as `<skill-dir>` for the helper commands. Work in one folder, `<root>`, in the scratchpad or an ignored directory: `<root>/_guide/` holds `tokens.md`, `contract.md`, the skeletons and copies of the type's reference pages for agents; `<root>/project/` holds the artboards and `canvas.json`, the only files published; `<root>/rows.json` collects the rows.

## Steps

1. **Pin the feature list.** For each feature: what the user gets, a status (Lead / Next / Later / Bet / Frame, or the user's own scale), the evidence or score behind it, and a build size. Group features into 2–5 pages and give each a one-letter code. Done when every feature has a page, code and status, and anything deliberately not designed is listed for the overview.

2. **Collect the app's look from source.** Read the app's color assets or tokens, typography helpers and bundled fonts, and view 4–8 real screenshots (snapshot tests, simulator captures, store screenshots) of the screens the features touch. Write `tokens.md`: colors with roles, which font is used where, radii, and component sizes. Load fonts with a Google Fonts `css2` link when the family is there; otherwise upload the font files as canvas assets. Done when every color and size an artboard needs has a source value.

3. **Write the contract** from [references/contract.md](references/contract.md): the shared story, the anatomy of screens several features touch, system-surface rules, glossary terms and, for paid features, tier behaviour. Done when two agents drawing the same shared screen would draw it identically.

4. **Create the canvas and read its rules.** Run the Artifact quickstart with intent `design`, create the canvas from the returned Design `type_url` with the user's title, then read the type instructions it returns and its `artifact-type/reference/format.md` and `craft.md`, saving copies in `<root>/_guide/`. They are the authority on file format, publishing and verification; this skill adds only the process. List the user's Design System artifacts; when one belongs to this app, install and use it in place of `tokens.md`.

5. **Build two skeleton artboards**: the app's most shared screen (navigation, header, section header, rows, tab bar) and one system surface (lock screen notification or Home Screen). Use inline styles, stroke SVG icons and real controls, and leave the status-bar area empty. Run `python3 <skill-dir>/scripts/lint_artboards.py <files>`. Done when both pass and match the screenshots side by side.

6. **Fix the artboard list.** Give each feature 5–8 artboards: entry point, main flow, add or edit, one empty or edge state, a notification or system surface where the feature has one, and for paid features at least one Free and one Lapsed state. Name files `<Feature>-<Screen>.dc.html` and title them `<Code><NN> · <screen>`. Done when every feature's main flow is covered from entry to result.

7. **Draw in parallel.** Brief one agent per feature with [references/agent-brief.md](references/agent-brief.md). Each writes only its own file prefix, lints, and returns its row for `rows.json`. The coordinator alone creates, publishes and edits the index.

8. **Review across features.** One reviewer reads every artboard against the contract and lists concrete fixes per file; route each fix to its owner or apply it, then re-lint. Done when no contract breach remains and every file passes lint.

9. **Write the overview and the index.** Write `Main.dc.html` at 1280 px wide: the canvas purpose (proposals, not an approved plan), one card per page with a link per feature to its first artboard and its size or score, the shared rules, and the "not designed on purpose" list. Then run `python3 <skill-dir>/scripts/build_canvas.py rows.json <root>/project` to write `canvas.json` with the row layout, title notes and verdict stickies. Done when the script reports every artboard listed and every link resolved.

10. **Publish and report.** Publish `canvas.json` with `Main.dc.html` first, then every other artboard in one call. The lint is the check: render or read the canvas back only when the user asks. Report the link, pages, artboard count, anything left undrawn, and that the canvas stays private until the user shares it.

## Revising

Follow the type's revising rules. Edit only the artboards the request names, re-run the lint on them, and rebuild `canvas.json` only when artboards, notes, pages or sizes change; `build_canvas.py --existing <root>/project/canvas.json` keeps the index's other keys.

## Row file and layout

`rows.json` holds the canvas title, the overview artboard and, per page, its rows; the schema and layout constants live in `scripts/build_canvas.py`. Layout: 390 px artboards 80 px apart, a title note 250 px above each row, the verdict sticky after the last artboard, 380 px between a row's tallest artboard and the next row.
