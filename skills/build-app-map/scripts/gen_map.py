#!/usr/bin/env python3
"""Generate the App Map navigation map (Main.dc.html) from map.json.

Usage: gen_map.py <map.json> --out <scratch>/project/Main.dc.html

Use it for the first build and for a full re-layout only: it drops hand edits made on the canvas (moved
cards, extra pills), so read the live Main.dc.html first and carry those edits into map.json. For one new
screen or a changed arrow, edit the live Main.dc.html in place and mirror the change in map.json.
Prints the map's width and height; put them in canvas.json (the Main.dc.html entry) when they change.

map.json:
{
  "title": "<App> App Map",
  "subtitle": "Every screen in the current app on main. Click a card to open the screen; press Play on a screen to click through the app.",
  "fontLink": "https://fonts.googleapis.com/css2?family=...&display=swap",      // optional
  "font": "'Figtree', -apple-system, system-ui, sans-serif",                   // body text
  "titleFont": "'Cormorant Garamond', Georgia, serif",                        // optional, the map title
  "palette": {"ink": "#353C31", "muted": "#676C5D", "accent": "#89683B", "start": "#48563E", "line": "#A79F8E",
              "stateLine": "#C9C0AE", "paper": "#FAF5EA", "card": "#FFFDF8", "cardBorder": "#DDD5C4", "tab": "#48563E",
              "tints": ["#F3EEE2", "#EEF0E6"]},
  "bands": [
    {"title": "Launch and first use",
     "columns": [
       {"main": {"board": "Launch-Loading", "title": "Launch", "sub": ["Decides the first screen"]},
        "arrow": {"label": "first use", "kind": "push"},
        "states": [{"board": "Resume-Choosing", "when": "unfinished work", "title": "Resume prompt", "sub": []}]},
       {"ref": "Locked-Landing", "refText": "Go in peace is drawn under Launch. Its other state:",
        "states": [{"board": "Locked-Pending", "when": "purchase pending", "title": "Awaiting approval"}]}
     ]},
    {"title": "Dark appearance", "grid": [{"board": "Dark-Welcome", "title": "Welcome"}], "perRow": 4,
     "tint": "#2A352D", "titleColor": "#EFEADD"},
    {"title": "Design kit (shipped components, not screens)", "grid": [{"board": "Kit-Tokens", "title": "Tokens"}],
     "note": "Not screens: the design system as it ships. A card opens its board on the Design kit page."}
  ]
}

Each band is one flow, left to right: a column's main card is a step on the main path; `arrow` (null = none)
leads to the next column, labelled with what moves you; `states` hang off a dashed rail below the main card,
each labelled with when it shows. Arrow kinds: push (solid), sheet (dashed, also menus), cover (dotted,
full-screen covers and root swaps), tab (solid, tab colour). A column with `ref` shows only the states of a
board drawn in another band. A card may carry "pill": "Redesign in draft". `grid` bands hold plain cards
without arrows, with an optional `note` line above them: dark copies, and the Design kit boards. The first
card of each flow band gets the start border.
"""
import argparse
import html
import json
import sys

CW, SW, GAP, INDENT, M, BAND_PAD, TITLE_H = 300, 260, 120, 40, 64, 40, 44
DEFAULT = {"ink": "#1F2328", "muted": "#59636E", "accent": "#7A5C00", "start": "#1F6FEB", "line": "#8C959F", "stateLine": "#C2C8CF",
           "paper": "#F6F8FA", "card": "#FFFFFF", "cardBorder": "#D0D7DE", "tab": "#BF8700",
           "tints": ["#EEF1F4", "#F1EFEA", "#EDF2EE", "#F2EEF1", "#EEF0F4", "#F3F1EC", "#ECF0F0"]}
DASH = {"push": None, "sheet": "6 6", "cover": "2 4", "tab": None, "rail": "4 4"}
LEGEND = {"push": "Push: the next step, labelled with what moves you", "sheet": "Sheet or menu", "cover": "Full-screen cover or root swap",
          "tab": "Tab bar switch"}


def esc(s):
    return html.escape(s, quote=False)


