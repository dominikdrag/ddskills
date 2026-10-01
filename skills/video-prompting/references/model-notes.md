# Model notes and official sources

Research snapshot: **27 September 2026**. These are version-specific vendor recommendations, not measured success rates. Read only the relevant model section. Recheck the selected model and host when support, settings or current availability matter; a newer version need not share an older version's behavior.

## Runway Gen-4 and Gen-4.5

- Gen-4's guide favors simple scenes, motion-focused image-to-video instructions and positive descriptions. It explicitly says negative prompting is unsupported. Prefer an affirmative state such as a fixed camera over a list of prohibited movements. [Gen-4 guide](https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide).
- Gen-4.5's text-to-video guide supports sequenced actions and approximate timestamps. It specifies no ideal prompt length and no inherent priority for words placed first. Natural sentences clarify relationships. Simplicity is a useful starting point, not a ban on choreography. [Text-to-video guide](https://help.runwayml.com/hc/en-us/articles/42460036199443-Text-to-Video-Prompting-Guide).
- For image-to-video, the image supplies the starting appearance. Motion blur, dust or a pose may imply movement that conflicts with the requested action. If unwanted cuts recur, check action duration and wording that suggests cuts. [Image-to-video guide](https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide).
- Runway's general guide recommends positive language, removing conflicting requirements and rebuilding a failed complex prompt from its essentials. JSON formatting provides no special precision. [Prompting principles](https://help.runwayml.com/hc/en-us/articles/46182941379347-Introduction-to-Prompting).

Use [generation controls](https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5) to check the current mode's settings. For complex moves, describe what enters view, not just a camera term. [Camera reference](https://help.runwayml.com/hc/en-us/articles/46749315925395-Camera-Terms-Prompts-Examples).

## Google Veo

- Google's technical best practices recommend a focused moment per short clip. For image-to-video, use a clear source image and describe motion rather than restating existing appearance. For dialogue, the technical guide recommends a speaker/action followed by a colon and unquoted speech. [Best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice).
- Describe audio in separate sentences, distinguishing ambience, effects and speech. Where the selected interface supports a negative prompt, list unwanted elements instead of writing commands containing “no” or “don't.” Do not put an exclusion list into an ordinary positive prompt without verifying how the host handles it. [Prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide).
- Google's Veo 3.1 blog demonstrates ingredient references, first/last-frame transitions and timestamped multi-shot prompts. It also uses quoted dialogue, unlike the technical best-practices page. Prefer current technical guidance for the selected surface; disclose an unresolved conflict when it affects the task. [Veo 3.1 workflows](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1/).

Practical synthesis: single shots are a useful baseline, while deliberate multi-shot prompts are valid experiments. For exact cuts, use an editing timeline. Do not infer that every feature documented for Google's API is exposed in Flow or another host.

## Adobe Firefly Video

Adobe's suggested structure is shot, character, action, location and aesthetic. Specify pace and concrete visual details; its guide warns about scenes with more than four subjects and says longer prompts do not always improve results. Treat that subject-count advice as model guidance rather than a universal rule. [Prompt guide](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/writing-effective-text-prompts-for-video-generation.html).

Firefly is also a host for partner models. Inspect which model is selected before applying Adobe-specific recommendations or controls. [Generation settings](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/generate-videos-using-text-prompts.html).

## Luma Ray3 / Ray3.14

Luma recommends present-tense, mid-action verbs, physical secondary motion and positive wording. With keyframes, focus on what changes. Its Ray3/Ray3.14 field guide gives version-specific style and length advice; do not export those preferences to unrelated models or assume these are the newest releases. Reference features also differ between versions. Use only the Luma sections as primary evidence for Luma behavior. [Luma field guide](https://lumalabs.ai/learning-hub/luma-video-models-guide-ray3.14-veo-sora-kling-compared).

## Sora 2: historical reference

At the research date, OpenAI labels its Sora 2 prompting recipe archived and lists the Videos API and Sora 2 shutdown date as 24 September 2026. A still-readable guide does not establish current access. [Deprecations](https://developers.openai.com/api/docs/deprecations).

The archived guide remains useful craft context: actions in beats, a clear subject action and camera move per shot, consistent character and lighting descriptions, and concise speaker-labelled dialogue. Do not present its API examples or limits as current production instructions. [Archived guide](https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide).

## Other models or uncertain support

Use the requested model's first-party guide. Verify the relevant mode, reference roles, audio and controls; do not substitute a better-documented model silently. If no authoritative guidance is accessible, provide a clearly labelled general draft and identify the specific unsupported assumption.
