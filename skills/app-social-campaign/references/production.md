# Production and delivery

## Choose a workable pipeline

Reuse the project's working social renderer when it fits. Otherwise, precise HTML/CSS artwork plus a browser renderer is a useful local pipeline. Art direction remains app-specific. The helpers below are deliberately independent: use only those that help the requested deliverable; they are not a new application framework.

Discover available runtimes first. Where available, `load_workspace_dependencies` locates bundled Node, Python, Playwright, Sharp, and Pillow. Otherwise inspect installed runtimes/packages. The scripts do not install software or depend on an old worktree. Use discovered executable paths. For Node, set `NODE_PACKAGES` to the directory containing `playwright` and `sharp`, and `CHROME_BIN` to a browser executable when a bundled browser is unavailable. For Python, use a runtime with Pillow. Put FFmpeg and ffprobe on PATH for video work. If tooling is missing, use an available suitable editor or report the specific production gap; do not call a plan a completed export.

Use one campaign directory with local relative links. A practical structure:

```text
campaign/
  app-profile.md
  campaign-plan.md
  observation-log.md
  publishing-order.md
  review.html
  assets/                 Original screenshots, permitted fonts, logo
  source/                 Copy, layout, render specs, source references
  posts/<id>/             Artwork, video, caption, accessible text, Stories
  profile/                Optional bio/icon/Highlight assets
  QA.md
  campaign.zip
```

Preserve a copy of the used helper scripts or exact helper version with the campaign's editable source. Do not rely solely on temporary caches. Include asset provenance and permission/license information where needed.

## Artwork export

Create app-specific HTML artboards. Use real screenshot files inside device frames or accurately cropped detail windows. Fonts should be local and fully loaded before capture. Compose editorial explanations as their own layer outside screenshot UI.

1080 × 1350 feed art and 1080 × 1920 vertical art are useful production choices. They are not a claim about the platform's current required or only accepted dimensions. Verify current official constraints when they affect the task and inspect the actual upload preview when publishing. Keep essential copy away from likely interface overlays, and use large type that survives a phone-sized preview.

`render_artwork.cjs` captures exact artboard elements, exports RGB PNGs, checks dimensions and text escaping the artboard, and preserves locked files. It does not detect every overlap, tiny text, wrong font, or misleading UI. Inspect its actual output.

Run:

```sh
node /path/to/app-social-campaign/scripts/render_artwork.cjs /path/to/campaign source/render-spec.json
```

Example `source/render-spec.json`:

```json
{
  "html": "source/artwork.html",
  "approvedHashes": "source/approved-hashes.json",
  "report": "source/render-report.json",
  "items": [
    {"selector": "#post-01-slide-01", "file": "posts/01/01.png", "width": 1080, "height": 1350, "textSelector": "h1,p,.number,.steps,.footer"}
  ]
}
```

`approvedHashes` is optional. Its JSON maps relative file paths to SHA-256 strings. A locked output is verified and left byte-identical; to revise approved artwork, deliberately use a new version path or update the lock only within the user's requested revision. Never reset a lock simply to make verification pass.

Create contact sheets and inspect each final image at full size and around 360 px wide. Ensure copy, numbers, bullets, conditions, image descriptions, and numbered publishing order agree. Rerun only affected exports after a text/layout fix.

## Reels

Choose a treatment that can actually be produced: authorized screen recording, live footage, or motion typography with real screenshots. State when a planned treatment changes. Do not animate a screenshot to imply that an action was recorded or succeeded.

Keep a timed scene list. Allow enough time to read the copy. A five-scene Reel need not have five equal durations. Use restrained motion when small product UI is visible. Keep core meaning understandable with sound off. Provide a scene description and a text equivalent; if there is speech, provide accurately timed subtitles. Describe a silent/text-based Reel's SRT as on-screen text, not a speech transcript.

`encode_reel.py` accepts same-sized source frames and encodes a gentle zoom/dissolve MP4. It verifies a full decode and writes a technical report. It does not produce an audio track or determine audio rights. An optional local audio file is looped/trimmed with fades; choose it intentionally and record its source/rights. Omitting audio produces a silent Reel; disclose that treatment.

```sh
python3 /path/to/app-social-campaign/scripts/encode_reel.py /path/to/campaign source/reel-04.json
```

