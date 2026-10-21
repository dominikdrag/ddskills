"""Run with: python3 -m unittest discover -s tests -v

The checker tests need ffmpeg and ffprobe. The renderer tests also need Node; the full renders run only when CHROME_BIN and
NODE_PACKAGES (a node_modules folder with playwright-core) are set.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
CHECKER = SCRIPTS / "video_check.py"
RENDERER = SCRIPTS / "render_video.mjs"
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
HAS_BROWSER = bool(shutil.which("node") and os.environ.get("CHROME_BIN") and os.environ.get("NODE_PACKAGES"))

PAGE = """<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;background:#17161A}
#art{position:relative;width:192px;height:82px;overflow:hidden;background:#17161A;color:#F4F2ED;font:700 12px sans-serif}
h1{position:absolute;left:8px;top:30px;margin:0;font-size:12px}h1 span{display:block;white-space:nowrap;width:max-content}
#dot{position:absolute;width:20px;height:20px;border-radius:10px;background:#F5B83D}</style>
<div id="art"><h1 id="h"></h1><div id="dot"></div></div>
<script>
let S;
window.setup = async (story, locale) => {
  S = story;
  document.getElementById('h').innerHTML = story.copy[locale].lines.map(l => `<span>${l}</span>`).join('');
  await document.fonts.ready;
  return {lines: story.copy[locale].lines.length};
};
window.renderAt = t => {
  const x = S.motion.periodic ? 130 + 30 * Math.sin(2 * Math.PI * t / S.loopSeconds) : 100 + 10 * t;
  const dot = document.getElementById('dot');
  dot.style.left = x + 'px';
  dot.style.top = S.motion.top + 'px';
};
window.layout = () => {
  const o = document.getElementById('art').getBoundingClientRect();
  const box = n => { const r = n.getBoundingClientRect(); return {x: r.x - o.x, y: r.y - o.y, right: r.right - o.x, bottom: r.bottom - o.y}; };
  return {headline: box(document.getElementById('h')), lines: [...document.querySelectorAll('h1 span')].map(box),
          items: [{id: 'dot', opacity: 1, ...box(document.getElementById('dot'))}]};
};
</script>
"""


def story(**changes):
    base = {
        "canvas": {"width": 192, "height": 82},
        "fps": 30,
        "loopSeconds": 5,
        "posterTimeCode": "00:00:02:15",
        "copy": {"en-US": {"lines": ["Hello", "there."]}, "pl": {"lines": ["Dzień", "dobry."]}},
        "headline": {"left": 8, "width": 80},
        "guides": {"statusBand": {"height": 12}},
        "motion": {"periodic": True, "top": 40},
    }
    base.update(changes)
    return base


class VideoTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.story_path = self.base / "story.json"

    def write_story(self, data):
        self.story_path.write_text(json.dumps(data), encoding="utf-8")

    def make_video(self, locale, color="0x17161A", fps=30, seconds=5, tags=True):
        path = self.base / "out" / locale / "header.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        tagging = ",setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv" if tags else ""
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={color}:s=192x82:r={fps}:d={seconds}",
                        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" + tagging, "-c:v", "libx264", str(path)],
                       check=True)
        return path

    def check(self, *extra):
        return subprocess.run([sys.executable, str(CHECKER), str(self.story_path), "--video", str(self.base / "out/{locale}/header.mp4"),
                               "--previews", str(self.base / "previews"), "--preview-widths", "96,64", *extra],
                              capture_output=True, text=True)

    def render(self, *extra, env=None):
        page = self.base / "page.html"
        page.write_text(PAGE, encoding="utf-8")
        return subprocess.run(["node", str(RENDERER), str(self.story_path), "--page", str(page), "--out",
                               str(self.base / "out/{locale}/header.mp4"), "--evidence", str(self.base / "evidence"), *extra],
                              capture_output=True, text=True, timeout=300, env=env)


@unittest.skipUnless(HAS_FFMPEG, "needs ffmpeg and ffprobe")
class CheckerTests(VideoTestCase):
    def test_conforming_videos_pass_with_previews_and_hashes(self):
        self.write_story(story())
        files = {locale: self.make_video(locale) for locale in ("en-US", "pl")}
        manifest = self.base / "check.json"
        result = self.check("--manifest", str(manifest), "--prefix", "a-")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads(manifest.read_text())
        for locale, path in files.items():
            entry = record["locales"][locale]
            self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertGreaterEqual(entry["statusBandWorstContrast"], 3)
            for name in (f"a-{locale}-poster-96.png", f"a-{locale}-poster-64.png", f"a-{locale}-frames.png"):
                self.assertTrue((self.base / "previews" / name).is_file(), name)

    def test_wrong_rate_and_missing_color_tags_are_reported(self):
        self.write_story(story(copy={"en-US": {"lines": ["Hello"]}}))
        self.make_video("en-US", fps=25)
        problems = json.loads(self.check().stdout)["problems"]
        self.assertTrue(any("30 fps constant" in p for p in problems), problems)
        self.make_video("en-US", tags=False)
        problems = json.loads(self.check().stdout)["problems"]
        self.assertEqual(problems, ["en-US: BT.709 tags"])

    def test_bright_status_band_fails_contrast(self):
        self.write_story(story(copy={"en-US": {"lines": ["Hello"]}}))
        self.make_video("en-US", color="0xF4F2ED")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertTrue(any("status band contrast" in p for p in json.loads(result.stdout)["problems"]))

    def test_poster_outside_the_loop_is_refused(self):
        self.write_story(story(posterTimeCode="00:00:06:00"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("posterTimeCode", result.stderr)


@unittest.skipUnless(shutil.which("node"), "needs node")
class RendererGateTests(VideoTestCase):
    def test_offer_price_or_number_in_copy_is_refused_before_rendering(self):
        cases = [
            {"en-US": {"lines": ["Free for a week"]}},
            {"en-US": {"lines": ["Plans from $3"]}},
            {"en-US": {"lines": ["3 mornings"]}},
            {"pl": {"lines": ["Za darmo"]}},
            {"en-US": {"lines": ["Plan it"], "labels": ["50% off"]}},
        ]
        for copy in cases:
            self.write_story(story(copy=copy, offerWords=["darmo"]))
            result = self.render()
            self.assertEqual(result.returncode, 1, copy)
            self.assertIn("price", result.stderr, copy)

    def test_numbers_in_labels_are_allowed_by_the_gate(self):
        self.write_story(story(copy={"en-US": {"lines": ["Plan it"], "labels": ["Example week, 27 of 30"]}}))
        result = self.render(env={**os.environ, "NODE_PACKAGES": str(self.base / "missing")})
        self.assertIn("playwright-core", result.stderr)  # passed the copy gate, stopped where the browser loads

    def test_out_of_spec_rate_and_input_hash_mismatch_are_refused(self):
        self.write_story(story(fps=25))
        self.assertIn("fps", self.render().stderr)
        (self.base / "capture.png").write_bytes(b"capture")
        self.write_story(story(inputs=[{"file": "capture.png", "sha256": "0" * 64}]))
        self.assertIn("hash mismatch", self.render().stderr)


@unittest.skipUnless(HAS_FFMPEG and HAS_BROWSER, "needs ffmpeg, node, CHROME_BIN and NODE_PACKAGES")
class RendererTests(VideoTestCase):
    def test_periodic_page_renders_a_seamless_loop_that_passes_the_checker(self):
        self.write_story(story())
        result = self.render("--report", str(self.base / "report.json"))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((self.base / "report.json").read_text())
        self.assertEqual(report["frames"], 150)
        self.assertEqual(report["problems"], 0)
        check = self.check()
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_stills_report_an_item_in_the_status_band(self):
        self.write_story(story(motion={"periodic": True, "top": 2}))
        result = self.render("--stills", "0,1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("dot in the status band", result.stderr)

    def test_motion_that_does_not_return_to_frame_zero_fails_the_seam(self):
        self.write_story(story(copy={"en-US": {"lines": ["Hello"]}}, motion={"periodic": False, "top": 40}))
        result = self.render()
        self.assertEqual(result.returncode, 1)
        self.assertIn("loop seam", (self.base / "evidence" / "problems.txt").read_text())


if __name__ == "__main__":
    unittest.main()
