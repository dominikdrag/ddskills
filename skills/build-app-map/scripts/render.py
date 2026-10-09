#!/usr/bin/env python3
"""Render an App Map board to PNG, or measure how much taller a board must be to show its whole scroll.

Usage:
  render.py <board.dc.html> <out.png> [--width W] [--height H] [--scale 2]
  render.py --measure <board.dc.html> [...]

Uses headless Google Chrome. The canvas runtime (support.js) exists only inside the canvas, so this shows the
static markup; App Map boards keep copy as literal markup, so they render fully. Fonts and uploaded images are
swapped for local files from config.json next to this script, so rendering needs no network:
  "fonts":  [{"family": "Figtree", "file": "<repo path to .ttf/.otf>", "weight": "300 900", "style": "normal"}]
             (replaces every fonts.googleapis.com <link>; leave empty when boards use system fonts)
  "assets": "<path to assets.json, relative to the mirror folder>"  ({"/_blob/<id>": "<repo path>"})
--measure prints `<file> <extra px>`: how far the element marked data-scroll overflows its parent at the
board's current height (0 = everything fits). Set CHROME to override the Chrome binary.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = os.environ.get("CHROME") or next(
    (p for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("google-chrome"),
                 shutil.which("chromium"), shutil.which("chrome")) if p and os.path.exists(p)), None)
MEASURE = ("<script>addEventListener('load',()=>{document.fonts.ready.then(()=>{const m=[...document.querySelectorAll('[data-scroll]')]"
           ".map(s=>Math.max(0,Math.ceil(s.offsetHeight-s.parentElement.clientHeight)));"
           "document.body.setAttribute('data-extra',String(Math.max(0,...m)))})})</script>")


def repo_root():
    out = subprocess.run(["git", "-C", HERE, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    return out.stdout.strip() or os.getcwd()


def local_page(path, config_path):
    """The board's source with web fonts and uploaded images pointed at local files."""
    src = open(path, encoding="utf-8").read()
    config = json.load(open(config_path, encoding="utf-8")) if os.path.exists(config_path) else {}
    repo = repo_root()
    fonts = config.get("fonts") or []
    if fonts:
        faces = "".join(
            f"@font-face{{font-family:'{f['family']}';font-style:{f.get('style', 'normal')};font-weight:{f.get('weight', '100 900')};"
            f"src:url('file://{os.path.join(repo, f['file'])}')}}" for f in fonts)
        src = re.sub(r"<link[^>]*fonts\.googleapis\.com[^>]*>", f"<style>{faces}</style>", src)
    assets = config.get("assets")
    if assets:
        assets_path = os.path.normpath(os.path.join(HERE, "..", assets))
        if os.path.exists(assets_path):
            for blob, file in json.load(open(assets_path, encoding="utf-8")).items():
                if blob.startswith("/_blob/"):
                    src = src.replace(blob, f"file://{os.path.join(repo, file)}")
    return src


def chrome(args, wait_for, stdout=subprocess.DEVNULL, timeout=30):
    """Run Chrome headless until wait_for() returns a value, then stop it (it may not exit by itself)."""
    if not CHROME:
        sys.exit("Google Chrome not found; set CHROME to its binary")
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files", *args],
                            stdout=stdout, stderr=subprocess.DEVNULL)
    result = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.25)
        result = wait_for()
        if result is not None:
            break
    proc.kill()
    proc.wait()
    return result


def render(path, out, width, height, scale, config_path):
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "page.html")
        open(page, "w", encoding="utf-8").write(local_page(path, config_path))
        if os.path.exists(out):
            os.remove(out)

        def done():
            if os.path.exists(out) and os.path.getsize(out) > 0:
                time.sleep(0.5)
                return True
            return None

        chrome([f"--user-data-dir={tmp}/profile", f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
                "--virtual-time-budget=3000", f"--screenshot={os.path.abspath(out)}", f"file://{page}"], done)
    if not (os.path.exists(out) and os.path.getsize(out) > 0):
        print(f"FAILED to render {path}", file=sys.stderr)
        return 1
    print(f"rendered {out}")
    return 0


def measure(path, config_path):
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "page.html")
        open(page, "w", encoding="utf-8").write(local_page(path, config_path).replace("</body>", MEASURE + "</body>"))
        dump = os.path.join(tmp, "dom.html")

        def done():
            text = open(dump, encoding="utf-8", errors="replace").read()
            return text if "</html>" in text else None

        with open(dump, "w") as sink:
            out = chrome([f"--user-data-dir={tmp}/profile", "--window-size=390,900", "--virtual-time-budget=3000", "--dump-dom",
                          f"file://{page}"], done, stdout=sink)
    m = re.search(r'data-extra="(\d+)"', out or "")
    return int(m.group(1)) if m else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--measure", action="store_true")
    parser.add_argument("--width", type=int, help="default: config board width, else 390")
    parser.add_argument("--height", type=int, help="default: config board height, else 844")
    parser.add_argument("--scale", type=float, default=2)
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    args = parser.parse_args()
    board = (json.load(open(args.config, encoding="utf-8")) if os.path.exists(args.config) else {}).get("board", {})
    args.width = args.width or board.get("width", 390)
    args.height = args.height or board.get("height", 844)
    if args.measure:
        for path in args.paths:
            print(path, measure(path, args.config))
        return 0
    if len(args.paths) != 2:
        parser.error("render needs <board.dc.html> <out.png>")
    return render(args.paths[0], args.paths[1], args.width, args.height, args.scale, args.config)


if __name__ == "__main__":
    sys.exit(main())
