import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("prepare", Path(__file__).parents[1] / "scripts/prepare.py")
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


def png(width, height):
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = zlib.compress((b"\x00" + b"\x00\x00\x00" * width) * height)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", data) + chunk(b"IEND", b"")


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.campaign = self.repo / "app/campaigns/example"
        self.post = "app/campaigns/example/posts/P01"
        self.campaign.mkdir(parents=True)
        self.root = {"id": "P01", "format": "carousel", "platforms": [], "copy": {}, "assets": [], "variants": []}

    def variant(self, slug, platforms, count=2):
        node = {"id": slug, "format": "carousel", "platforms": platforms, "copy": {}, "assets": []}
        for platform in platforms:
            node["copy"][platform] = {}
            for field in prepare.FIELDS[platform]:
                rel = f"posts/P01/variants/{slug}/copy/{field}-{platform}.txt"
                path = self.campaign / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("A title\n" if field == "title" else "Canonical caption, membership required.\n")
                node["copy"][platform][field] = rel
        width, height = prepare.RATIOS[platforms[0]]
        for number in range(1, count + 1):
            rel = f"posts/P01/variants/{slug}/exports/images/{number:02}.png"
            path = self.campaign / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            data = png(width, height)
            path.write_bytes(data)
            node["assets"].append({"path": rel, "role": "image", "sha256": hashlib.sha256(data).hexdigest()})
        self.root["variants"].append(node)
        return node

    def run_plan(self, platforms):
        (self.campaign / "campaign.json").write_text(json.dumps({"app": "app", "posts": [self.root]}))
        return prepare.prepare(self.repo, [self.post], platforms, "2026-10-21")["tasks"]

    def test_variant_record_keys_and_published_resume(self):
        self.variant("instagram", ["instagram", "facebook"])
        self.variant("tiktok", ["tiktok", "youtube"])
        (self.campaign / "publication.json").write_text(json.dumps({"posts": {"P01/tiktok": {
            "tiktok": {"status": "published", "date": "2026-10-21", "url": "https://example.com/post"},
            "youtube": {"status": "scheduled", "date": "2026-10-22"}}}}))
        tasks = self.run_plan(prepare.PLATFORMS)
        self.assertEqual([t["record_key"] for t in tasks], ["P01/instagram"] * 2 + ["P01/tiktok"] * 2)
        self.assertEqual([t["action"] for t in tasks], ["check_remote_before_publish"] * 2 + ["skip_published", "reconcile"])
        self.assertIn("membership required", tasks[0]["copy"]["caption"]["text"])
        self.assertEqual(tasks[3]["format"], "image_post")

    def test_parent_owns_platforms_and_selects_aspect(self):
        for slug, platforms in [("instagram", ["instagram"]), ("tiktok", ["tiktok"])]:
            node = self.variant(slug, platforms)
            self.root["copy"].update(node["copy"])
            self.root["platforms"].extend(platforms)
            node["platforms"] = []
        tasks = self.run_plan(["instagram", "tiktok"])
        self.assertEqual([t["record_key"] for t in tasks], ["P01", "P01"])
        self.assertEqual([(t["images"][0]["width"], t["images"][0]["height"]) for t in tasks], [(4, 5), (9, 16)])

    def test_actual_variant_folder_resolves(self):
        self.variant("instagram", ["instagram", "facebook"])
        self.run_plan(["instagram"])
        tasks = prepare.prepare(self.repo, [self.post + "/variants/instagram"], ["instagram", "facebook"], "2026-10-21")["tasks"]
        self.assertEqual([task["record_key"] for task in tasks], ["P01/instagram"] * 2)
        with self.assertRaisesRegex(prepare.PreparationError, "expected posts/post-id"):
            prepare.prepare(self.repo, [self.post + "/instagram"], ["instagram"], "2026-10-21")

    def test_completed_input_damage_does_not_block_unresolved_platform(self):
        done = self.variant("instagram", ["instagram"])
        self.variant("tiktok", ["tiktok"])
        self.run_plan(["instagram", "tiktok"])
        (self.campaign / "publication.json").write_text(json.dumps({"posts": {"P01/instagram": {
            "instagram": {"status": "published", "date": "2026-10-21", "url": "https://example.com/post"}}}}))
        (self.campaign / done["copy"]["instagram"]["caption"]).unlink()
        tasks = self.run_plan(["instagram", "tiktok"])
        self.assertEqual(tasks[0]["input_validation"], "skipped_already_published")
        self.assertEqual(tasks[1]["image_count"], 2)
        with self.assertRaises(FileNotFoundError):
            prepare.prepare(self.repo, [self.post], ["instagram"], "2026-10-21", check_published_inputs=True)

    def test_rejects_tampered_export(self):
        node = self.variant("instagram", ["instagram"])
        (self.campaign / node["assets"][0]["path"]).write_bytes(png(8, 10))
        with self.assertRaisesRegex(prepare.PreparationError, "hash mismatch"):
            self.run_plan(["instagram"])

    def test_rejects_missing_middle_slide(self):
        node = self.variant("instagram", ["instagram"], count=3)
        node["assets"].pop(1)
        with self.assertRaisesRegex(prepare.PreparationError, "contiguous"):
            self.run_plan(["instagram"])

    def test_rejects_wrong_aspect_final_slide_instead_of_omitting_it(self):
        node = self.variant("instagram", ["instagram"], count=3)
        asset = node["assets"][-1]
        data = png(9, 16)
        (self.campaign / asset["path"]).write_bytes(data)
        asset["sha256"] = hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(prepare.PreparationError, "mixed aspect ratios"):
            self.run_plan(["instagram"])

    def test_rejects_ambiguous_platform_ownership(self):
        self.variant("one", ["instagram"])
        self.variant("two", ["instagram"])
        with self.assertRaisesRegex(prepare.PreparationError, "declaring unit, found 2"):
            self.run_plan(["instagram"])

    def test_rejects_copy_path_escape(self):
        node = self.variant("instagram", ["instagram"])
        node["copy"]["instagram"]["caption"] = "../../secret.txt"
        with self.assertRaisesRegex(prepare.PreparationError, "path outside"):
            self.run_plan(["instagram"])

    def test_rejects_duplicate_batch_entry(self):
        self.variant("instagram", ["instagram"])
        self.run_plan(["instagram"])
        with self.assertRaisesRegex(prepare.PreparationError, "duplicate requested"):
            prepare.prepare(self.repo, [self.post, self.post], ["instagram"], "2026-10-21")

    def test_preparation_does_not_create_publication(self):
        self.variant("instagram", ["instagram"])
        self.run_plan(["instagram"])
        self.assertFalse((self.campaign / "publication.json").exists())


if __name__ == "__main__":
    unittest.main()
