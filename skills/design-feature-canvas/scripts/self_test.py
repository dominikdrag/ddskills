#!/usr/bin/env python3
"""Exercise the artboard lint and the canvas index builder with small fixtures."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LINT = SCRIPT_DIR / "lint_artboards.py"
BUILD = SCRIPT_DIR / "build_canvas.py"


def artboard(title: str, height: int = 844, body: str = "<p>Hello</p>", width: int = 390) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{title}</title>\n<script src=\"./support.js\"></script>\n</head>\n<body>\n<x-dc>\n"
        "<helmet>\n<style>\nbody{margin:0}\n</style>\n</helmet>\n"
        f"<div style=\"width: {width}px; height: {height}px; background: #F5EAD8\">\n{body}\n</div>\n"
        "</x-dc>\n"
        f"<script type=\"text/x-dc\" data-dc-script data-props='{{\"$preview\":{{\"width\":{width},\"height\":{height}}}}}'>\n"
        "class Component extends DCLogic {\n  renderVals() {\n    return {};\n  }\n}\n</script>\n</body>\n</html>\n"
    )


def run(script: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *arguments], capture_output=True, text=True, check=False)


class LintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())

    def write(self, name: str, content: str) -> Path:
        path = self.directory / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_artboard_passes(self) -> None:
        path = self.write("Ok.dc.html", artboard("Ok", body="<button aria-label=\"Back\"><svg viewBox=\"0 0 24 24\"><path d=\"M15 5l-7 7 7 7\"></path></svg></button>"))
        result = run(LINT, str(path))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_size_mismatch_fails(self) -> None:
        src = artboard("Size", height=900).replace("\"height\":900", "\"height\":844")
        result = run(LINT, str(self.write("Size.dc.html", src)))
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from $preview", result.stdout)

    def test_forbidden_content_fails(self) -> None:
        for name, body, message in [
            ("Emoji.dc.html", "<p>Hi 🎁</p>", "emoji"),
            ("Data.dc.html", "<img src=\"data:image/png;base64,AAAA\">", "data: URI"),
            ("Comment.dc.html", "<!-- note --><p>x</p>", "HTML comment"),
            ("Unclosed.dc.html", "<div><p>x</p>", "unclosed"),
            ("Expr.dc.html", "<p>{{ a + b }}</p>", "expression"),
        ]:
            with self.subTest(name=name):
                result = run(LINT, str(self.write(name, artboard(name, body=body))))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(message, result.stdout)

    def test_missing_support_line_fails(self) -> None:
        src = artboard("NoSupport").replace("<script src=\"./support.js\"></script>", "")
        result = run(LINT, str(self.write("NoSupport.dc.html", src)))
        self.assertIn("support.js", result.stdout)

    def test_fake_status_bar_warns_only(self) -> None:
        result = run(LINT, str(self.write("Clock.dc.html", artboard("Clock", body="<span>9:41</span>"))))
        self.assertEqual(result.returncode, 0)
        self.assertIn("warning", result.stdout)


class BuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "Main.dc.html").write_text(artboard("Overview", height=1120, width=1280, body="<a href=\"Gifts-A.dc.html\">Gifts</a>"), encoding="utf-8")
        (self.project / "Gifts-A.dc.html").write_text(artboard("A", height=1400, body="<a href=\"Gifts-B.dc.html\">Next</a>"), encoding="utf-8")
        (self.project / "Gifts-B.dc.html").write_text(artboard("B"), encoding="utf-8")
        (self.project / "Plans-A.dc.html").write_text(artboard("C"), encoding="utf-8")
        self.rows = {
            "title": "Feature designs",
            "overview": {"file": "Main.dc.html", "width": 1280, "height": 1120},
            "pages": [{"id": "lead", "name": "Lead", "fill": "green", "rows": [
                {"key": "gifts", "title": "Gift ideas", "sticky": "Lead · M", "artboards": [
                    {"file": "Gifts-A.dc.html", "title": "G01 · A", "height": 1400, "links": True},
                    {"file": "Gifts-B.dc.html", "title": "G02 · B", "height": 844}]},
                {"key": "plans", "title": "Plans", "sticky": "Next · L", "artboards": [
                    {"file": "Plans-A.dc.html", "title": "C01 · A", "height": 844}]},
            ]}],
        }

    def build(self, *extra: str) -> subprocess.CompletedProcess:
        rows_path = self.root / "rows.json"
        rows_path.write_text(json.dumps(self.rows), encoding="utf-8")
        return run(BUILD, str(rows_path), str(self.project), "--now", "2026-01-01T00:00:00Z", *extra)

    def canvas(self) -> dict:
        return json.loads((self.project / "canvas.json").read_text(encoding="utf-8"))

    def test_layout(self) -> None:
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stdout)
        canvas = self.canvas()
        boards = canvas["boards"]
        self.assertEqual((boards["Gifts-B.dc.html"]["x"], boards["Gifts-B.dc.html"]["y"]), (470, 0))
        self.assertEqual(boards["Plans-A.dc.html"]["y"], 1400 + 380)
        self.assertTrue(boards["Gifts-A.dc.html"]["is_interactive"])
        self.assertEqual(canvas["notes"]["t_plans"]["y"], 1780 - 250)
        self.assertEqual(canvas["notes"]["s_gifts"]["x"], 2 * 470)
        self.assertEqual(canvas["order"][0], "Main.dc.html")
        self.assertEqual(canvas["createdOnFiles"], {"v": 1, "at": "2026-01-01T00:00:00Z"})
        self.assertEqual([page["id"] for page in canvas["pages"]], ["overview", "lead"])

    def test_unlisted_file_and_broken_link_fail(self) -> None:
        (self.project / "Stray.dc.html").write_text(artboard("Stray", body="<a href=\"Nowhere.dc.html\">x</a>"), encoding="utf-8")
        result = self.build()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not listed", result.stdout)

    def test_height_mismatch_fails(self) -> None:
        self.rows["pages"][0]["rows"][0]["artboards"][1]["height"] = 900
        result = self.build()
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from index", result.stdout)

    def test_existing_keys_and_user_notes_survive(self) -> None:
        existing = {"v": 3, "title": "Kept title", "createdOnFiles": {"v": 1, "at": "2025-01-01T00:00:00Z"},
                    "boards": {"Gifts-A.dc.html": {"x": 5, "y": 5, "w": 390, "h": 1400, "guides": [{"kind": "grid", "size": 8}]}},
                    "notes": {"arrow1": {"x": 1, "y": 2, "text": "", "kind": "arrow"}}, "designSystems": [{"namespace": "app"}]}
        existing_path = self.root / "existing.json"
        existing_path.write_text(json.dumps(existing), encoding="utf-8")
        result = self.build("--existing", str(existing_path))
        self.assertEqual(result.returncode, 0, result.stdout)
        canvas = self.canvas()
        self.assertEqual(canvas["title"], "Kept title")
        self.assertEqual(canvas["createdOnFiles"]["at"], "2025-01-01T00:00:00Z")
        self.assertEqual(canvas["boards"]["Gifts-A.dc.html"]["x"], 0)
        self.assertIn("guides", canvas["boards"]["Gifts-A.dc.html"])
        self.assertIn("arrow1", canvas["notes"])
        self.assertEqual(canvas["designSystems"], [{"namespace": "app"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
