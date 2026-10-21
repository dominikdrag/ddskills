# Chrome and Flow mechanics

Use this reference when the Chrome connection, a native file chooser or Flow's controls require it. Flow's UI changes: observe it again instead of replaying coordinates or old accessibility indices.

## Chrome entry and input

Use a task-specific Chrome tab, or continue the clip's known project tab. If the harness exposes Chrome as a browser, use that interface. If it reports `Browser is not available: chrome`, use its native app interface. With `cua_repl`, the native entry is `await cua.getApp("Google Chrome")`; read the returned API documentation before further calls.

Flow's home was `https://flow.google.com/` in the observed workflow. Follow the current official redirect if it changes. Reuse existing authentication. Leave password, MFA or CAPTCHA steps requiring the user to the user and continue independent preparation.

On native Chrome, a paste can leave a prompt or path unchanged. Inspect the resulting field. For a settable accessibility field, `setValue` was reliable in the observed workflow. Verify the prompt text and the enabled generation control before submission. A new tab or modal can renumber the accessibility tree, so observe after the transition before selecting another element.

## Reference upload

In Frames mode, select Start to open the frame picker, then Upload media. On a macOS file chooser, open Go to Folder with Command-Shift-G, observe its path field, set the full known file path and press Return. Confirm the intended file is selected before choosing Open. Waiting for the chooser state avoids accepting its previous folder by mistake.

Wait until the upload is complete and the preview is the intended image. Choose Add to prompt and confirm it occupies the intended first-frame slot; the presence of a media tile alone does not establish attachment to the generation.

## Settings and submission

Observe the settings panel with the reference and prompt already attached. Verify all requested controls and x1 together, including the model label, which may be clearer in a screenshot than in the accessibility tree. Recheck after a model or mode change because dependent settings can reset.

After submitting, retain the project URL and provider state. When the clip tile is ready, open it. The editor can initially show a zero duration while loading; wait for the actual duration and playable preview. Its media identifier can be retained from the observed editor URL.

## Original download

Use Download media and choose the requested original size. In the observed UI, `720p Original size` was distinct from 1080p/4K upscales and an animated GIF. Accept a native save dialog with a descriptive filename. Then verify Chrome's Done state and the downloaded file on disk.

For playback, disable looping when useful and verify the player reaches the end. A few sampled frames help review continuity but do not establish speech accuracy or fluid motion. Retain the raw file and report an observed creative deviation; downloading again is a recovery step, while generating again spends another attempt.
