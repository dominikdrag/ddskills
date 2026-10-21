# Header and search-results video

Read when producing or revising a header or search-results video. Compose each frame by the placement's reference ([headers](headers.md) or [search results](search-results.md)); this file adds motion, rendering, checks and delivery. The method has shipped for headers; for search results, preview at 360 px and keep the status-band guide only where the placement shows an overlay.

## Apple's limits

A dated reference, checked 21 October 2026 on the [creative asset specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/creative-assets-specifications) and [asset best practices](https://developer.apple.com/app-store/asset-best-practices/). Recheck before production and record the URL and date in the story.

| Placement | Size | Rate | Length | Files |
| --- | --- | --- | --- | --- |
| Header | 21:9, 3840 × 1646 | 30 or 60 fps | 5–30 s | .mov, .m4v, .mp4 |
| Search results | 3:2, 1920 × 1280 to 3840 × 2560 | 30 or 60 fps | 5–30 s | .mov, .m4v, .mp4 |

- Videos loop continuously. Search results are always muted; the product page starts muted and people can unmute. Every video works silently.
- The docs name no codec, file size or audio rule. App Store Connect's matched header spec (20 October 2026) read "audio not required" and allowed up to 500 MB.
- Best practices: the poster frame is the first image people see; start strong; avoid quick cuts and fast-moving visuals; loop without visible jumps.
- App Review Guideline 2.3.14: creative assets carry no unverifiable product claims and no specific or discounted pricing.

## Plan the loop

- **Show the product doing its job.** Motion earns its place by demonstrating the mechanism: a plan building, records filling in, a real recording of the key moment. A deck of static screens shuffling was rejected for not showing what the app does. When the user asks for options, vary the style (real footage, motion graphic, illustrated scene) and say in one line what each shows.
- **Loop by construction.** The whole picture is a pure function of `t` modulo the loop length. Sequences end where they start: a deck returns to its first card, a build-up rolls back, a float follows `sin(2πt / loop)`. Footage that cannot loop crossfades its first frame back in over the last ~0.6 s.
- **Pace for reading.** Hold each finished state about 2–3 s, move with eased transitions of about 0.5–1.3 s, and cut nothing.
- **Choose the poster frame.** Pick the moment that shows a finished state (the completed plan, the filled chart, a full card) and record it as `posterTimeCode` (`HH:MM:SS:FF`). Frame 0 serves only when it already shows that state. The poster is set at upload, not baked into the file.
- **Keep copy offer-free.** The headline carries no price, offer, trial, discount or number. Numbers that belong to sourced example data (a sample plan's times, an example week's count) may appear in labelled artwork.
- **Keep sources true.** Real captures move as whole cards; their pixels are never redrawn. Real footage may be trimmed, scaled, colour-converted and crossfaded at the wrap, nothing more. Drawn charts and illustrations carry no status bar or app chrome, so they cannot pass for app screens.

## Build the page

Each option is one HTML page driven by a story JSON. The page exposes:

- `#art`: the artboard element, exactly the canvas size.
- `setup(story, locale, runtime)`: builds the frame, waits for fonts (`document.fonts.load`, then `document.fonts.ready`), decodes images, fits the copy, and returns facts worth recording, such as the fitted font size. `runtime` carries `framesUrl` and `frameCount` for footage and `prescaled[key]` (`url`, `width`, `height`) for prescaled images.
- `renderAt(t)`: sets every moving property from `t` in seconds; it may be async when it swaps an image. Motion comes only from `t`: no CSS animations, transitions, timers or clock reads.
- `layout()`: boxes relative to `#art` (`x`, `y`, `right`, `bottom`): `headline` (`null` when textless), `lines` (one per headline line) and `items` (each placed or moving element with `id`, `opacity`, and optional flags `exiting`, `bleeds` for a planned crop past the canvas edge, `nearCopyOk` for an element allowed inside the copy clearance).

Story fields the scripts read; other fields pass through to the page:

| Field | Use |
| --- | --- |
| `canvas` `{width, height}`, `fps`, `loopSeconds` | Exact output, checked against `limits` |
| `posterTimeCode` | Poster previews; default `00:00:00:00` |
| `copy` `{locale: {lines, labels}}` | One video per locale; copy gate (labels may hold example numbers) |
| `offerWords` | Lowercase stems of free, trial, discount and offer in the story's other languages |
| `headline` `{left, width}` | Column check for each headline line |
| `guides.statusBand.height`, `guides.copyClearance` | Header status-bar band, an estimate (about 260 px of 1646 worked); copy clearance, default 40 px |
| `inputs` `[{file, sha256}]` | Hash-checked before rendering; paths relative to the story |
| `recording` `{file, start, duration, filter}` | Footage decoded to PNG frames at `fps` |
| `prescale` `{key: {file, width, height, crop}}` | Images cut and resized to their exact display size |
| `limits` `{fps, seconds, maxBytes}` | Override after a verified spec change |

## Render and check

The scripts need Node with `playwright-core` (set `NODE_PACKAGES` to its `node_modules`), a Chrome or Chromium binary in `CHROME_BIN`, ffmpeg with libx264, and Python 3.10+ with Pillow. Evidence stays outside the project.

1. **Stills.** Render a few moments per locale and settle the layout before a full render. Done when the stills pass and show the intended states.

   ```sh
   node /path/to/app-store-creative-assets/scripts/render_video.mjs story.json --page page.html --evidence /path/outside/project --stills 0,4,8
   ```

2. **Render.** Done when the renderer exits 0 for every locale.

   ```sh
   node /path/to/app-store-creative-assets/scripts/render_video.mjs story.json --page page.html \
     --out 'out/{locale}/3840x1646/header.mp4' --evidence /path/outside/project --report render-report.json
   ```

   It refuses mismatched input hashes and offer copy, checks the layout of every frame, compares the frame at `t = loopSeconds` with frame 0 (tolerating rasterisation noise), and encodes H.264 High, yuv420p, BT.709-tagged, CRF 14, 2 s keyframes, faststart. It adds a silent stereo AAC track by default, the form App Store Connect accepted; `--no-audio` omits it.

3. **Check.** Done when it exits 0 for every locale.

   ```sh
   python3 /path/to/app-store-creative-assets/scripts/video_check.py story.json \
     --video 'out/{locale}/3840x1646/header.mp4' --previews previews --manifest export-manifest.json
   ```

   It probes size, constant rate, frame count, length, codec, BT.709 tags and file size; samples the status band's contrast for white glyphs every 0.5 s; reports the decoded wrap (last to first frame) beside an ordinary step; and writes posters at the poster frame (1536 px for review, 1320 px for a 440 pt iPhone at 3×; add 360 for search results) and a ten-frame sheet.

4. **Watch.** Build a review page that plays each video as Apple does (`muted loop autoplay playsinline`), full width and in an iPhone-width frame, beside its poster and frame sheet. Done when you have watched two passes across the wrap and judged the poster at phone width for every locale.

## Why the scripts work this way

- Chrome rasterises a freshly painted layer slightly differently from a moving one, so the renderer draws the loop's last half second before frame 0.
- Chrome draws a downscaled image with a fast filter, then swaps in a sharper one a few frames later: a visible pop. Prescale every downscaled capture to its exact display size.
- ffmpeg drops embedded ICC profiles when prescaling; give it sRGB sources or convert them first.
- Simulator screen recordings are tagged Display P3. Convert while decoding, then scale: `colorspace=space=bt709:primaries=bt709:trc=srgb:range=tv:ispace=bt709:iprimaries=smpte432:itrc=srgb:irange=tv,scale=in_color_matrix=bt709:in_range=tv,format=rgb24`.
- ffmpeg 8 ignores output colour flags such as `-color_primaries` when frames carry their own properties; `setparams` in the filter chain sets the BT.709 tags.
- After hundreds of frames a few edge pixels rasterise differently, so the seam check compares pixels with a tolerance instead of bytes.
- At CRF 14, 16 s came to about 27 MB for a photographic scene and 3–8 MB for graphics.

## Deliver

Keep per option and locale: the video, `story.json`, `page.html`, provenance for every capture and footage clip, the render report, the check manifest, previews and checksums. Record the poster time code beside the files; the upload needs it.
