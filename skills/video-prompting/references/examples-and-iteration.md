# Examples and iteration

These are original, untested examples and practical synthesis. They demonstrate decisions, not proven outputs or compulsory prompt lengths.

## A visible beat from a vague brief

Weak brief: “A cinematic watchman realizing he forgot something. Make it funny and professional.”

Text-to-video draft:

```text
Medium shot at eye level of a night watchman beside a desk in a quiet
museum office. He reaches for his tea, stops with his hand above the
cup, then slowly looks toward a wall clock. The camera gently pushes
toward his face. Cool moonlight and a small amber desk lamp.
Restrained live-action comedy.
```

Image-to-video adaptation, assuming the image already contains the person, cup and clock:

```text
The person reaches toward the cup, pauses with his hand above it,
then looks toward the clock. His sleeve settles after the movement.
The camera gently pushes toward his face.
```

Both preserve the same action and camera intention. If a referenced prop is absent, do not pretend it is visible: revise the composition, describe its introduction if supported, or change the action within the user's scope.

Optional audio for a supported Veo mode, using the technical guide's dialogue convention:

```text
The watchman says quietly: Was that today?
Audio: a low ventilation hum and the ticking of the wall clock.
```

The hand never touches the cup, so adding a ceramic clink would introduce an unexplained action. Check audio against the visual beats.

## Brief worksheet

Use only fields that help this request. This is working context; it need not all appear in the final video prompt.

```text
Model/version and host:
Mode and input assets, with each asset's role:
Selected duration and aspect ratio:
What the viewer should notice:
Visible action and endpoint:
Camera intention:
Appearance or continuity to preserve:
Exact dialogue, delivery and other sound:
Requirements that need editing:
```

For a single prompt, return one copyable block. Keep UI/API settings and asset mappings outside it. Include alternatives only when requested or useful for an unresolved creative choice.

## Multi-shot requests

Give each shot its own framing, action and audio direction. Fit their durations inside the selected clip length. Label timestamps as requested pacing in surrounding delivery notes; the prompt itself can state the intended times directly.

If the user requests an eight-second generation with a hard cut at three seconds, preserve that attempt. Explain that exact cut timing needs verification. A fallback is to generate each shot separately and place the cut at three seconds in editing. First/last-frame interpolation is not equivalent to two shot references plus a hard cut.

For continuity, reuse supported reference assets and stable identity descriptions appropriate to the mode. Do not assume a fresh generation remembers a previous prompt, or that a shared seed alone establishes identity.

## Diagnose the failure before rewriting

| Observed result | Useful next hypothesis or test |
|---|---|
| Identity or clothing changes | Check reference role/support, conflicting descriptions and transformation complexity |
| Image barely moves | Specify a visible action, its endpoint and a physical consequence |
| A required beat disappears | Reduce competing actions or allow more time |
| Camera follows the wrong thing | Name the tracked subject and distinguish its movement from camera movement |
| Requested still object keeps moving | Inspect the image for blur, dust or a pose implying motion |
| Unwanted cut | Check duration and cut-like wording; test continuous-shot language |
| Dialogue rushes | Read the line aloud; allow time or propose a shorter line for review |
| Speakers swap lines | Use unambiguous speaker labels and fewer simultaneous actions |
| Logo, text or actual UI is unreliable | Use supplied authentic assets and typography in editing |

These are hypotheses. The input-cue and unwanted-cut tests are documented in [Runway's image-to-video guide](https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide); adapt them cautiously for other models.

Record the prompt, model/version, assets, controls and prompt-enhancement state when running comparisons. Change one likely cause while keeping the rest stable. Review the complete clip for action, identity, contact, camera, timing, audio and ending. A promising frame or one successful sample is limited evidence; repeat only when the result and production stakes warrant it.
