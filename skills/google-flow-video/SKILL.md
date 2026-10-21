---
name: google-flow-video
description: Generate and download videos in Google Flow using Google Chrome from existing prompts and reference images. Use for new clips, resuming queued generations, or recovering downloads; use video-prompting for prompt-only work.
---

# Google Flow Video

Turn an existing scene prompt and its references into a downloaded, checked raw clip. Follow the project's workflow for episode selection, storage and records. Keep app facts, schedules and deployment details in that project.

## Establish the run

Read the applicable project instructions and any Flow workflow they name. Resolve each requested clip's prompt, reference roles, destination, settings, attempt budget and existing provider project or output. For a batch, identify the clips still needed before spending credits.

Explicit user settings take precedence over project defaults and older prompt headings. When neither supplies settings, start with **10 seconds, 720p, Omni 1.1 Flash, 9:16 and x1**, subject to their presence in Flow's current controls. The default budget is one generation per requested clip; a larger budget requires user authorization. Reading a fallback or retry suggestion does not increase the budget.

Inspect the actual reference images. Distinguish a first frame, last frame and Ingredients reference. Preserve an existing accepted prompt. If a longer duration only needs a longer closing hold, save a dated prompt variant with that change and keep dialogue intact. Use `video-prompting`, when available, for a substantive prompt revision.

## Reconcile before generating

Check retained clips, download records and known Flow projects:

- A valid existing clip satisfies a request for the remaining clips. Report a mismatch instead of silently replacing it.
- A completed provider output with a missing local file needs a download, not another generation.
- An in-flight or uncertain submission needs inspection in its existing project before any new submission.

Use one project per clip unless continuing its existing project or the user requests another organization. Record the project URL, exact prompt/reference inputs and intended settings before submission so an interrupted run can resume. Record confirmed submissions and uncertain outcomes separately; reconcile either against Flow before spending again.

## Generate in Chrome

Use the available Computer Use browser tools in Google Chrome. Read [Chrome and Flow mechanics](references/chrome-flow.md) when browser discovery, native Chrome, file upload or downloads need guidance. Work from fresh UI observations; selectors and accessibility indices belong to the current state.

1. Open the clip's project and attach the inspected references in their intended roles. Use Frames for a specified first/last frame and Ingredients for identity/style guidance; confirm the selected model supports the required mode.
2. Set and visibly verify model, mode, duration, resolution, aspect ratio, output count and displayed credit cost. If a requested option is unavailable, report it and continue independent clips; obtain a changed instruction before substituting a model or setting.
3. Fill the exact prepared prompt and verify the field contains it. Save the run record, then submit once. Confirm a queued, generating, completed or failed provider state before moving on.
4. Wait for this submission while doing independent work. A failed or rejected submission consumes the attempt. Preserve the provider reason and report it; further generations need an available authorized attempt. If Flow rejects a concept, any proposed revision must comply with the policy rather than disguise the same request.

Generation, completed preview and downloaded file are separate milestones. An unexpected navigation or an uncertain button click is a reason to inspect the project, not to resubmit.

## Download and verify

Download the requested original resolution through Flow's download control. Check the browser reports completion and the actual local file exists. Keep the provider bytes intact when retaining the clip at the project's destination; verify the source and retained copy have the same SHA-256. Keep raw scenes distinct from assembled final exports.

Use `ffprobe` for actual video duration, dimensions, frame rate and audio streams, and `ffmpeg -v error -i <clip> -f null -` for a full decode when those tools are available. Compare the video stream with the requested duration and aspect ratio: a 10-second video can legitimately have a 10.005-second audio/container duration. For vertical 720p at 9:16, expect 720 by 1280. Report unavailable verification rather than infer a pass.

Play the clip and inspect its beginning, action and ending against the brief: continuity, speakers, text, motion and final pose. Technical audio presence or a playing UI does not prove dialogue accuracy, listening quality or lip sync. State what was actually assessed, and keep any remaining creative review explicit. Record deviations while respecting the generation budget.

## Retain and hand off

Follow the project's record schema. Include project/media identity, actual submitted prompt and reference hashes/roles, observed settings, confirmed attempts, provider failure or completion state, output path/hash/metadata and concise verification findings. Keep scratch frames and browser logs outside project records unless the project requests them.

Run the project's inventory, packaging and tracker updates within the user's authorized scope. Publishing a tracker or social post, scheduling and changing accounts each retain their own authorization boundary; creating clips alone grants none of them.

Deliver clickable file paths or the available native video preview, actual settings, attempt counts and material deviations. Call a clip generated and downloaded only after verifying the file; reserve assembled, approved and published for evidence of those states.
