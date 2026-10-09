"""Run with: python3 -m unittest discover -s tests -v"""

import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit
import zipfile

from PIL import Image, ImageCms


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "asset_pack.py"
SPEC = importlib.util.spec_from_file_location("asset_pack", SCRIPT)
pack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pack)
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


class AssetPackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "source"
        self.root.mkdir()
        self.manifest_path = self.root / "manifest.json"
        self.output = self.base / "delivery"
        self.make_image()
        self.manifest = {
            "schemaVersion": 1,
            "placement": "search-results",
            "previewWidths": [1536, 360],
            "assets": [{"id": "example-en", "locale": "en-US", "file": "art.png", "width": 120, "height": 80}],
            "specification": {"url": "https://example.test/spec", "checkedAt": "2026-10-09"},
        }
        self.save_manifest()

    def make_image(self, name="art.png", mode="RGB", profile=SRGB, **options):
        color = (230, 190, 110, 255) if mode == "RGBA" else (230, 190, 110)
        image = Image.new(mode, (120, 80), color)
        if profile is not None:
            options["icc_profile"] = profile
        image.save(self.root / name, **options)

    def save_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def validate(self):
        self.save_manifest()
        return pack.validate(self.manifest_path)[0]

    def rejected(self):
        with self.assertRaises((pack.ValidationError, OSError)):
            self.validate()

    def test_rgb_png_and_jpeg_pass_with_hashes_and_unchanged_inputs(self):
        self.make_image("art.jpg")
        self.manifest["assets"].append({"id": "example-pl", "locale": "pl", "file": "art.jpg", "width": 120, "height": 80})
        original = {}
        for asset in self.manifest["assets"]:
            original[asset["file"]] = (self.root / asset["file"]).read_bytes()
            asset["sha256"] = hashlib.sha256(original[asset["file"]]).hexdigest()
        report = self.validate()
        self.assertEqual([a["format"] for a in report["assets"]], ["PNG", "JPEG"])
        self.assertTrue(all(a["icc"]["status"] == "srgb-verified" for a in report["assets"]))
        for name, content in original.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_missing_profile_requires_explicit_opt_out_and_is_unverified(self):
        self.make_image(profile=None)
        self.rejected()
        self.manifest["requireEmbeddedSrgb"] = False
        report = self.validate()
        self.assertEqual(report["assets"][0]["icc"], {"embedded": False, "status": "missing-unverified"})
        built = pack.build(self.manifest_path, self.output)
        self.assertEqual(built["previews"][0]["colorHandling"], "assumed-srgb-from-unverified-input")
        self.assertEqual(built["assets"][0]["icc"]["status"], "missing-unverified")

    def test_invalid_or_non_srgb_profile_rejected_even_with_opt_out(self):
        self.manifest["requireEmbeddedSrgb"] = False
        for profile in (b"not a valid ICC", ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()):
            with self.subTest(profile=profile[:10]):
                self.make_image(profile=profile)
                self.rejected()

    def test_opaque_alpha_and_rgb_transparency_are_rejected(self):
        self.make_image(mode="RGBA")
        self.rejected()
        self.make_image(transparency=(230, 190, 110))
        self.rejected()

    def test_dimensions_must_match_and_be_positive_integers(self):
        for bad in (121, 0, -1, 120.0, True):
            with self.subTest(width=bad):
                self.manifest["assets"][0]["width"] = bad
                self.rejected()

    def test_stale_asset_and_source_hash_rejected(self):
        self.manifest["assets"][0]["sha256"] = "0" * 64
        self.rejected()
        del self.manifest["assets"][0]["sha256"]
        (self.root / "notes.txt").write_text("source provenance")
        self.manifest["sources"] = [{"file": "notes.txt", "sha256": "0" * 64}]
        self.rejected()
        self.manifest["sources"][0]["sha256"] = pack.sha256(self.root / "notes.txt")
        self.assertEqual(len(self.validate()["sources"]), 1)

    def test_paths_must_be_relative_and_contained_in_root(self):
        outside = self.base / "outside.png"
        outside.write_bytes((self.root / "art.png").read_bytes())
        (self.root / "escaped.png").symlink_to(outside)
        for path in (str(outside), "C:/outside.png", "../outside.png", "escaped.png", "../source/art.png", "art.png\n"):
            with self.subTest(path=path):
                self.manifest["assets"][0]["file"] = path
                self.rejected()
        self.manifest["assets"][0]["file"] = "art.png"
        self.manifest["attachments"] = ["../outside.png"]
        self.rejected()
        del self.manifest["attachments"]
        self.manifest["sources"] = [{"file": "escaped.png", "sha256": pack.sha256(outside)}]
        self.rejected()

    def test_duplicate_or_unsafe_identifiers_rejected(self):
        self.manifest["assets"].append({**self.manifest["assets"][0], "id": "EXAMPLE-EN"})
        self.rejected()
        self.manifest["assets"].pop()
        for identifier in ("../escape", "<script>", "", ".", "a/b"):
            with self.subTest(identifier=identifier):
                self.manifest["assets"][0]["id"] = identifier
                self.rejected()

    def test_extension_orientation_and_animation_rejected(self):
        self.make_image("real.jpg")
        (self.root / "art.png").write_bytes((self.root / "real.jpg").read_bytes())
        self.rejected()
        (self.root / "alias.png").symlink_to(self.root / "real.jpg")
        self.manifest["assets"][0]["file"] = "alias.png"
        self.rejected()
        self.manifest["assets"][0]["file"] = "art.png"
        exif = Image.Exif()
        exif[274] = 6
        self.make_image(exif=exif)
        self.rejected()
        first = Image.new("RGB", (120, 80), "red")
        second = Image.new("RGB", (120, 80), "blue")
        first.save(self.root / "art.png", save_all=True, append_images=[second], duration=100, icc_profile=SRGB)
        self.rejected()

    def test_build_checksums_zip_byte_equality_and_thumbnail_aspect(self):
        (self.root / "notes.txt").write_text("approved production notes", encoding="utf-8")
        self.manifest["attachments"] = ["notes.txt"]
        self.manifest["sources"] = [{"file": "notes.txt", "sha256": pack.sha256(self.root / "notes.txt")}]
        self.save_manifest()
        originals = {p.name: p.read_bytes() for p in self.root.iterdir()}
        built = pack.build(self.manifest_path, self.output)
        self.assertTrue(built["zip"]["byteEqualityVerified"])
        self.assertEqual(built["specification"], self.manifest["specification"])
        self.assertEqual((self.output / "assets/example-en.png").read_bytes(), originals["art.png"])
        self.assertEqual((self.output / "attachments/notes.txt").read_bytes(), originals["notes.txt"])
        for width in (1536, 360):
            with Image.open(self.output / f"previews/example-en-{width}.png") as image:
                self.assertEqual(image.size, (width, width * 2 // 3))
                self.assertEqual(image.mode, "RGB")
                self.assertIn("icc_profile", image.info)
        entries = {}
        for line in (self.output / "checksums.sha256").read_text().splitlines():
            digest, name = line.split("  ", 1)
            entries[name] = digest
            self.assertEqual(pack.sha256(self.output / name), digest)
        actual_payload = {str(p.relative_to(self.output)) for p in self.output.rglob("*") if p.is_file()}
        self.assertEqual(set(entries), actual_payload - {"checksums.sha256", "delivery.zip"})
        with zipfile.ZipFile(self.output / "delivery.zip") as archive:
            self.assertEqual(set(archive.namelist()), actual_payload - {"delivery.zip"})
            for name in archive.namelist():
                self.assertEqual(archive.read(name), (self.output / name).read_bytes())
        for name, content in originals.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_review_escapes_locale_and_has_fixed_thumbnail_width(self):
        self.manifest["assets"][0]["locale"] = '<script>alert("bad")</script>'
        self.save_manifest()
        pack.build(self.manifest_path, self.output)
        review = (self.output / "review.html").read_text()
        self.assertNotIn("<script>", review)
        self.assertIn("&lt;script&gt;", review)
        self.assertIn('style="width:360px"', review)

    def test_exact_input_manifest_retains_custom_fields_and_validation_hash(self):
        self.manifest["story"] = {"headline": "A real benefit", "selection": "chosen"}
        self.manifest["project"] = {"name": "An app"}
        self.manifest["limitations"] = ["App UI remains English."]
        original = (json.dumps(self.manifest, indent=4, ensure_ascii=False) + "\n\n").encode("utf-8")
        self.manifest_path.write_bytes(original)
        validated = pack.validate(self.manifest_path)[0]
        self.assertEqual(validated["inputManifest"]["sha256"], hashlib.sha256(original).hexdigest())
        built = pack.build(self.manifest_path, self.output)
        self.assertEqual(built["inputManifest"]["sha256"], validated["inputManifest"]["sha256"])
        copied = self.output / built["inputManifest"]["outputFile"]
        self.assertEqual(copied.read_bytes(), original)
        self.assertEqual(json.loads(copied.read_bytes())["story"], self.manifest["story"])
        with zipfile.ZipFile(self.output / "delivery.zip") as archive:
            self.assertEqual(archive.read("input-manifest.json"), original)

    def test_manifest_change_after_validation_is_rejected(self):
        original_validate = pack.validate

        def validate_then_change(*args):
            result = original_validate(*args)
            self.manifest_path.write_bytes(self.manifest_path.read_bytes() + b"\n")
            return result

        with patch.object(pack, "validate", side_effect=validate_then_change):
            with self.assertRaises(pack.ValidationError):
                pack.build(self.manifest_path, self.output)
        self.assertEqual({p.name for p in self.base.iterdir()}, {"source"})

    def test_review_links_attachments_manifest_and_zip_with_encoded_paths(self):
        attachment = 'Source notes/provenance #1 & ół 100%.txt'
        destination = self.root / attachment
        destination.parent.mkdir()
        destination.write_text("production provenance")
        self.manifest["attachments"] = [attachment]
        self.save_manifest()
        pack.build(self.manifest_path, self.output)

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []
                self.labels = []
                self.in_link = False

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.urls.append(dict(attrs)["href"])
                    self.in_link = True

            def handle_endtag(self, tag):
                if tag == "a":
                    self.in_link = False

            def handle_data(self, data):
                if self.in_link:
                    self.labels.append(data)

        parser = Links()
        review = (self.output / "review.html").read_text()
        parser.feed(review)
        self.assertIn(attachment, parser.labels)
        self.assertIn("&amp;", review)
        decoded = []
        for url in parser.urls:
            parts = urlsplit(url)
            self.assertFalse(parts.query)
            self.assertFalse(parts.fragment)
            relative = unquote(parts.path)
            decoded.append(relative)
            self.assertTrue((self.output / relative).is_file(), url)
        self.assertIn("input-manifest.json", decoded)
        self.assertIn("delivery.zip", decoded)
        self.assertIn(f"attachments/{attachment}", decoded)

    def test_existing_empty_or_nonempty_output_preserved(self):
        self.output.mkdir()
        with self.assertRaises(pack.ValidationError):
            pack.build(self.manifest_path, self.output)
        sentinel = self.output / "keep.txt"
        sentinel.write_text("keep me")
        with self.assertRaises(pack.ValidationError):
            pack.build(self.manifest_path, self.output)
        self.assertEqual(sentinel.read_text(), "keep me")

    def test_validation_failure_does_not_create_output_and_build_failure_cleans_temp(self):
        self.manifest["assets"][0]["width"] = 1
        self.save_manifest()
        with self.assertRaises(pack.ValidationError):
            pack.build(self.manifest_path, self.output)
        self.assertEqual({p.name for p in self.base.iterdir()}, {"source"})
        self.manifest["assets"][0]["width"] = 120
        self.save_manifest()
        with patch.object(pack, "verify_zip", side_effect=pack.ValidationError("simulated verification failure")):
            with self.assertRaises(pack.ValidationError):
                pack.build(self.manifest_path, self.output)
        self.assertEqual({p.name for p in self.base.iterdir()}, {"source"})

    def test_cli_emits_json_and_failure_exit_code(self):
        good = subprocess.run([sys.executable, str(SCRIPT), "validate", str(self.manifest_path)], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)["valid"])
        self.manifest["assets"][0]["sha256"] = "0" * 64
        self.save_manifest()
        bad = subprocess.run([sys.executable, str(SCRIPT), "validate", str(self.manifest_path)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertFalse(json.loads(bad.stderr)["valid"])
        self.assertEqual(bad.stdout, "")


if __name__ == "__main__":
    unittest.main()
