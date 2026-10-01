# Feature agent brief

Send each feature agent this brief with the placeholders filled. Keep the tool limits as written: background agents cannot answer permission prompts, so a browser, computer-use or connector call stalls the whole run.

```text
You draw one feature of the "<canvas title>" Claude Design canvas: <feature name>, code <C>.

Read first: <root>/_guide/tokens.md, <root>/_guide/contract.md, the two skeleton artboards in <root>/_guide/, and the type's format rules at <root>/_guide/format.md. Copy the skeletons' markup patterns; reproduce the contract's shared screens exactly.

Feature: <what the user gets, status, decisions already made, what stays free>.
Lane: draw the shipped app plus only this feature's elements from the contract's ownership list. Where another feature would add to a shared screen, draw the shipped version; name any extra sources in your sticky.
Screens (file → canvas title → content and state):
- <root>/project/<Feature>-<Screen>.dc.html → "<C>01 · <screen>" → <what it shows; tier; key copy>
- …

Artboard rules: root is width 390px and height ≥ 844px (taller when the screen scrolls; the tab bar sits at the bottom of that height), with the same size in data-props $preview. Inline styles on every element; flex or grid with gap. Leave the top 54px empty: no fake status bar. Stroke SVG icons only; no emoji, no data: URIs, no HTML comments, no script-built UI. Real <button>, <a href> and <input> with <label>; aria-label on icon-only buttons. Light appearance unless told otherwise. You may link your own artboards for the obvious flow with <a href="<Feature>-<Other>.dc.html"> styled as the control.

Check: python3 <skill-dir>/scripts/lint_artboards.py <root>/project/<Feature>-*.dc.html, and fix until every file passes.

Tools: file read/write/search, and the shell only for the lint and for listing files. No browser, computer-use, web, connector or Artifact tools; do not publish.

Return JSON: {"key": "<feature>", "title": "<row title>", "sticky": "<50–90 word verdict: status, score and size, what Free and Lapsed users see, the key design decision>", "artboards": [{"file": "<name>.dc.html", "title": "<canvas title>", "height": <H>, "links": <true|false>}], "notes": "<anything not reproduced and why>"}
```

Merge the returned rows into `rows.json` under their page, in the feature order from step 1.