class Map:
    def __init__(self, spec):
        self.spec = spec
        self.p = {**DEFAULT, **spec.get("palette", {})}
        self.kinds = set()

    def card_h(self, sub):
        return 48 + 15 * len(sub or [])

    def card(self, c, x, y, w, main=True, start=False):
        p = self.p
        sub = c.get("sub") or []
        h = self.card_h(sub)
        border = f"2px solid {p['start']}" if start else f"1px solid {p['cardBorder']}"
        lines = "".join(f'<span style="display: block; font-size: 11px; line-height: 15px; color: {p["muted"]}">{esc(s)}</span>' for s in sub)
        pill = ""
        if c.get("pill"):
            pill = (f'<span style="position: absolute; right: 8px; top: -9px; padding: 1px 7px; border-radius: 9px; background: {p["accent"]}; '
                    f'color: {p["card"]}; font-size: 10px; line-height: 16px; font-weight: 600">{esc(c["pill"])}</span>')
        return (f'<a href="{c["board"]}.dc.html" style="position: absolute; left: {x}px; top: {y}px; width: {w}px; height: {h}px; '
                f'box-sizing: border-box; padding: 10px 14px; border-radius: 10px; border: {border}; background: {p["card"]}; '
                f'box-shadow: 0 1px 2px rgba(0,0,0,0.06); color: {p["ink"]}; text-decoration: none; display: block">'
                f'<span style="display: block; font-size: {14 if main else 13}px; line-height: 18px; font-weight: 600">{esc(c.get("title") or c["board"])}</span>'
                f'<span style="display: block; font-size: 11px; line-height: 15px; color: {p["accent"]}">{c["board"]}</span>{lines}{pill}</a>')

    def hline(self, x1, x2, y, kind="push", label=None):
        p = self.p
        w = x2 - x1
        rail = kind == "rail"
        color = p["stateLine"] if rail else (p["tab"] if kind == "tab" else p["line"])
        dash = DASH.get(kind)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        head = "" if rail else f'<path d="M{w - 7} -4L{w} 0L{w - 7} 4" fill="none" stroke="{color}" stroke-width="1.5"></path>'
        out = (f'<svg width="{w}" height="12" viewBox="0 -6 {w} 12" aria-hidden="true" style="position: absolute; left: {x1}px; '
               f'top: {y - 6}px; overflow: visible"><path d="M0 0H{w}" stroke="{color}" stroke-width="1.5"{d}></path>{head}</svg>')
        if label:
            out += (f'<span style="position: absolute; left: {x1 + 6}px; top: {y - 34}px; width: {w - 12}px; font-size: 11px; '
                    f'line-height: 14px; color: {p["muted"]}; text-align: center">{esc(label)}</span>')
        return out

    def vline(self, x, y1, y2):
        return (f'<svg width="4" height="{y2 - y1}" viewBox="-2 0 4 {y2 - y1}" aria-hidden="true" style="position: absolute; '
                f'left: {x - 2}px; top: {y1}px"><path d="M0 0V{y2 - y1}" stroke="{self.p["stateLine"]}" stroke-width="1.5"></path></svg>')

    def states(self, states, x, sy, rail_from):
        parts, last_mid = [], None
        rail_x = x + 18
        for s in states:
            mid = sy + 24
            parts.append(self.hline(rail_x, x + INDENT, mid, kind="rail"))
            parts.append(self.card(s, x + INDENT, sy, SW, main=False))
            if s.get("when"):
                parts.append(f'<span style="position: absolute; left: {x + INDENT + SW + 10}px; top: {mid - 8}px; width: {GAP - 20}px; '
                             f'font-size: 11px; line-height: 14px; color: {self.p["muted"]}">{esc(s["when"])}</span>')
            last_mid = mid
            sy += self.card_h(s.get("sub")) + 20
        if last_mid is not None:
            parts.append(self.vline(rail_x, rail_from, last_mid))
        return parts, sy

    def flow_band(self, band, top):
        y0 = top + BAND_PAD + TITLE_H
        parts, bottom = [], y0
        cols = band["columns"]
        for ci, col in enumerate(cols):
            x = M + BAND_PAD + ci * (CW + GAP)
            if col.get("ref"):
                parts.append(f'<span style="position: absolute; left: {x}px; top: {y0}px; width: {CW}px; font-size: 12px; '
                             f'line-height: 16px; color: {self.p["muted"]}">{esc(col.get("refText") or col["ref"] + " is drawn in another band.")}</span>')
                sy = y0 + 40
                for s in col.get("states", []):
                    parts.append(self.card(s, x, sy, SW, main=False))
                    sy += self.card_h(s.get("sub")) + 24
                bottom = max(bottom, sy)
                continue
            main = col["main"]
            h = self.card_h(main.get("sub"))
            parts.append(self.card(main, x, y0, CW, start=(ci == 0)))
            arrow = col.get("arrow")
            if arrow and ci + 1 < len(cols) and not cols[ci + 1].get("ref"):
                kind = arrow.get("kind", "push")
                self.kinds.add(kind)
                parts.append(self.hline(x + CW, x + CW + GAP, y0 + 26, kind=kind, label=arrow.get("label")))
            st, sy = self.states(col.get("states", []), x, y0 + h + 28, y0 + h)
            parts += st
            bottom = max(bottom, sy)
        width = BAND_PAD * 2 + len(cols) * CW + (len(cols) - 1) * GAP
        return parts, width, bottom - top + BAND_PAD - 20

    def grid_band(self, band, top):
        per = band.get("perRow", 4)
        y0 = top + BAND_PAD + TITLE_H
        parts = []
        if band.get("note"):
            parts.append(f'<p style="position: absolute; left: {M + BAND_PAD}px; top: {y0}px; margin: 0; font-size: 12px; '
                         f'line-height: 16px; color: {band.get("titleColor") or self.p["muted"]}">{esc(band["note"])}</p>')
            y0 += 32
        bottom = y = y0
        cards = band["grid"]
        for start in range(0, len(cards), per):
            row = cards[start:start + per]
            for i, c in enumerate(row):
                parts.append(self.card(c, M + BAND_PAD + i * (CW + GAP), y, CW, main=False))
            y += max(self.card_h(c.get("sub")) for c in row) + 20
            bottom = y
        cols = min(per, len(band["grid"])) or 1
        return parts, BAND_PAD * 2 + cols * CW + (cols - 1) * GAP, bottom - top + BAND_PAD - 20

    def legend(self, x):
        p = self.p
        rows = [(k, LEGEND[k]) for k in ("push", "sheet", "cover", "tab") if k in self.kinds] or [("push", LEGEND["push"])]
        rows.append(("rail", "Another state of that step, and when it shows"))
        out = []
        for i, (kind, text) in enumerate(rows):
            out.append(f'<div style="position: relative; height: 18px{"; margin-top: 6px" if i else ""}">{self.hline(0, 56, 9, kind=kind)}'
                       f'<span style="position: absolute; left: 68px; top: 1px">{esc(text)}</span></div>')
        return (f'<div style="position: absolute; left: {x}px; top: {M}px; width: 420px; box-sizing: border-box; padding: 14px 16px; '
                f'border-radius: 12px; border: 1px solid {p["cardBorder"]}; background: {p["card"]}; font-size: 12px; line-height: 16px; '
                f'color: {p["muted"]}">{"".join(out)}<div style="margin-top: 8px">A card with a coloured border starts its band.</div></div>')

    def build(self):
        p, parts, y, width = self.p, [], M + 150, 0
        for bi, band in enumerate(self.spec["bands"]):
            top = y
            inner, band_w, band_h = (self.grid_band if "grid" in band else self.flow_band)(band, top)
            tint = band.get("tint") or p["tints"][bi % len(p["tints"])]
            parts.append(f'<div aria-hidden="true" style="position: absolute; left: {M}px; top: {top}px; width: {band_w}px; height: {band_h}px; '
                         f'border-radius: 22px; background: {tint}"></div>')
            parts.append(f'<h2 style="position: absolute; left: {M + BAND_PAD}px; top: {top + 26}px; margin: 0; font-size: 16px; '
                         f'line-height: 20px; font-weight: 600; color: {band.get("titleColor") or p["ink"]}">{esc(band["title"])}</h2>')
            parts += inner
            width = max(width, M + band_w + M)
            y = top + band_h + 48
        width = max(width, 1280)
        height = y - 48 + M
        title_font = self.spec.get("titleFont") or self.spec.get("font") or "system-ui, sans-serif"
        header = (f'<h1 style="position: absolute; left: {M}px; top: {M}px; margin: 0; font-family: {title_font}; font-size: 52px; '
                  f'line-height: 60px; font-weight: 500; color: {p["ink"]}">{esc(self.spec["title"])}</h1>'
                  f'<p style="position: absolute; left: {M}px; top: {M + 70}px; width: {width - 2 * M - 460}px; margin: 0; font-size: 14px; '
                  f'line-height: 20px; color: {p["muted"]}">{esc(self.spec.get("subtitle", ""))}</p>' + self.legend(width - M - 420))
        return header + "".join(parts), width, height

    def page(self):
        body, w, h = self.build()
        p, font = self.p, self.spec.get("font") or "-apple-system, system-ui, sans-serif"
        link = f'<link rel="stylesheet" href="{html.escape(self.spec["fontLink"])}">\n' if self.spec.get("fontLink") else ""
        return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(self.spec["title"])}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{link}<style>
body{{margin:0;font-family:{font};color:{p["ink"]};-webkit-font-smoothing:antialiased}}
a{{color:{p["ink"]}}}
</style>
</helmet>
<div data-root="1" style="width: {w}px; height: {h}px; position: relative; overflow: hidden; background: {p["paper"]}; font-family: {font}; color: {p["ink"]}">{body}</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{ renderVals() {{ return {{}}; }} }}
</script>
</body>
</html>
''', w, h


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("spec")
    parser.add_argument("--out", required=True, help="where to write Main.dc.html (a scratch copy, never the live file)")
    args = parser.parse_args()
    spec = json.load(open(args.spec, encoding="utf-8"))
    source, w, h = Map(spec).page()
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(source)
    print(w, h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
