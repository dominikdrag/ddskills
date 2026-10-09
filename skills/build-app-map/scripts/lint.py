#!/usr/bin/env python3
"""Check App Map boards (.dc.html) against the Design canvas format rules and their links.

Usage: lint.py [--pending-ok] <file-or-dir> [...]

Pass the whole project folder: links are checked against sibling board files. Exit 1 when any ERROR is
found; WARN lines do not fail (external URLs such as Terms or Privacy are expected warnings).
--pending-ok reports links to boards that do not exist yet as WARN, while boards are still being built;
the final check runs without it.
"""
import os
import re
import sys
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SVG_SELF_OK = {"path", "circle", "rect", "line", "polyline", "polygon", "ellipse", "stop", "use"}
PROJECT_MARK = os.sep + "project" + os.sep
PENDING_OK = "--pending-ok" in sys.argv
FORBIDDEN = [("innerHTML", "innerHTML"), ("appendChild", "appendChild"), ("<iframe", "iframe"), ("<object", "object"),
             ("<embed", "embed"), ("data:image", "data: URI"), ("data:font", "data: URI"),
             ("addEventListener('keydown'", "key handler"), ('addEventListener("keydown"', "key handler")]


class Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()))

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID and tag not in SVG_SELF_OK and tag != "marker":
            self.errors.append(f"self-closed <{tag}/> at line {self.getpos()[0]}")

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"stray </{tag}> at line {self.getpos()[0]}")
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        names = [t for t, _ in self.stack]
        if tag in names:
            while self.stack and self.stack[-1][0] != tag:
                t, pos = self.stack.pop()
                self.errors.append(f"unclosed <{t}> opened at line {pos[0]}")
            self.stack.pop()
        else:
            self.errors.append(f"stray </{tag}> at line {self.getpos()[0]}")


def project_root(path):
    i = path.rfind(PROJECT_MARK)
    return path[: i + len(PROJECT_MARK)] if i >= 0 else os.path.dirname(path) + os.sep


def lint(path):
    errs, warns = [], []
    src = open(path, encoding="utf-8").read()
    if '<script src="./support.js"></script>' not in src:
        errs.append('missing exact <script src="./support.js"></script> head line')
    if "<x-dc>" not in src or "</x-dc>" not in src:
        errs.append("missing <x-dc> wrapper")
    if "<helmet>" not in src:
        warns.append("no <helmet>")
    m = re.search(r"<script type=\"text/x-dc\" data-dc-script data-props='([^']*)'>", src)
    if not m:
        errs.append("missing data-dc-script block with single-quoted data-props")
    else:
        if "class Component extends DCLogic" not in src[m.end():]:
            errs.append("logic block lacks 'class Component extends DCLogic'")
        pv = re.search(r'"\$preview"\s*:\s*\{\s*"width"\s*:\s*(\d+)\s*,\s*"height"\s*:\s*(\d+)', m.group(1))
        if not pv:
            errs.append("data-props has no $preview width/height")
        else:
            body = src[src.find("</helmet>") + 9:] if "</helmet>" in src else src[src.find("<x-dc>") + 6:]
            root = re.search(r"<div\b[^>]*?\bstyle=\"([^\"]*)\"", body)
            if root:
                rw = re.search(r"(?:^|;)\s*width:\s*(\d+)px", root.group(1))
                rh = re.search(r"(?:^|;)\s*height:\s*(\d+)px", root.group(1))
                if rw and rh:
                    if (rw.group(1), rh.group(1)) != pv.groups():
                        errs.append(f"root {rw.group(1)}x{rh.group(1)} != $preview {pv.group(1)}x{pv.group(2)}")
                else:
                    warns.append("root div has no fixed px width/height")
    for bad, why in FORBIDDEN:
        if bad in src:
            errs.append(f"forbidden: {why}")
    for url in re.findall(r"(?:src|href)=\"(https?://[^\"]+)\"", src):
        if url.startswith("https://fonts.googleapis.com/css2?"):
            continue
        warns.append(f"external url {url}")
    if "fonts.googleapis.com" in src and not re.search(r"<helmet>\s*<link rel=\"stylesheet\" href=\"https://fonts\.googleapis\.com/css2\?", src):
        errs.append("the Google Fonts link must be the first line inside <helmet>")
    holes = re.findall(r"\{\{[^}]*\}\}", src)
    if holes:
        warns.append(f"{len(holes)} {{{{holes}}}} (App Map copy stays literal markup): {sorted(set(holes))[:5]}")
    if re.search("[\U0001F300-\U0001FAFF☀-➿]", src):
        warns.append("possible emoji / dingbat characters")
    root = project_root(os.path.abspath(path))
    here = os.path.dirname(os.path.abspath(path))
    for href in re.findall(r"href=\"([^\"#][^\"]*\.dc\.html)\"", src):
        target = os.path.join(root, href[1:]) if href.startswith("/") else os.path.join(here, href)
        if not os.path.exists(target):
            (warns if PENDING_OK else errs).append(f"broken link -> {href}")
    for name in re.findall(r"<dc-import name=\"([^\"]+)\"", src):
        if not os.path.exists(os.path.join(here, name + ".dc.html")):
            errs.append(f"dc-import of missing {name}.dc.html")
    if re.search(r"<a [^>]*>(?:(?!</a>).)*<button", src, re.DOTALL):
        errs.append("<button> inside <a> (swallows the click)")
    b = Balance()
    try:
        b.feed(src[src.find("<x-dc>"): src.rfind("</x-dc>") + 7])
        b.close()
    except Exception as e:
        errs.append(f"parse error {e}")
    errs += b.errors[:8]
    errs += [f"unclosed <{t}> opened at line {p[0]}" for t, p in b.stack[:5]]
    return errs, warns


def main():
    files = []
    for arg in [a for a in sys.argv[1:] if a != "--pending-ok"]:
        if os.path.isdir(arg):
            for d, _, fs in os.walk(arg):
                files += [os.path.join(d, f) for f in fs if f.endswith(".dc.html")]
        elif os.path.isfile(arg):
            files.append(arg)
        else:
            print(f"ERROR not found: {arg}")
    bad = 0
    for f in sorted(files):
        errs, warns = lint(f)
        for e in errs:
            print(f"ERROR {os.path.basename(f)}: {e}")
        for w in warns:
            print(f"WARN  {os.path.basename(f)}: {w}")
        bad += bool(errs)
    print(f"{len(files)} files, {bad} with errors")
    if not files:
        print("ERROR no .dc.html files found; pass the project folder")
    sys.exit(1 if bad or not files else 0)


if __name__ == "__main__":
    main()
