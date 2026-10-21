# Chrome publishing mechanics

These are observed recovery paths, not permanent selectors. Read the current Computer Use tool documentation and derive controls from fresh UI state. Never carry element IDs, coordinates or tab numbers into another run.

## Browser and account selection

Prefer the Chrome browser binding when the harness exposes it. If Chrome is available only as a native app, bind it through the Computer Use API, for example `cua.getApp("com.google.Chrome")`. Keep computer interaction in that API; a local preparation helper is not a browser-control fallback.

Use task-specific tabs. Preserve tabs opened by the user for authentication. Switching Instagram profiles means the website's account switcher, not Chrome's browser profiles.

Instagram's account list can depend on the current account. If an app profile shows only itself and the personal account, switch to the already signed-in personal account and open **More / Switch accounts** again. That can reveal the other saved app profiles. Wait for the switch to finish, then verify the composer shows the intended app handle. The viewed profile's URL can remain unchanged after switching; use the active account avatar or composer identity as evidence.

For TikTok and YouTube, verify the account/channel identity in the current uploader or profile. Meta Business Suite's selected Facebook page does not establish an Instagram connection.

## Native file selection

Open the uploader, invoke the macOS file picker's **Go to Folder** (`super+shift+g`), enter the exact export directory and confirm it. Read UI state between navigation steps.

Select the first numbered slide and Shift-click the last. Verify the picker reports the intended number of documents before opening. A Select All sent while a filename is focused may select its text rather than all files. Verify the uploaded count and ascending order in the platform preview.

Native accessibility trees sometimes expose both an outer and inner button for the same control. If the outer crop/menu button has no effect, inspect the screenshot or try the observed inner button. Fetch a new state after each action. A stale element error warrants refreshing the native app binding and reading current state, not repeating the action blindly.

## Captions and clipboard

Prefer browser-supported field filling or clipboard APIs when available. In native Chrome, the reliable path observed in Studio was:

1. Click the matching **Copy caption / Copy title / Copy description** button in Studio.
2. Read state to let the copy action settle, then switch to the destination tab.
3. Click the real editor and press `super+v`.
4. Verify the actual caption and updated character count. Compare against the canonical file; resolve any stale Studio copy before publishing.

Native `setValue()` on a web contenteditable can change visible text without updating the site's editor state. Avoid it for captions. The native app's temporary-clipboard `paste()` was also unreliable in this workflow. Ordinary address-bar controls can use `setValue()`; verify navigation after Return.

For TikTok, copy the title and description separately. Inspect the final preview and count rather than assuming multiline typing delivered the exact text. Keep an observed caption mismatch unresolved until the live post or edit dialog shows the full canonical text.

## Platform controls and verification

- **Instagram:** Create a Post, upload all images, choose 4:5 or Original, keep the original filter, then add caption and the AI label where required. Confirm any Facebook sharing switch is off if posting Facebook separately. A successful upload can take tens of seconds. Wait for **Your post has been shared**, then open the new carousel on the profile to obtain its permalink.
- **TikTok:** Use the photo uploader. Under **More options**, enable AI disclosure for generated scenes and **Your brand** for promotion of the account's own app. These toggles may require screenshot-based interaction when absent from accessibility output; observe the expanded controls and checked state afterward. A first-use AI notice may need its ordinary enable action. After publishing, refresh the content list once if it still shows older posts. Open the new entry: the content list may link to `/video/<id>` while the live carousel resolves to `/photo/<id>`. Save the live photo URL without transient image-position parameters.
- **Facebook:** Use the intended page's photo post. Paste the caption through a real editor input action and verify the published text. If the caption was lost, edit the existing post instead of creating a duplicate. Business Suite may not expose a native AI switch; inspect current controls and record a truthful caption disclosure when needed. Capture the actual page post permalink.
- **YouTube:** Switch to the intended channel, create an image Post and verify the current picker supports the full count. Use the canonical image-Post body. In the observed workflow the picker accepted up to ten images; inspect the current UI if the pack exceeds that count. Verify the public `/post/<id>` page, not only a creation toast. Image Posts and Shorts are separate formats.

Enable disclosures from the campaign's actual provenance, not from these examples alone. A truthful fallback for a campaign whose generated cover and closing scene frame a genuine app capture is: “Cover and closing scene are AI-generated. App screenshot is real, with example data.” Adapt only to facts that are documented for the assets being posted.

If submit leaves an uncertain result, inspect the profile/content list before trying again. Do independent preparation while processing; keep user updates brief. Save publication screenshots outside the repository and include an appropriate proof screenshot in the final response.
