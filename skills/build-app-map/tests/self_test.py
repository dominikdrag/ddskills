#!/usr/bin/env python3
"""End-to-end check of the App Map helpers on a tiny fixture app: kit build, map, index, lint, layout, drift."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
TEMPLATES = SKILL / "templates"

VIEW = "import SwiftUI\n\nstruct {name}: View {{\n    var body: some View {{ Text(\"{text}\") }}\n}}\n"
BOARDS_MODULE = '''import chrome as c


@c.draw("Home-Main")
def _():
    return ('<main style="flex: 1 1 auto; padding: 24px">'
            + c.link("Open detail", c.L("Home-Detail"), "display: block; height: 44px", label="Open detail")
            + c.link("Settings", c.L("Settings-Sheet"), "display: block; height: 44px") + '</main>')


@c.draw("Home-Detail")
def _():
    return '<main style="padding: 24px">' + c.link("Back", c.L("Home-Main"), "display: block; height: 44px") + '</main>'


@c.draw("Settings-Sheet")
def _():
    return c.sheet('<p style="margin: 0">Home</p>', c.link("Done", c.L("Home-Main"), "display: block; height: 44px"))


@c.draw("Kit-Tokens")
def _():
    return c.kit_board("Tokens", c.swatches() + c.specimen([("Title", "font-size: 28px; font-weight: 700", "Title")]))
'''


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd, check=False)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


class AppMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp())
        cls.repo = cls.tmp / "app"
        sources = cls.repo / "Projects/App/Sources"
        snaps = cls.repo / "Projects/App/Tests/__Snapshots__"
        for name, text in [("Home/HomeView", "Home"), ("Home/DetailView", "Detail"), ("Settings/SettingsView", "Settings")]:
            path = sources / f"{name}.swift"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(VIEW.format(name=Path(name).name, text=text), encoding="utf-8")
        (sources / "DesignSystem").mkdir(parents=True)
        (sources / "DesignSystem/Colors.swift").write_text("import SwiftUI\nenum Colors {}\n", encoding="utf-8")
        snaps.mkdir(parents=True)
        for name in ["home.png", "home-large-text.png", "detail.png", "settings.png", "kit-tokens.png"]:
            (snaps / name).write_bytes(b"\x89PNG fixture")
        subprocess.run(["git", "init", "-q", "-b", "main", str(cls.repo)], check=True)
        git(cls.repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
        git(cls.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
        cls.commit = git(cls.repo, "rev-parse", "--short", "HEAD")

        cls.root = cls.tmp / "root"
        (cls.root / "project").mkdir(parents=True)
        shutil.copytree(SCRIPTS, cls.root / "tools")
        config = json.loads((TEMPLATES / "config.json").read_text(encoding="utf-8"))
        config.update({"snapshots": "Projects/App/Tests/__Snapshots__/", "ignored": []})
        (cls.root / "tools/config.json").write_text(json.dumps(config), encoding="utf-8")
        shutil.copytree(TEMPLATES / "kit", cls.root / "kit")
        (cls.root / "kit/boards/example.py").unlink()
        (cls.root / "kit/boards/home.py").write_text(BOARDS_MODULE, encoding="utf-8")
        snap = "Projects/App/Tests/__Snapshots__/"
        src = "Projects/App/Sources/"
        cls.inventory = {
            "title": "Fixture App Map", "canvas": "https://claude.ai/artifact/fixture", "syncedAt": cls.commit,
            "map": {"file": "Main.dc.html", "width": 1280, "height": 900, "page": "map", "pageName": "Overview"},
            "pages": [{"id": "home", "name": "Home"}, {"id": "settings", "name": "Settings"}, {"id": "kit", "name": "Design kit"}],
            "boards": [
                {"name": "Home-Main", "title": "Home", "page": "home", "row": "Home", "presentation": "tab-root",
                 "sources": [src + "Home/HomeView.swift"], "snapshot": snap + "home.png", "snapshots": [snap + "home.png"],
                 "note": "Home\nThe tab root.", "dark": True},
                {"name": "Home-Detail", "title": "Detail", "page": "home", "row": "Home", "presentation": "push",
                 "sources": [src + "Home/DetailView.swift"], "snapshot": snap + "detail.png", "snapshots": [snap + "detail.png"]},
                {"name": "Settings-Sheet", "title": "Settings (sheet)", "page": "settings", "row": "Settings", "presentation": "sheet",
                 "sources": [src + "Settings/SettingsView.swift"], "snapshot": snap + "settings.png", "snapshots": [snap + "settings.png"]},
                {"name": "Kit-Tokens", "title": "Tokens", "page": "kit", "row": "Foundations", "presentation": "kit",
                 "sources": [src + "DesignSystem/"], "snapshot": snap + "kit-tokens.png", "snapshots": [snap + "kit-tokens.png"]},
            ],
        }
        (cls.root / "inventory.json").write_text(json.dumps(cls.inventory), encoding="utf-8")
        cls.map = {"title": "Fixture App Map", "subtitle": "Every screen.", "bands": [
            {"title": "Home", "columns": [
                {"main": {"board": "Home-Main", "title": "Home", "sub": ["Tab root"]}, "arrow": {"label": "Open detail", "kind": "push"},
                 "states": [{"board": "Settings-Sheet", "when": "Settings", "title": "Settings", "pill": "Redesign in draft"}]},
                {"main": {"board": "Home-Detail", "title": "Detail"}, "arrow": None, "states": []}]},
            {"title": "Dark appearance", "grid": [{"board": "Dark-Home-Main", "title": "Home"}], "tint": "#222222", "titleColor": "#EEEEEE"},
            {"title": "Design kit", "grid": [{"board": "Kit-Tokens", "title": "Tokens"}], "note": "Not screens: the design system as it ships."}]}
        (cls.root / "map.json").write_text(json.dumps(cls.map), encoding="utf-8")

        cls.build = run(str(cls.root / "kit/build_boards.py"), "--manifest", str(cls.root / "inventory.json"), "--out", str(cls.root / "project"))
        cls.gen = run(str(cls.root / "tools/gen_map.py"), str(cls.root / "map.json"), "--out", str(cls.root / "project/Main.dc.html"))
        width, height = (int(v) for v in cls.gen.stdout.split())
        cls.inventory["map"].update({"width": width, "height": height})
        (cls.root / "inventory.json").write_text(json.dumps(cls.inventory), encoding="utf-8")
        cls.index = run(str(cls.root / "tools/build_index.py"), str(cls.root / "inventory.json"), "--project", str(cls.root / "project"),
                        "--manifest", str(cls.root / "tools/boards.json"), "--now", "2026-10-08T12:00:00Z")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_kit_builds_light_and_dark_boards(self) -> None:
        self.assertEqual(self.build.returncode, 0, self.build.stderr)
        dark = (self.root / "project/Dark-Home-Main.dc.html").read_text(encoding="utf-8")
        self.assertIn("#000000", dark)
        self.assertIn('href="Home-Detail.dc.html"', dark, "links to boards without a dark copy stay light")
        light = (self.root / "project/Home-Main.dc.html").read_text(encoding="utf-8")
        self.assertIn("#FFFFFF", light)

    def test_index_lays_out_rows_and_dark_page(self) -> None:
        self.assertEqual(self.index.returncode, 0, self.index.stdout)
        canvas = json.loads((self.root / "project/canvas.json").read_text(encoding="utf-8"))
        self.assertEqual([p["id"] for p in canvas["pages"]], ["map", "home", "settings", "dark", "kit"])
        self.assertEqual(canvas["boards"]["Kit-Tokens.dc.html"]["page"], "kit")
        self.assertIn("Design kit page", canvas["notes"]["s_map_howto"]["text"])
        self.assertEqual(canvas["order"][0], "Main.dc.html")
        self.assertEqual(canvas["boards"]["Home-Detail.dc.html"]["x"], 470)
        self.assertEqual(canvas["notes"]["t_home_0"]["y"], -250)
        self.assertEqual(canvas["notes"]["s_home_0"]["x"], 940)
        manifest = json.loads((self.root / "tools/boards.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["boards"]["Dark-Home-Main"]["light"], "Home-Main")
        self.assertEqual(manifest["scannedThrough"], self.commit)

    def test_index_refuses_to_overwrite(self) -> None:
        again = run(str(self.root / "tools/build_index.py"), str(self.root / "inventory.json"), "--project", str(self.root / "project"),
                    "--manifest", str(self.tmp / "other.json"))
        self.assertEqual(again.returncode, 1)
        self.assertIn("refusing", again.stdout)

    def test_lint_and_layout_pass(self) -> None:
        lint = run(str(self.root / "tools/lint.py"), str(self.root / "project"))
        self.assertEqual(lint.returncode, 0, lint.stdout)
        layout = run(str(self.root / "tools/check_layout.py"), str(self.root / "project"))
        self.assertEqual(layout.returncode, 0, layout.stdout)

    def test_map_has_one_card_per_board_and_legend(self) -> None:
        source = (self.root / "project/Main.dc.html").read_text(encoding="utf-8")
        for board in ["Home-Main", "Home-Detail", "Settings-Sheet", "Dark-Home-Main", "Kit-Tokens"]:
            self.assertEqual(source.count(f'<a href="{board}.dc.html"'), 1, board)
        self.assertIn("Redesign in draft", source)
        self.assertIn("Push: the next step", source)
        self.assertIn("Not screens: the design system as it ships.", source)

    def test_coverage_and_drift(self) -> None:
        cov = run(str(self.root / "tools/check_drift.py"), "--coverage", "--repo", str(self.repo), "--to", self.commit,
                  "--manifest", str(self.root / "inventory.json"))
        self.assertEqual(cov.returncode, 0, cov.stdout)
        clean = run(str(self.root / "tools/check_drift.py"), "--repo", str(self.repo), "--json")
        self.assertEqual(json.loads(clean.stdout)["direct"], {})
        view = self.repo / "Projects/App/Sources/Home/HomeView.swift"
        view.write_text(view.read_text(encoding="utf-8").replace("Home", "Today"), encoding="utf-8")
        (self.repo / "Projects/App/Sources/Home/NewView.swift").write_text(VIEW.format(name="NewView", text="New"), encoding="utf-8")
        (self.repo / "Projects/App/Sources/DesignSystem/Colors.swift").write_text("import SwiftUI\nenum Colors { static let a = 1 }\n",
                                                                                  encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "change")
        drift = json.loads(run(str(self.root / "tools/check_drift.py"), "--repo", str(self.repo), "--json").stdout)
        self.assertEqual(sorted(drift["direct"]), ["Dark-Home-Main", "Home-Main", "Kit-Tokens"], "a folder source covers its files")
        self.assertEqual(drift["unlisted"], ["Projects/App/Sources/Home/NewView.swift"])

    def test_lint_catches_format_errors(self) -> None:
        bad = self.tmp / "bad" / "project"
        bad.mkdir(parents=True)
        good = (self.root / "project/Home-Detail.dc.html").read_text(encoding="utf-8")
        cases = {
            "NoSupport.dc.html": (good.replace('<script src="./support.js"></script>', ""), "support.js"),
            "Nested.dc.html": (good.replace("</main>", '<a href="Nested.dc.html"><button>x</button></a></main>'), "<button> inside <a>"),
            "Broken.dc.html": (good, "broken link"),
            "Size.dc.html": (good.replace('"height":844', '"height":900'), "!= $preview"),
            "Unclosed.dc.html": (good.replace("</main>", "<div></main>"), "unclosed"),
        }
        for name, (src, _) in cases.items():
            (bad / name).write_text(src, encoding="utf-8")
        result = run(str(SCRIPTS / "lint.py"), str(bad))
        self.assertEqual(result.returncode, 1)
        for name, (_, message) in cases.items():
            self.assertTrue(any(line.startswith(f"ERROR {name}") and message in line for line in result.stdout.splitlines()),
                            f"{name}: expected {message!r} in\n{result.stdout}")
        pending = run(str(SCRIPTS / "lint.py"), "--pending-ok", str(bad / "Broken.dc.html"))
        self.assertEqual(pending.returncode, 0, pending.stdout)

    def test_layout_catches_overlap_and_missing_card(self) -> None:
        project = self.tmp / "layout" / "project"
        shutil.copytree(self.root / "project", project)
        canvas = json.loads((project / "canvas.json").read_text(encoding="utf-8"))
        canvas["boards"]["Home-Detail.dc.html"]["x"] = 100
        (project / "canvas.json").write_text(json.dumps(canvas), encoding="utf-8")
        main = (project / "Main.dc.html").read_text(encoding="utf-8").replace('<a href="Home-Detail.dc.html"', '<a href="Home-Gone.dc.html"')
        (project / "Main.dc.html").write_text(main, encoding="utf-8")
        result = run(str(SCRIPTS / "check_layout.py"), str(project), "--manifest", str(self.root / "tools/boards.json"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("boards overlap on page home", result.stdout)
        self.assertIn("Main.dc.html has no card for Home-Detail", result.stdout)

    def test_contact_sheet(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        images = []
        for i, size in enumerate([(390, 844), (390, 1600)]):
            path = self.tmp / f"img{i}.png"
            Image.new("RGB", size, "gray").save(path)
            images.append(str(path))
        out = self.tmp / "sheet.png"
        result = run(str(SCRIPTS / "contact_sheet.py"), str(out), *images, "--columns", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(out) as sheet:
            self.assertEqual(sheet.width, 2 * (260 + 12) + 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
