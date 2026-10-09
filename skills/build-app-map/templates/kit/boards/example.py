"""Draw functions for one area. Name the module after the area (onboarding.py, today.py); delete this example.

Each function returns the markup inside the board root. Link every control that navigates with c.link(...) and
c.L("<Board>"); read copy, sizes and order from the source at the pinned commit.
"""
import chrome as c


@c.draw("Example-Screen")
def _():
    t = c.T
    button = c.link("Continue", c.L("Example-Next"),
                    f"display: flex; align-items: center; justify-content: center; height: 50px; border-radius: 25px; "
                    f"background: {t['action']}; color: {t['onAction']}; font-size: 17px; font-weight: 600")
    return (f'<div style="height: {c.STATUS}px; flex-shrink: 0"></div>'
            f'<main style="flex: 1 1 auto; display: flex; flex-direction: column; padding: 24px 20px; gap: 12px">'
            f'<h1 style="margin: 0; font-size: 34px; font-weight: 700">Example</h1></main>'
            f'<div style="padding: 0 20px 8px">{button}</div><div style="height: {c.HOME}px; flex-shrink: 0"></div>')


@c.draw("Kit-Tokens")
def _():
    return c.kit_board("Tokens", c.swatches(), "Every colour token, light and dark, from the colour assets.")
