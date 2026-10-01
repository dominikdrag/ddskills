# Review and delivery

Use this reference for screenshot production, visual review, source limitations, and release handoff. Scale the checks to the requested change; a copy review does not require building the app or packaging new files.

## Source hierarchy

- The user's accepted direction governs creative choices. Current product sources and authentic captures constrain claims.
- Use Apple's current [product-page guidance](https://developer.apple.com/app-store/product-page/), [asset best practices](https://developer.apple.com/app-store/asset-best-practices/), and [screenshot specifications](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/) for platform constraints. Confirm relevant device classes, dimensions, formats, and locale requirements against the intended release configuration when producing exports; do not assume a past project's sizes still apply.
- If the workspace supplies `AppStorePositioning.md` or `AppStoreScreenshotCopy-PaulSolt.md`, read them for positioning and copy guidance. They are optional local references, not dependencies required to install this skill. Their useful principles are reflected in the entrypoint: headline-first drafting, a meaningful sequence, authentic product evidence, and thumbnail readability.
- The copy checks draw on [Paul Solt's screenshot copy review](https://x.com/PaulSolt/status/2037591726227902555), summarized in the supplied notes alongside [DesignerAnts' work](https://www.designerants.com/work). Keep these practitioner sources distinct from Apple's platform constraints.
- Practitioner advice suggests treatments to test. Do not promote reported conversion lifts, exact ranking weights, gallery-view percentages, fixed UI ratios, or screenshot OCR claims into platform facts. Verify any such claim that the work actually needs.

## Capture and framing

Record original capture paths, hashes, dimensions, appearance, source type, and known version/date context. Preserve original images. Identify populated example data as demo data where relevant; it is not customer evidence.

Use the [runtime capture workflow](runtime-capture.md) to acquire screenshots or audit sources before production. Inspect the raw capture before the device frame or marketing artwork can hide missing materials or system UI.

| Source | What it establishes | What still needs checking |
| --- | --- | --- |
| Current runtime screenshot | Pixels captured from the running app on a simulator or device | Build, state, materials, appearance, and suitability for the intended release |
| Native snapshot/reference render | App view code rendered by a test or offscreen harness; a design reference | Not a production screenshot substitute: it may force plain fills, omit system chrome, or bypass the live compositor |
| Retained older runtime capture | The interface as it was captured then | Provenance, visible text, controls, materials, and release compatibility; it cannot satisfy a request for fresh captures |
| Newly rendered marketing artwork | A new composition/export | It does not establish that its embedded app capture is fresh |

A source-code comparison can support feature consistency but does not turn a reference render into a runtime capture. If capture fails, report the gap and keep the affected set incomplete. A different supported state still needs a real runtime capture. References may support an explicitly requested mockup, but disclosure of their limitations alone does not make them suitable substitutes for the requested finished screenshots. Retry when there is a concrete recovery path, rather than repeatedly running an unchanged failing environment.

For complete-device compositions:

- Scale the whole captured viewport uniformly. Avoid stretching it to a new export ratio; adapt the surrounding canvas or framing instead.
- Keep the phone, side buttons, and meaningful content inside the intended canvas. Check frame geometry, screen aperture, headline clearance, and safe areas visually.
- A hardware camera cutout may belong to the surrounding device frame. Inspect whether it is already present, avoid duplicating it, and do not cover app content. Never paint in a clock, signal bars, controls, or other missing software chrome. If the source cannot fit a truthful frame, obtain a suitable capture or revise the treatment.
- Real light and dark sources must be inspected separately. Preserve their pixels apart from uniform scaling and the chosen device aperture; do not invent one appearance from the other.
- A recovery suggestion, selection, or confirmation prompt is not proof that the user accepted it or completed the action. Align the headline with what is actually shown.

## Visual review

Inspect every distinct finished composition at full size, then the ordered contact sheet and small previews around 160–200 pixels wide. Thumbnail width is a useful local review convention, not an Apple specification.

Check that the opening makes the app understandable, each later frame adds something, and the captions alone tell a coherent story. Check actual line breaks, font loading, contrast, UI authenticity, whole-phone bounds, and visual consistency. A contact sheet alone cannot reveal all UI defects. A DOM bounds check alone cannot establish good typography or legibility.

For resized exports, verify every required file's dimensions, image mode, transparency requirements, and proportions. Visually inspect representative variants and any composition whose layout changes. Review localized copy in its rendered form; fitting the English source does not establish that a translation fits.

## Reproduction and package

Prefer one editable story/manifest for copy, order, source references, and variants. Use it to generate dependent material rather than hand-maintaining copies of headlines. Keep renderer/template configuration reproducible without embedding machine-specific paths or credentials in the reusable skill.

A useful production delivery includes editable source, original captures or resolvable provenance, ordered exports, a full-size review route, contact/thumbnail sheets, and a delivery note. Add a ZIP when requested or useful. Do not create empty formats or extra variants to satisfy a checklist.

Verify expected files, dimensions and image properties, referenced fonts and licenses, links, source/export hashes, and caption/order parity. If packaging an archive, check its integrity and that archived exports match the reviewed files. Keep raw logs and scratch evidence wherever the repository requires; retain concise provenance and results with the deliverable.

After a scoped edit, regenerate its dependent outputs and repeat affected checks. Compare exports intended to remain unchanged against their prior hashes, and inspect the source diff for unrelated layout changes; a whole-set rerender can drift even when only copy was edited. Do not broaden into unrelated app builds, redesigns, release actions, or tests once evidence is sufficient. Preserve approved baselines and any collaborator's active files.

## Release and measurement

Use the app's existing release workflow for any authorized handoff or upload. Keep generated artwork, reviewed exports, approval, upload, and publication distinct. Rendering or packaging does not grant permission to modify a live listing.

For an experiment, consult current [Product Page Optimization guidance](https://developer.apple.com/app-store/product-page-optimization/). Record the baseline, treatment, traffic context, metrics, and limitations. A combined copy/layout change measures the package; it cannot isolate the effect of one caption. Recommend a candidate based on clarity, and reserve claims of conversion improvement for appropriate observed evidence.
