#!/usr/bin/env python3
"""Validate original artwork and build an inspectable, portable delivery pack.

Requires Python 3.10+ and Pillow with ImageCms. No inputs are rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from urllib.parse import quote
import zipfile

from PIL import Image, ImageCms


class ValidationError(ValueError):
    """An input does not satisfy the declared delivery contract."""


LIMITS = [
    "Technical file checks do not establish visual quality, legibility, claim accuracy, or Apple approval.",
    "Dimensions and the embedded-sRGB check are supplied delivery requirements, not a live Apple policy check.",
]
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SHA_PATTERN = re.compile(r"[a-fA-F0-9]{64}\Z")
FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_file(root: Path, value: object) -> tuple[str, Path]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValidationError("File paths must be nonempty relative POSIX paths.")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValidationError("Control characters are not allowed in file paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", value) or ".." in path.parts or not path.parts:
        raise ValidationError(f"File path escapes or does not identify a file: {value!r}")
    candidate = root / path
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValidationError(f"File must remain inside the asset root: {value!r}")
    return str(path), candidate


def positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValidationError(f"{label} must be a positive integer.")
    return value


def check_hash(expected: object, observed: str, label: str) -> None:
    if not isinstance(expected, str) or not SHA_PATTERN.fullmatch(expected):
        raise ValidationError(f"{label}: sha256 must contain 64 hexadecimal characters.")
    if expected.lower() != observed:
        raise ValidationError(f"{label}: SHA-256 mismatch.")


def image_metadata(path: Path, require_srgb: bool) -> dict:
    expected_format = FORMATS.get(path.suffix.lower())
    if expected_format is None:
        raise ValidationError(f"{path.name}: expected a .png, .jpg, or .jpeg file.")
    with Image.open(path) as image:
        if image.format != expected_format:
            raise ValidationError(f"{path.name}: extension and decoded format differ.")
        if getattr(image, "n_frames", 1) != 1 or getattr(image, "is_animated", False):
            raise ValidationError(f"{path.name}: animated or multi-image assets are not supported.")
        if image.mode != "RGB" or "transparency" in image.info:
            raise ValidationError(f"{path.name}: artwork must be RGB with no alpha or transparency.")
        if image.getexif().get(274, 1) != 1:
            raise ValidationError(f"{path.name}: normalize EXIF orientation before delivery.")
        image.load()
        icc_bytes = image.info.get("icc_profile")
        profile_info = {"embedded": False, "status": "missing-unverified"}
        if icc_bytes is not None:
            try:
                profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
                name = ImageCms.getProfileName(profile).strip()
                color_space = profile.profile.xcolor_space.strip()
            except Exception as error:
                raise ValidationError(f"{path.name}: invalid embedded ICC profile.") from error
            if color_space != "RGB" or not re.search(r"sRGB", name, re.IGNORECASE):
                raise ValidationError(f"{path.name}: embedded profile must identify sRGB and RGB color space.")
            profile_info = {
                "embedded": True,
                "status": "srgb-verified",
                "name": name,
                "colorSpace": color_space,
                "sha256": hashlib.sha256(icc_bytes).hexdigest(),
            }
        elif require_srgb:
            raise ValidationError(f"{path.name}: embedded sRGB ICC profile is required by this delivery manifest.")
        return {
            "width": image.width,
            "height": image.height,
            "format": image.format,
            "mode": image.mode,
            "alpha": False,
            "icc": profile_info,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }


def validate(manifest_path: Path, root: Path | None = None) -> tuple[dict, Path]:
    manifest_path = manifest_path.resolve(strict=True)
    root = (root or manifest_path.parent).resolve(strict=True)
    if not root.is_dir():
        raise ValidationError("Asset root must be a directory.")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if not isinstance(manifest, dict) or type(manifest.get("schemaVersion")) is not int or manifest["schemaVersion"] != 1:
        raise ValidationError("Expected a manifest object with schemaVersion 1.")
    placement = manifest.get("placement")
    if placement not in {"header", "search-results", "universal"}:
        raise ValidationError("placement must be header, search-results, or universal.")
    require_srgb = manifest.get("requireEmbeddedSrgb", True)
    if type(require_srgb) is not bool:
        raise ValidationError("requireEmbeddedSrgb must be a boolean.")
    widths = manifest.get("previewWidths", [1536, 360])
    if not isinstance(widths, list) or not widths:
        raise ValidationError("previewWidths must be a nonempty array.")
    for width in widths:
        positive_int(width, "Preview width")
    if len(set(widths)) != len(widths):
        raise ValidationError("previewWidths must be unique.")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValidationError("assets must be a nonempty array.")
    checked_assets = []
    identifiers = set()
    for entry in assets:
        if not isinstance(entry, dict):
            raise ValidationError("Each asset must be an object.")
        identifier = entry.get("id")
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
            raise ValidationError("Asset IDs must start with a letter or digit and contain only letters, digits, dots, underscores, or hyphens.")
        if identifier.casefold() in identifiers:
            raise ValidationError(f"Duplicate asset ID: {identifier!r}")
        identifiers.add(identifier.casefold())
        locale = entry.get("locale")
        if not isinstance(locale, str) or not locale.strip():
            raise ValidationError(f"{identifier}: locale must be a nonempty string.")
        width = positive_int(entry.get("width"), f"{identifier} width")
        height = positive_int(entry.get("height"), f"{identifier} height")
        relative, path = relative_file(root, entry.get("file"))
        metadata = image_metadata(path, require_srgb)
        if (width, height) != (metadata["width"], metadata["height"]):
            raise ValidationError(f"{identifier}: decoded dimensions do not match the manifest.")
        if "sha256" in entry:
            check_hash(entry["sha256"], metadata["sha256"], identifier)
        checked_assets.append({"id": identifier, "locale": locale, "file": relative, **metadata})
    sources = manifest.get("sources", [])
    attachments = manifest.get("attachments", [])
    if not isinstance(sources, list) or not isinstance(attachments, list):
        raise ValidationError("sources and attachments must be arrays.")
    checked_sources = []
    for source in sources:
        if not isinstance(source, dict):
            raise ValidationError("Each source must be an object with file and sha256.")
        relative, path = relative_file(root, source.get("file"))
        observed = sha256(path)
        check_hash(source.get("sha256"), observed, relative)
        checked_sources.append({"file": relative, "sha256": observed, "bytes": path.stat().st_size})
    checked_attachments = []
    attachment_names = set()
    for attachment in attachments:
        relative, path = relative_file(root, attachment)
        if relative.casefold() in attachment_names:
            raise ValidationError(f"Duplicate attachment: {relative!r}")
        attachment_names.add(relative.casefold())
        checked_attachments.append({"file": relative, "sha256": sha256(path), "bytes": path.stat().st_size})
    specification = manifest.get("specification")
    if specification is not None and not isinstance(specification, dict):
        raise ValidationError("specification must be a metadata object.")
    report = {
        "schemaVersion": 1,
        "valid": True,
        "inputManifest": {
            "file": manifest_path.name,
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "bytes": len(manifest_bytes),
        },
        "placement": placement,
        "requireEmbeddedSrgb": require_srgb,
        "previewWidths": widths,
        "assets": checked_assets,
        "sources": checked_sources,
        "attachments": checked_attachments,
        "verificationLimits": LIMITS,
    }
    if specification is not None:
        report["specification"] = specification
    return report, root


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_review(report: dict) -> str:
    escape = html.escape
    def href(path: str) -> str:
        return escape(quote(path, safe="/"), quote=True)

    widths = report["previewWidths"]
    large_width = 1536 if 1536 in widths else widths[0]
    small_width = 360 if 360 in widths else widths[-1]
    sections = []
    for asset in report["assets"]:
        identifier = asset["id"]
        label = escape(f"{identifier} · {asset['locale']}")
        large = f"previews/{identifier}-{large_width}.png"
        small = f"previews/{identifier}-{small_width}.png"
        source = href(asset["outputFile"])
        profile_status = escape(asset["icc"]["status"])
        sections.append(
            f'<section><h2>{label}</h2><p>{asset["width"]} × {asset["height"]} · '
            f'{escape(asset["format"])} · {profile_status} · <a href="{source}">Original export</a></p>'
            f'<a href="{source}"><img class="large" src="{href(large)}" alt="{label}" '
            f'width="{large_width}"></a><h3>{small_width} px review</h3>'
            f'<img class="thumbnail" src="{href(small)}" alt="{label} thumbnail" '
            f'width="{small_width}" style="width:{small_width}px"></section>'
        )
    limits = "".join(f"<li>{escape(limit)}</li>" for limit in report["verificationLimits"])
    attachment_links = "".join(
        f'<li><a href="{href(attachment["outputFile"])}">{escape(attachment["file"])}</a></li>'
        for attachment in report["attachments"]
    )
    attachments = f'<h2>Included attachments</h2><ul>{attachment_links}</ul>' if attachment_links else ""
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>App Store creative assets — review</title><style>'
        '*{box-sizing:border-box}body{font:16px/1.5 system-ui,sans-serif;margin:32px auto;padding:0 24px;'
        'max-width:1600px;color:#222;background:#f5f5f5}section{margin:48px 0}img{height:auto;display:block}'
        '.large{max-width:100%;border-radius:12px}.thumbnail{max-width:none}a{color:#174ac6}'
        'h1,h2{line-height:1.2}p{overflow-wrap:anywhere}</style><body><h1>App Store creative assets</h1>'
        f'<p>Placement: {escape(report["placement"])}. Produced locally; inspect each locale and thumbnail.</p>'
        '<p><a href="delivery.zip">Download delivery ZIP</a> · '
        '<a href="input-manifest.json">Input manifest</a> · '
        '<a href="delivery-manifest.json">Delivery manifest</a> · '
        '<a href="checksums.sha256">Checksums</a></p>'
        + attachments
        + "".join(sections)
        + f'<h2>Verification limits</h2><ul>{limits}</ul></body></html>\n'
    )


def payload_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file())


def verify_zip(directory: Path, archive_path: Path, payload: list[Path]) -> None:
    expected = {str(path.relative_to(directory)): sha256(path) for path in payload}
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != sorted(expected):
            raise ValidationError("ZIP contents did not match the delivery payload.")
        for name, expected_hash in expected.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_hash:
                raise ValidationError(f"ZIP bytes differ for {name!r}.")


def build(manifest_path: Path, output: Path, root: Path | None = None) -> dict:
    report, root = validate(manifest_path, root)
    output = output.absolute()
    if os.path.lexists(output):
        raise ValidationError("Output already exists; choose a new output directory.")
    if not output.parent.is_dir():
        raise ValidationError("The output parent directory must already exist.")
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        shutil.copyfile(manifest_path, staging / "input-manifest.json")
        if sha256(staging / "input-manifest.json") != report["inputManifest"]["sha256"]:
            raise ValidationError("Input manifest changed while copying.")
        report["inputManifest"]["outputFile"] = "input-manifest.json"
        (staging / "assets").mkdir()
        (staging / "previews").mkdir()
        srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
        preview_profile = srgb.tobytes()
        preview_records = []
        for asset in report["assets"]:
            _, original = relative_file(root, asset["file"])
            output_file = f"assets/{asset['id']}{original.suffix.lower()}"
            shutil.copyfile(original, staging / output_file)
            if sha256(staging / output_file) != asset["sha256"]:
                raise ValidationError(f"Input changed while copying {asset['id']}.")
            asset["outputFile"] = output_file
            with Image.open(staging / output_file) as image:
                icc_bytes = image.info.get("icc_profile")
                rgb = (
                    ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes)), srgb, outputMode="RGB")
                    if icc_bytes is not None else image.copy()
                )
                for width in report["previewWidths"]:
                    height = max(1, round(image.height * width / image.width))
                    relative = f"previews/{asset['id']}-{width}.png"
                    rgb.resize((width, height), Image.Resampling.LANCZOS).save(
                        staging / relative, format="PNG", icc_profile=preview_profile
                    )
                    preview_records.append({
                        "assetId": asset["id"], "locale": asset["locale"], "file": relative,
                        **image_metadata(staging / relative, True),
                        "colorHandling": "converted-to-srgb" if icc_bytes is not None else "assumed-srgb-from-unverified-input",
                    })
        for attachment in report["attachments"]:
            _, original = relative_file(root, attachment["file"])
            relative = f"attachments/{attachment['file']}"
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
            if sha256(destination) != attachment["sha256"]:
                raise ValidationError(f"Attachment changed while copying {attachment['file']}.")
            attachment["outputFile"] = relative
        report["previews"] = preview_records
        report["state"] = "produced"
        write_json(staging / "delivery-manifest.json", report)
        (staging / "review.html").write_text(make_review(report), encoding="utf-8")
        payload = payload_files(staging)
        checksums = "".join(f"{sha256(path)}  {path.relative_to(staging)}\n" for path in payload)
        (staging / "checksums.sha256").write_text(checksums, encoding="utf-8")
        payload.append(staging / "checksums.sha256")
        archive_path = staging / "delivery.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(payload):
                entry = zipfile.ZipInfo(str(path.relative_to(staging)), date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                archive.writestr(entry, path.read_bytes())
        verify_zip(staging, archive_path, payload)
        archive_hash = sha256(archive_path)
        if os.path.lexists(output):
            raise ValidationError("Output appeared during the build; refusing to overwrite it.")
        staging.rename(output)
        return {**report, "outputDirectory": str(output), "zip": {"file": str(output / "delivery.zip"), "sha256": archive_hash, "byteEqualityVerified": True}}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "build"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("manifest", type=Path)
        subparser.add_argument("--root", type=Path, help="Asset root; defaults to the manifest's parent directory.")
        if command == "build":
            subparser.add_argument("--out", type=Path, required=True, help="New output directory in an existing parent.")
    arguments = parser.parse_args()
    try:
        report = (
            validate(arguments.manifest, arguments.root)[0]
            if arguments.command == "validate" else build(arguments.manifest, arguments.out, arguments.root)
        )
    except (ValidationError, OSError, ValueError, Image.DecompressionBombError, ImageCms.PyCMSError) as error:
        print(json.dumps({"valid": False, "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
