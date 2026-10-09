# Export, review and packaging

Read for production or a revision that changes delivered files. A discussion-only request does not require rendering, manifests or a ZIP.

## Confirm the placement

Check the live [creative asset specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/creative-assets-specifications) and [asset guidance](https://developer.apple.com/app-store/asset-best-practices/) for the intended format. The following is a dated reference, checked 9 October 2026, not a permanent validator preset:

| Still-image placement | Published dimensions | Formats |
| --- | --- | --- |
| Product-page header, 21:9 | 3840 × 1646 | PNG or JPEG |
| Search results, 3:2 | 1920 × 1280 minimum; 3840 × 2560 maximum | PNG or JPEG |
| Universal, 16:9 option listed for both | 5244 × 2950 | PNG |

Apple excludes alpha channels/transparency. Its guidance asks for product-relevant imagery and clear focal content, and excludes specific prices, discounts, website URLs, other marketplace branding and Apple-designated recognitions. Check the live policy for the actual creative; these notes do not replace it. Photorealism and app screenshots are not universal requirements for creative assets. Central focal placement helps accommodate crops; no numerical margin in this skill is an official safe area.

Choose the requested placement and formats rather than exporting every supported possibility. Preserve each exact pixel dimension from the selected specification; nominal ratios may involve rounding. Record its source/check date with the production story. Our helper requires an embedded sRGB profile by default to make color checks reproducible; that is a delivery convention, not an assertion that Apple mandates embedded ICC metadata.

## Verify appearance and provenance

- Inspect the original assets, final composition, every distinct localization and the small preview. Check recognizable branding, exact case, font loading and glyphs, headline fit, meaningful contrast, key-detail geometry and the intended crop. UI captures remain faithful and uniformly scaled.
- Label safe areas and simulated overlays by origin: current Apple template, observed preview, user constraint or estimate. A local review page does not prove Apple's final presentation.
- Verify image format, dimensions, RGB color, alpha absence, color profile and source/export hashes. Source provenance and a valid file are independent of visual quality.
- Revisions refresh the affected previews, review labels/links, manifests, checksums and archives. Compare hashes for approved outputs outside the revision scope. Do not leave old favorites labeled as selected.

Keep source and output references in a project-owned manifest. Record original captures, icon/fonts and their license sources, generated masters and edits, locale/copy decisions, and any unresolved capture or rendering limitation. Keep private product assets and machine paths out of a reusable public skill package.

## Optional portable helper

`scripts/asset_pack.py` uses Python 3.10+, Pillow and Pillow's ImageCms support. It validates finished static images, creates aspect-preserving previews and an offline HTML review, then packages exact input image bytes. It does not render creative compositions, translate UI, check safe-area geometry, consult Apple, or decide that artwork is visually approved. An existing project renderer/packager can remain authoritative; the helper is optional.

Place the following structure in a project manifest, adjusting sizes and paths to the verified brief. Extra project story fields can stay in that manifest. `file` paths resolve relative to the manifest folder unless `--root` supplies a different asset root.

```json
{
  "schemaVersion": 1,
  "placement": "search-results",
  "specification": {
    "url": "https://developer.apple.com/help/app-store-connect/reference/app-information/creative-assets-specifications",
    "checkedAt": "2026-10-09"
  },
  "requireEmbeddedSrgb": true,
  "previewWidths": [1536, 360],
  "assets": [
    {
      "id": "search-en-US",
      "locale": "en-US",
      "file": "out/en-US/search-results.png",
      "width": 3840,
      "height": 2560
    }
  ],
  "sources": [],
  "attachments": ["story.json", "provenance.json"]
}
```

- `placement`: `header`, `search-results` or `universal`. Dimensions are explicit per asset, so the helper follows updated requirements without treating an old preset as policy.
- `assets`: at least one image, with unique filename-safe `id`, `locale`, relative `file`, exact positive integer `width`/`height`, and optional `sha256` to check an existing output lock.
- `sources`: optional objects with relative `file` and expected `sha256`. They verify capture/brand bytes; they do not prove the production renderer used those bytes. Sources are not copied into the delivery unless explicitly attached.
- `attachments`: optional list of specific project files. Include only documents needed for handoff; no folder-wide sweep or inferred upload. File paths must remain within the asset root, including symlink resolution.
- `previewWidths`: optional positive widths, default `[1536, 360]`. These describe review images, not Apple export formats. Choose values appropriate to the placement.
- `requireEmbeddedSrgb`: defaults to `true`. If an established pipeline deliberately supplies no ICC, setting `false` permits that omission and reports color verification as unresolved. Invalid or identifiable non-sRGB profiles still fail. Resolve that color uncertainty before claiming verified sRGB delivery.

Run from any directory with the installed skill's actual path:

```sh
python3 /path/to/app-store-creative-assets/scripts/asset_pack.py validate /path/to/project/pack.json
python3 /path/to/app-store-creative-assets/scripts/asset_pack.py build /path/to/project/pack.json --out /path/to/project/delivery-r2
```

Use `--root /path/to/project` when the manifest lives in a separate source folder. Validation is read-only. Build requires a new output directory inside an existing parent and never rewrites the input images; use a new revision directory for each rebuilt pack. It validates all inputs before publishing the completed output directory. Errors return a nonzero exit code and JSON diagnostics.

The result contains copied images, requested previews, `review.html`, `delivery-manifest.json`, the byte-identical `input-manifest.json`, explicit attachments, `checksums.sha256` and `delivery.zip`. The review links the manifest, attachments and ZIP; the input manifest preserves extra project fields and the original path references. Rebuilding from it still needs the original asset root. Open the generated review and inspect its images at the displayed sizes. The archive is verified against its payload; the output manifest records what was checked and what still needs visual or provider review. Image hashes establish identity, not capture freshness or legal/licensing status.

## Handoff

Provide requested exports, the review path, useful package, retained editable source and relevant limits. An uploaded asset, an Apple-approved asset and an assigned/published placement are different states. For authorized release work, follow the app's existing tooling and verify the actual locale/placement and provider state. A produced pack alone does not authorize upload or any later release action.
