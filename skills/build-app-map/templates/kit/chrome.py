"""App Map kit: the app's tokens and shared markup. Every board module imports it as `c`.

Fill THEMES from the app's colour assets (both appearances when the app draws dark copies), FONT_LINK and the
font stacks from its typography code, and add the app's shared chrome as functions below `sheet`: header or
navigation bar, tab bar, titles, rows, buttons, notices, state screens. Builders call these instead of
copying markup, so one fix here reaches every board. Sizes and colours come from the code, never guesses.
"""
import html

THEMES = {
    "light": {"bg": "#FFFFFF", "ink": "#000000", "muted": "#6B6B6B", "action": "#0A66FF", "onAction": "#FFFFFF", "dim": "rgba(0,0,0,0.2)"},
    "dark": {"bg": "#000000", "ink": "#FFFFFF", "muted": "#A0A0A0", "action": "#4D8DFF", "onAction": "#FFFFFF", "dim": "rgba(0,0,0,0.45)"},
}
T = dict(THEMES["light"])
MODE = "light"

# A Google Fonts css2 link when the app's fonts are there, else "" and system stacks (or uploaded @font-face rules).
FONT_LINK = ""
UI = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif"
WIDTH, HEIGHT = 390, 844   # one phone screen; keep in step with tools/config.json "board"
STATUS, HOME = 47, 34      # status area and home indicator: left empty, never drawn

DRAW = {}


def draw(name):
    """Register a board's draw function: it returns the markup inside the board root."""
    def wrap(fn):
        DRAW[name] = fn
        return fn
    return wrap


def use(mode):
    """Switch the active palette; every helper reads T."""
    global MODE
    MODE = mode
    T.clear()
    T.update(THEMES[mode])


def esc(text):
    return html.escape(text, quote=False)


def L(name):
    """The href of another board."""
    return f"{name}.dc.html"


def page(title, height, body, width=WIDTH):
    """A whole board file. `body` is the markup inside the fixed root."""
    root = (f"width: {width}px; height: {height}px; position: relative; overflow: hidden; background: {T['bg']}; "
            f"font-family: {UI}; color: {T['ink']}; display: flex; flex-direction: column")
    link = f"{FONT_LINK}\n" if FONT_LINK else ""
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{link}<style>
body{{margin:0;font-family:{UI};color:{T['ink']};-webkit-font-smoothing:antialiased}}
button,input,textarea{{font-family:inherit;color:inherit}}
a{{color:{T['ink']}}}
</style>
</helmet>
<div data-root="1" style="{root}">{body}</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{width},"height":{height}}}}}'>
class Component extends DCLogic {{ renderVals() {{ return {{}}; }} }}
</script>
</body>
</html>
'''


def link(inner, href, style, label=None):
    """A control that navigates: an <a> styled as the control (never a <button> inside an <a>)."""
    aria = f' aria-label="{esc(label)}"' if label else ""
    return f'<a href="{href}"{aria} style="text-decoration: none; {style}">{inner}</a>'


def sheet(parent, body, top=62, radius=38, height=HEIGHT):
    """A system sheet over its dimmed parent. The parent layer is fixed at full size under the dim and the sheet."""
    return (f'<div style="position: absolute; left: 0; top: 0; width: {WIDTH}px; height: {height}px; z-index: 0; '
            f'display: flex; flex-direction: column">{parent}</div>'
            f'<div aria-hidden="true" style="position: absolute; inset: 0; z-index: 1; background: {T["dim"]}"></div>'
            f'<div style="position: absolute; left: 0; right: 0; top: {top}px; bottom: 0; z-index: 2; background: {T["bg"]}; '
            f'border-radius: {radius}px {radius}px 0 0; display: flex; flex-direction: column; overflow: hidden">{body}</div>')


# ---------------------------------------------------------------- Design kit helpers

def swatches(names=None):
    """Kit-Tokens: one row per token with its light and dark swatch and value. `names` maps token key to label."""
    keys = list(names or THEMES["light"])
    heads = "".join(f'<span style="width: 120px">{mode.title()}</span>' for mode in ("light", "dark") if mode in THEMES)
    rows = [f'<div style="display: flex; gap: 12px; padding-bottom: 6px; font-size: 11px; line-height: 14px; color: {T["muted"]}">'
            f'<span style="flex: 1 1 auto">Token</span>{heads}</div>']
    for key in keys:
        cells = "".join(
            f'<div style="display: flex; align-items: center; gap: 8px; width: 120px">'
            f'<span style="width: 28px; height: 28px; border-radius: 8px; background: {THEMES[mode].get(key, "transparent")}; '
            f'box-shadow: inset 0 0 0 1px rgba(127,127,127,0.35)"></span>'
            f'<span style="font-size: 11px; line-height: 14px; color: {T["muted"]}">{esc(THEMES[mode].get(key, "–"))}</span></div>'
            for mode in ("light", "dark") if mode in THEMES)
        label = esc((names or {}).get(key, key))
        rows.append(f'<div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid rgba(127,127,127,0.2)">'
                    f'<span style="flex: 1 1 auto; font-size: 13px; line-height: 16px; font-weight: 600">{label}</span>{cells}</div>')
    return "".join(rows)


def specimen(roles):
    """Kit-Type: one line per type role. `roles` is [(name, css, sample)], css being the role's inline font style."""
    return "".join(
        f'<div style="padding: 10px 0; border-bottom: 1px solid rgba(127,127,127,0.2)">'
        f'<div style="font-size: 11px; line-height: 14px; color: {T["muted"]}; margin-bottom: 4px">{esc(name)} · {esc(css)}</div>'
        f'<div style="{css}">{esc(sample)}</div></div>' for name, css, sample in roles)


def kit_board(title, body, caption=""):
    """The frame of a Design kit board: the group's name, an optional source line, then the specimens."""
    note = f'<p style="margin: 0 0 16px; font-size: 12px; line-height: 16px; color: {T["muted"]}">{esc(caption)}</p>' if caption else ""
    return (f'<div style="height: {STATUS}px; flex-shrink: 0"></div><main data-scroll="1" style="display: flex; flex-direction: column; '
            f'padding: 16px 20px 32px"><h1 style="margin: 0 0 6px; font-size: 28px; line-height: 34px">{esc(title)}</h1>{note}{body}</main>')
