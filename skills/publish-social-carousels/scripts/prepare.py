#!/usr/bin/env python3
"""Prepare a read-only publishing plan from marketing campaign manifests (Python 3.10+)."""

import argparse
import hashlib
import json
import re
import struct
import sys
from datetime import date
from pathlib import Path

PLATFORMS = ("instagram", "facebook", "tiktok", "youtube")
RATIOS = {"instagram": (4, 5), "facebook": (4, 5), "tiktok": (9, 16), "youtube": (9, 16)}
FIELDS = {"instagram": ("caption",), "facebook": ("caption",),
          "tiktok": ("title", "caption"), "youtube": ("body",)}


class PreparationError(ValueError):
    pass


def inside(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise PreparationError(f"path outside {root}: {value}")
    return path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nodes(node, key):
    yield key, node
    for child in node.get("variants", []):
        yield from nodes(child, key + "/" + child["id"])


def png_size(path):
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise PreparationError(f"expected a PNG with an IHDR header: {path}")
    return struct.unpack(">II", header[16:24])


def images(campaign, node, platform):
    ratio = RATIOS[platform]
    groups = {}
    for _, child in nodes(node, ""):
        for asset in child.get("assets", []):
            if asset.get("role") != "image":
                continue
            path = inside(campaign, asset["path"])
            width, height = png_size(path)
            if width <= 0 or height <= 0:
                raise PreparationError(f"invalid image dimensions: {path}")
            if not re.fullmatch(r"\d+\.png", path.name):
                raise PreparationError(f"expected numbered PNG slides: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != asset.get("sha256"):
                raise PreparationError(f"manifest hash mismatch: {path}")
            group = groups.setdefault(path.parent, {})
            if path in group:
                raise PreparationError(f"image declared more than once: {path}")
            group[path] = {"path": str(path), "sha256": actual, "width": width, "height": height}
    matching = {}
    for directory, group in groups.items():
        fits = [image["width"] * ratio[1] == image["height"] * ratio[0] for image in group.values()]
        if any(fits):
            if not all(fits):
                raise PreparationError(f"mixed aspect ratios in slide directory: {directory}")
            matching[directory] = group
    if len(matching) != 1:
        raise PreparationError(f"{platform}: expected one {ratio[0]}:{ratio[1]} image directory; found {len(matching)}")
    directory, group = next(iter(matching.items()))
    ordered = sorted(group, key=lambda path: int(path.stem))
    if len(ordered) < 2 or [int(p.stem) for p in ordered] != list(range(1, len(ordered) + 1)):
        raise PreparationError(f"slides must start at 01 and be contiguous: {directory}")
    if platform == "youtube" and len(ordered) > 10:
        raise PreparationError("YouTube pack exceeds the ten-image workflow; inspect current UI before adapting it")
    return [group[p] for p in ordered]


def copy_fields(campaign, node, platform):
    declared = node.get("copy", {}).get(platform, {})
    result = {}
    for field in FIELDS[platform]:
        if field not in declared:
            raise PreparationError(f"{platform}: missing canonical {field} file declaration")
        path = inside(campaign, declared[field])
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        if not text.strip():
            raise PreparationError(f"empty publishing copy: {path}")
        if platform == "tiktok" and field == "title":
            title = text.strip()
            if len(title) > 90 or len(title.splitlines()) != 1:
                raise PreparationError(f"TikTok title must be one line, at most 90 characters: {path}")
        result[field] = {"path": str(path), "text": text, "characters": len(text.rstrip("\n")),
                         "sha256": hashlib.sha256(raw).hexdigest()}
    return result


def prepare(repo, posts, platforms, when, *, check_published_inputs=False):
    repo = Path(repo).resolve()
    date.fromisoformat(when)
    tasks, seen = [], set()
    for value in posts:
        folder = inside(repo, value)
        parts = folder.relative_to(repo).parts
        try:
            split = parts.index("posts")
        except ValueError:
            raise PreparationError(f"expected a campaign/posts/post-id path: {folder}") from None
        campaign = repo.joinpath(*parts[:split])
        post_parts = parts[split + 1:]
        if not post_parts or len(post_parts) % 2 != 1 or any(
                post_parts[index] != "variants" for index in range(1, len(post_parts), 2)):
            raise PreparationError(f"expected posts/post-id or posts/post-id/variants/variant-id: {folder}")
        requested = "/".join(post_parts[::2])
        manifest = read_json(campaign / "campaign.json")
        all_nodes = [pair for post in manifest["posts"] for pair in nodes(post, post["id"])]
        if requested not in {key for key, _ in all_nodes}:
            raise PreparationError(f"no declared post or variant {requested!r} in {campaign}")
        publication = campaign / "publication.json"
        records = read_json(publication).get("posts", {}) if publication.is_file() else {}
        for platform in dict.fromkeys(platforms):
            if platform not in PLATFORMS:
                raise PreparationError(f"unsupported platform: {platform}")
            matches = [(key, node) for key, node in all_nodes
                       if (key == requested or key.startswith(requested + "/"))
                       and platform in node.get("platforms", [])]
            if len(matches) != 1:
                raise PreparationError(f"{requested}/{platform}: expected one declaring unit, found {len(matches)}")
            key, node = matches[0]
            identity = (str(campaign), key, platform)
            if identity in seen:
                raise PreparationError(f"duplicate requested publication: {key}/{platform}")
            seen.add(identity)
            if node.get("format") != "carousel":
                raise PreparationError(f"{key}: expected format carousel")
            record = records.get(key, {}).get(platform)
            if record is not None and record.get("status") not in ("scheduled", "published"):
                raise PreparationError(f"invalid publication status: {key}/{platform}")
            action = "check_remote_before_publish"
            if record:
                action = "skip_published" if record["status"] == "published" and record.get("url") else "reconcile"
            task = {"app": manifest["app"], "campaign": str(campaign), "record_key": key,
                    "platform": platform, "format": "image_post" if platform == "youtube" else "photo_carousel",
                    "production_state": node.get("state", {}).get("production"),
                    "action": action, "existing_record": record,
                    "record_command": ["python3", str(repo / "tools/campaigns/campaigns.py"), "posted",
                                       str(campaign), key, platform, "--date", when, "--url", "<verified-live-url>"]}
            if action == "skip_published" and not check_published_inputs:
                task["input_validation"] = "skipped_already_published"
            else:
                media = images(campaign, node, platform)
                task.update(input_validation="hashes_and_png_headers_checked",
                            image_directory=str(Path(media[0]["path"]).parent), image_count=len(media),
                            images=media, copy=copy_fields(campaign, node, platform))
            tasks.append(task)
    return {"schema_version": 1, "date": when, "repo": str(repo), "read_only_preparation": True,
            "note": "Verify active accounts, provenance, current claims and remote state before publishing.",
            "tasks": tasks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--post", action="append", required=True, help="repo-relative campaign/posts/post-id folder")
    parser.add_argument("--platforms", nargs="+", choices=PLATFORMS, required=True)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD in the user's publishing timezone")
    parser.add_argument("--check-published-inputs", action="store_true", help="also audit media/copy for completed records")
    parser.add_argument("--output", type=Path, help="new JSON plan outside the marketing repository; defaults to stdout")
    args = parser.parse_args()
    try:
        plan = prepare(args.repo, args.post, args.platforms, args.date,
                       check_published_inputs=args.check_published_inputs)
        content = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            target = args.output.resolve()
            if target.is_relative_to(args.repo.resolve()):
                raise PreparationError("run plans belong outside the marketing repository")
            with target.open("x", encoding="utf-8") as stream:
                stream.write(content)
            print(f"Prepared {len(plan['tasks'])} publication tasks: {target}")
        else:
            print(content, end="")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
