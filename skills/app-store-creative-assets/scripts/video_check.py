#!/usr/bin/env python3
"""Check rendered creative-asset videos against their story and write review previews.

Requires Python 3.10+, Pillow, and ffmpeg/ffprobe on PATH. Videos are read, never rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from PIL import Image


class ValidationError(ValueError):
    """The story or a video does not satisfy the declared delivery contract."""


# Apple's video limits as read on 21 October 2026 (500 MB from App Store Connect's matched spec, not the docs page).
DEFAULT_LIMITS = {"fps": [30, 60], "seconds": [5, 30], "maxBytes": 500_000_000}
EXTENSIONS = {".mov", ".m4v", ".mp4"}
# Status-bar glyph regions across the top band: left, centre and right, as fractions of the width.
BAND_REGIONS = [(0.0, 0.234), (0.383, 0.617), (0.766, 1.0)]
LIMITS = [
    "File checks do not establish visual quality, legibility, claim accuracy, the displayed crop, or Apple approval.",
    "The decoded seam figure is a sanity read; the renderer's frame-0 comparison is the seam gate.",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timecode_seconds(code: str, fps: int) -> float:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2}):(\d{2})", code)
    if not match:
        raise ValidationError(f"posterTimeCode must be HH:MM:SS:FF, got {code!r}.")
    h, m, s, f = (int(part) for part in match.groups())
    if m > 59 or s > 59 or f >= fps:
        raise ValidationError(f"posterTimeCode out of range: {code!r}.")
    return h * 3600 + m * 60 + s + f / fps


def load_story(path: Path) -> dict:
    story = json.loads(path.read_text(encoding="utf-8"))
    canvas = story.get("canvas") or {}
    for key in ("width", "height"):
        if type(canvas.get(key)) is not int or canvas[key] <= 0:
            raise ValidationError(f"canvas.{key} must be a positive integer.")
    if type(story.get("fps")) is not int or not isinstance(story.get("loopSeconds"), (int, float)):
        raise ValidationError("fps (integer) and loopSeconds are required.")
    if not story.get("copy"):
        raise ValidationError("copy needs at least one locale.")
    story["limits"] = {**DEFAULT_LIMITS, **story.get("limits", {})}
    story["posterTimeCode"] = story.get("posterTimeCode", "00:00:00:00")
    if timecode_seconds(story["posterTimeCode"], story["fps"]) >= story["loopSeconds"]:
        raise ValidationError("posterTimeCode must fall inside the loop.")
    return story


def probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-count_frames", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def decode(path: Path, times: list[float], fps: int) -> dict[float, Image.Image]:
    """Decode the frames shown at each time (frame index round(t * fps)) as RGB, BT.709 limited range as tagged."""
    indices = sorted({round(t * fps) for t in times})
    select = "+".join(f"eq(n\\,{n})" for n in indices)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf",
                        f"select='{select}',scale=in_color_matrix=bt709:in_range=tv,format=rgb24",
                        "-fps_mode", "passthrough", str(Path(tmp) / "%05d.png")], check=True)
        images = [Image.open(file).convert("RGB") for file in sorted(Path(tmp).glob("*.png"))]
    if len(images) != len(indices):
        raise ValidationError(f"{path.name}: decoded {len(images)} frames, wanted {len(indices)}.")
    by_index = dict(zip(indices, images))
    return {t: by_index[round(t * fps)] for t in times}


def luminance(rgb: tuple[float, float, float]) -> float:
    def linear(channel: float) -> float:
        channel /= 255
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(value) for value in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mean_rgb(image: Image.Image, box: tuple[int, int, int, int]) -> tuple[float, float, float]:
    pixels = list(image.crop(box).resize((64, 8)).getdata())
    return tuple(sum(p[i] for p in pixels) / len(pixels) for i in range(3))


def mean_abs_diff(a: Image.Image, b: Image.Image) -> float:
    size = (480, max(1, round(480 * a.height / a.width)))
    pa, pb = list(a.resize(size).getdata()), list(b.resize(size).getdata())
    return sum(abs(x[i] - y[i]) for x, y in zip(pa, pb) for i in range(3)) / (len(pa) * 3)


def scaled(image: Image.Image, width: int) -> Image.Image:
    return image.resize((width, round(width * image.height / image.width)), Image.LANCZOS)


def check_video(story: dict, locale: str, path: Path, previews: Path, prefix: str, widths: list[int]) -> tuple[dict, list[str]]:
    W, H, fps, loop, limits = story["canvas"]["width"], story["canvas"]["height"], story["fps"], story["loopSeconds"], story["limits"]
    info = probe(path)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ValidationError(f"{path.name}: no video stream.")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    duration = float(info["format"]["duration"])
    frames = round(loop * fps)
    size = path.stat().st_size
    checks = {
        f"size {W} x {H}": (video["width"], video["height"]) == (W, H),
        f"{fps} fps constant": video["r_frame_rate"] == f"{fps}/1" and video["avg_frame_rate"] == f"{fps}/1",
        "frame rate allowed": fps in limits["fps"],
        f"length {limits['seconds'][0]}-{limits['seconds'][1]} s": limits["seconds"][0] <= duration <= limits["seconds"][1],
        f"{frames} frames": int(video.get("nb_read_frames", -1)) == frames,
        "extension .mov/.m4v/.mp4": path.suffix.lower() in EXTENSIONS,
        "H.264 yuv420p": video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p",
        "BT.709 tags": all(video.get(k) == "bt709" for k in ("color_primaries", "color_transfer", "color_space")),
        f"under {limits['maxBytes']} bytes": size <= limits["maxBytes"],
    }
    problems = [f"{locale}: {name}" for name, ok in checks.items() if not ok]
    base = {"file": str(path), "sha256": sha256(path), "bytes": size, "durationSeconds": duration, "checks": checks,
            "video": {k: video.get(k) for k in ("codec_name", "profile", "level", "width", "height", "pix_fmt", "r_frame_rate",
                                                 "avg_frame_rate", "nb_read_frames", "color_primaries", "color_transfer",
                                                 "color_space", "color_range", "bit_rate")},
            "audio": [{k: s.get(k) for k in ("codec_name", "sample_rate", "channels", "bit_rate")} for s in audio]}
    if not all(checks[k] for k in list(checks)[:5]):
        return base, problems  # frame times assume the declared size, rate and length

    band =(story.get("guides") or {}).get("statusBand", {}).get("height", 0)
    band_times = [i * 0.5 for i in range(int(loop * 2))] if band else []
    sheet_times = [round(loop * i / 10, 3) for i in range(10)]
    poster_time = timecode_seconds(story["posterTimeCode"], fps)
    last = (frames - 1) / fps
    images = decode(path, sorted(set(band_times + sheet_times + [0, 1 / fps, last, poster_time])), fps)

    # White status-bar glyphs over the top band need at least 3:1 contrast in every sampled frame.
    worst = None
    for t in band_times:
        for left, right in BAND_REGIONS:
            ratio = 1.05 / (luminance(mean_rgb(images[t], (round(left * W), 0, round(right * W), band))) + 0.05)
            worst = ratio if worst is None else min(worst, ratio)
    if worst is not None and worst < 3:
        problems.append(f"{locale}: status band contrast {worst:.1f}:1 is under 3:1")

    previews.mkdir(parents=True, exist_ok=True)
    written = []
    for width in widths:
        target = previews / f"{prefix}{locale}-poster-{width}.png"
        scaled(images[poster_time], width).save(target, optimize=True)
        written.append(target.name)
    tile = min(768, W)
    tiles = [scaled(images[t], tile) for t in sheet_times]
    sheet = Image.new("RGB", (tile * 2 + 16, (tiles[0].height + 16) * 5), (255, 255, 255))
    for i, image in enumerate(tiles):
        sheet.paste(image, ((i % 2) * (tile + 16), (i // 2) * (tiles[0].height + 16)))
    target = previews / f"{prefix}{locale}-frames.png"
    sheet.save(target, optimize=True)
    written.append(target.name)

    return {
        **base,
        "statusBandWorstContrast": None if worst is None else round(worst, 1),
        "loopSeamMeanAbsDiff": round(mean_abs_diff(images[last], images[0]), 3),
        "ordinaryStepMeanAbsDiff": round(mean_abs_diff(images[0], images[1 / fps]), 3),
        "posterTimeCode": story["posterTimeCode"], "frameSheetTimes": sheet_times, "previews": written,
    }, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("story", type=Path)
    parser.add_argument("--video", required=True, help="path with a {locale} placeholder, as given to render_video.mjs --out")
    parser.add_argument("--previews", required=True, type=Path)
    parser.add_argument("--prefix", default="", help="preview filename prefix, such as an option ID and a dash")
    parser.add_argument("--preview-widths", default="1536,1320", help="poster widths in pixels, comma-separated")
    parser.add_argument("--manifest", type=Path, help="write the full check record here")
    args = parser.parse_args(argv)
    try:
        story = load_story(args.story)
        widths = [int(w) for w in args.preview_widths.split(",")]
        if "{locale}" not in args.video and len(story["copy"]) > 1:
            raise ValidationError("--video needs {locale} for more than one locale.")
        record = {"story": str(args.story), "canvas": story["canvas"], "fps": story["fps"], "loopSeconds": story["loopSeconds"],
                  "posterTimeCode": story["posterTimeCode"], "locales": {}, "problems": [], "limits": LIMITS}
        for locale in story["copy"]:
            path = Path(args.video.replace("{locale}", locale))
            if not path.is_file():
                raise ValidationError(f"Missing video for {locale}: {path}")
            record["locales"][locale], problems = check_video(story, locale, path, args.previews, args.prefix, widths)
            record["problems"] += problems
    except (ValidationError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=1), file=sys.stderr)
        return 1
    if args.manifest:
        args.manifest.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {locale: {k: entry.get(k) for k in ("bytes", "statusBandWorstContrast", "loopSeamMeanAbsDiff", "ordinaryStepMeanAbsDiff")}
               for locale, entry in record["locales"].items()}
    print(json.dumps({"ok": not record["problems"], "problems": record["problems"], "locales": summary}, indent=1))
    return 1 if record["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