Example:

```json
{
  "output": "posts/04/reel.mp4",
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "transition": 0.4,
  "zoom": 0.025,
  "scenes": [
    {"file": "source/reel-04/01.png", "seconds": 4},
    {"file": "source/reel-04/02.png", "seconds": 5}
  ]
}
```

Optional keys: `audio` (relative file path), `approvedHashes` (same lock format). Duration is the sum of scene durations minus each transition overlap. The example lasts 8.6 seconds. Frame dimensions must match the configured output. Existing videos are not replaced without `--replace`; locked output paths are always rejected. Keep user-approved originals when making a new version.

The encoder uses H.264/yuv420p with BT.709 color handling; audio, when present, is AAC stereo at 48 kHz. Verify actual metadata rather than inferring it from arguments. Inspect decoded scene frames, transitions, color, reading pace, cover crop, full playback, and audio if present. Technical level/decode checks do not establish perceptual sound quality.

## Review board and delivery pack

`campaign_pack.py` renders a neutral, brand-color-aware board from finished media and consistent text. The board supports week filters, image enlargement, caption copy, and inline video. It also writes text sidecars and publishing order. It does not generate campaign concepts or art. Adapt the board when the campaign needs a different review experience.

Use a separate project-specific authoring schema if useful, then adapt it into this small delivery manifest. Keep the authored content as the source of truth.

```json
{
  "schema_version": 1,
  "title": "App name — campaign idea",
  "phase": "sample",
  "language": "en",
  "summary": "The creative idea and what is ready to review.",
  "release_note": "D0 is the confirmed public release day. Nothing is scheduled.",
  "brand": {"background": "#F7F5EF", "text": "#262922", "accent": "#637451"},
  "documents": [{"label": "Campaign plan", "file": "campaign-plan.md"}],
  "extra_files": ["source/artwork.html", "source/artwork.css", "assets/screenshot.png", "QA.md"],
  "posts": [{
    "id": "01", "title": "A specific hook", "week": 1, "day": "D0",
    "format": "single", "status": "ready", "goal": "Introduce the problem",
    "caption": "The complete caption.",
    "publication_note": "Confirm the release and profile destination before posting.",
    "assets": [{"file": "posts/01/01.png", "type": "image", "role": "feed", "width": 1080, "height": 1350, "alt": "Describe all meaningful copy and visuals."}],
    "stories": []
  }]
}
```

Declare every production asset. Video assets use `type: "video"`, the dimensions, a scene description in `alt`, and an optional local `poster` path. Covers can be additional image assets with `role: "cover"`; they are not extra scheduled posts. Stories use the same media entry shape. Set `caption_limit` if the destination differs from the default 2,200 characters. Optional `approved_hashes` refers to the lock JSON. Add profile files, accessible video text/SRTs, native sticker instructions, fonts, all source scripts, plans, and QA evidence explicitly through `extra_files` or `documents` so the pack is reproducible.

```sh
python3 /path/to/app-social-campaign/scripts/campaign_pack.py /path/to/campaign source/delivery.json --check-only
python3 /path/to/app-social-campaign/scripts/campaign_pack.py /path/to/campaign source/delivery.json
python3 /path/to/app-social-campaign/scripts/campaign_pack.py /path/to/campaign source/delivery.json --zip
```

All inputs are local paths inside the campaign root. ZIP creation rejects unfinished listed posts. A sample delivery should list only finished sample posts and set `phase: "sample"`; put planned later concepts in the linked campaign plan. `ready` means produced for review, not user-approved, scheduled, or published.

The pack uses an explicit file list, not a recursive archive of the repository. It validates RGB dimensions, video metadata, captions, approved hashes, source/document existence, and ZIP CRC/hashes. It does not validate publication claims, full video decoding, every URL in arbitrary linked HTML, or actual browser usability.

Before delivery, exercise the rendered board in a browser: all assets load, each filter shows the intended posts, images open, captions copy, videos play and stop appropriately, and mobile has no horizontal overflow. Check local links and any distribution-specific crop/format requirements. Include the exact checks and remaining boundaries in QA.md. Regenerate the archive after final edits so it contains the final files, and verify the download points to that archive.
