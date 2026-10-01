---
name: video-prompting
description: "Write, review, or improve prompts for video generation models. Use for turning scene briefs into prompts, adapting prompts to image inputs, or diagnosing prompt-related failures. Covers text-to-video and image-to-video; does not itself generate or publish footage."
---

# Video Prompting

Turn the user's visual intent into clear, executable scene direction. Preserve their chosen model, story, tone, dialogue and production constraints. This skill supports a generation workflow but does not require generation to complete a prompt-writing request.

## Establish the inputs

Reuse known context: model/version, host application, generation mode, input assets, duration, aspect ratio, intended viewer takeaway and audio requirements. Distinguish the host from the selected model; a service can expose several models with different controls.

Inspect supplied reference images when available. Identify whether each image is a first frame, an end frame or an identity/style reference. Those roles are not interchangeable. If an image cannot be inspected, state the assumption instead of describing it as seen.

Ask only when a missing choice materially changes the prompt. Otherwise draft with stated assumptions. An unspecified model need not block a general scene brief; label it model-neutral and leave unsupported settings unclaimed.

For model-specific syntax or capability questions, read the relevant section of [model notes](references/model-notes.md). Reuse official sources already verified in this task; otherwise check current first-party documentation before asserting support, limits or availability. If verification is unavailable, identify what remains uncertain and continue the independent creative work.

## Put direction in the right place

- **Text-to-video:** establish the subject, setting, framing and appearance as well as movement.
- **Image-to-video:** let the starting image carry existing appearance. Describe subject, camera and environmental motion. Add visual detail for something newly revealed or introduced; do not redundantly contradict the input image.
- **Reference-led generation:** say what each reference should preserve and describe the new scene. Do not treat an identity reference as a mandatory opening composition.
- **First/last frames:** describe the path between endpoints. Endpoint images do not specify an exact cut between two shots.
- **Settings:** keep duration, format, resolution and reference assignments separate from the paste-ready prompt when the tool exposes controls. Prose cannot override an unsupported setting.
- **Editing:** identify exact typography, cuts and sound timing that need timeline control. Honor a requested single-generation attempt; offer separate shots as a fallback instead of silently changing the deliverable.

## Write the shot

Describe what an observer can see: a subject does something, in a direction, at a pace, with an endpoint. Express emotion through suitable visible behavior. Separate subject movement from camera movement, and name what the camera reveals. Use a few compatible lighting/style choices that serve the brief.

A useful drafting order is framing → subject/action → setting → camera → look → sound. It is an organizing aid, not special model syntax. Use as much detail as the shot needs; do not enforce a universal word count, keyword order or JSON format.

Start with one main action and camera intention when exploring. Preserve deliberate choreography or multi-shot requests. For sequences, separate shot blocks and allow plausible time for each beat. Timestamps express desired pacing, not a guaranteed edit boundary.

For audio-capable modes, distinguish dialogue, ambience and effects. Keep approved dialogue exact, identify the speaker and delivery, and allow time for speech and reaction. Surface dialogue that cannot fit instead of quietly shortening it. Apply the selected model's negative-prompt and dialogue conventions; never copy a universal blacklist between models.

For worked examples or failure diagnosis, read the relevant section of [examples and iteration](references/examples-and-iteration.md). Keep brand and product facts in the project's own brief. When representing an actual product, use authentic captures and editing for UI; do not invent behavior or successful actions.

## Review and deliver

Check for conflicting camera directions, timing overload, ambiguous pronouns, image/motion contradictions, and sound events unsupported by the action. Preserve intentional surrealism; physical plausibility is a creative choice unless the brief requires realism.

Deliver a paste-ready prompt, separate settings/reference roles where useful, and only material assumptions or editing notes. For a review, explain the consequential problems first; rewrite only to the requested scope. A small correction does not require multiple alternatives or a new storyboard. Save files only when requested or when the project workflow calls for a durable prompt artifact.

When reviewing generated results, distinguish observed failures from hypotheses. Change one likely cause at a time and preserve what already works. If failures repeat, propose a concrete simplification, input change, shot split or model alternative. Stay within any generation authorization and budget.

Call an untested prompt a draft. Claims about motion, identity, lip sync, timing or sound require actual playback evidence; vendor examples and prompt checks do not prove them.
