#!/usr/bin/env python3
"""Static checks for Claude Design .dc.html artboards.

Usage: lint_artboards.py FILE [FILE ...]

Errors fail the run (exit 1); warnings are printed but pass. The checks cover the
format rules that fail silently on a canvas: the exact support.js line, a fixed root
size equal to data-props $preview, the logic class, balanced tags, and content the
format forbids (emoji, data: URIs, HTML comments, script-built UI, iframes).
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr",
    "path", "circle", "rect", "line", "polyline", "polygon", "ellipse", "stop", "use",
}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0000FE0F]")
SUPPORT_LINE = '<script src="./support.js"></script>'
PROPS = re.compile(r"<script type=\"text/x-dc\" data-dc-script data-props='([^']*)'>")
ROOT = re.compile(r"</helmet>\s*<div style=\"width: (\d+)px; height: (\d+)px;")
HOLE = re.compile(r"\{\{\s*([^}]*)\}\}")
FORBIDDEN = ("<iframe", "<object", "<embed", "innerHTML", "appendChild")


class Balance(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: List[Tuple[str, int]] = []
        self.errors: List[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in VOID:
            return
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
            return
        open_tag = self.stack[-1][0] if self.stack else "nothing"
        self.errors.append(f"line {self.getpos()[0]}: </{tag}> does not close <{open_tag}>")
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return


def preview_size(src: str) -> Tuple[int, int] | None:
    match = PROPS.search(src)
    if not match:
        return None
    props = json.loads(match.group(1).replace("&amp;", "&").replace("&#39;", "'"))
    preview = props.get("$preview", {})
    return int(preview.get("width", 0)), int(preview.get("height", 0))


def lint(path: Path) -> Tuple[List[str], List[str]]:
    src = path.read_text(encoding="utf-8")
    errors: List[str] = []
    warnings: List[str] = []
    if SUPPORT_LINE not in src:
        errors.append(f"missing the exact head line {SUPPORT_LINE}")
    if "<x-dc>" not in src or "</x-dc>" not in src:
        errors.append("missing <x-dc> … </x-dc>")
    try:
        preview = preview_size(src)
    except (ValueError, TypeError) as error:
        errors.append(f"data-props is not valid JSON: {error}")
        preview = None
    if not PROPS.search(src):
        errors.append("missing <script type=\"text/x-dc\" data-dc-script data-props='…'> block")
    if "class Component extends DCLogic" not in src:
        errors.append("missing class Component extends DCLogic")
    root = ROOT.search(src)
    if not root:
        errors.append('the element right after </helmet> must start with style="width: Wpx; height: Hpx; …"')
    elif preview and (int(root.group(1)), int(root.group(2))) != preview:
        errors.append(f"root size {root.group(1)}x{root.group(2)} differs from $preview {preview[0]}x{preview[1]}")
    if "<!--" in src:
        errors.append("HTML comment found; remove it")
    if "data:" in re.sub(r"data-[a-z-]+=", "", src):
        errors.append("data: URI found; upload the asset or draw it inline")
    for token in FORBIDDEN:
        if token in src:
            errors.append(f"forbidden {token!r}")
    emoji = sorted(set(EMOJI.findall(src)))
    if emoji:
        errors.append(f"emoji found {emoji}; use stroke SVG icons")
    for hole in HOLE.finditer(src):
        if re.search(r"[+!()?:<>=]|\s-\s", hole.group(1)):
            errors.append(f"hole is an expression: {{{{{hole.group(1)}}}}}")
    body = src.split("<x-dc>", 1)[-1].split("</x-dc>", 1)[0]
    parser = Balance()
    parser.feed(body)
    parser.close()
    errors.extend(parser.errors[:5])
    if parser.stack:
        errors.append(f"unclosed elements: {[tag for tag, _ in parser.stack][-5:]}")
    if re.search(r">\s*9:41\s*<", body):
        warnings.append("9:41 text found; draw no fake status bar (a lock-screen clock is fine)")
    return errors, warnings


def main(argv: List[str]) -> int:
    if not argv:
        print(__doc__.strip().splitlines()[2])
        return 2
    failed = 0
    for name in argv:
        errors, warnings = lint(Path(name))
        print(f"{'FAIL' if errors else 'ok  '} {name}")
        for message in errors:
            print(f"   error: {message}")
        for message in warnings:
            print(f"   warning: {message}")
        failed += bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
