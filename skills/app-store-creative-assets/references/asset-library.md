# Asset Library upload, review and attachment

Read when the user has authorized uploading, submitting or attaching a header or search-results asset. Each step below is its own release action; do the ones authorized and stop there. Learned shipping header videos on 20–21 October 2026; when a step fails, recheck the API and the web UI before retrying.

Uploading and managing assets needs the Account Holder, Admin, App Manager or Marketing role; submitting for review needs Account Holder, Admin or App Manager.

## Upload (API)

1. Create the asset: `POST /v1/appAssetLibraryVideos` (images: `appAssetLibraryImages`) with `category` `CREATIVE_ASSETS`, `fileName`, `fileSize`, a `referenceName` naming placement, idea, locale and date, for video the `previewFrameTimeCode` (`HH:MM:SS:FF`, the chosen poster), and the `assetLibrary` relationship set to the app's ID.
2. PUT each part listed in the response's upload operations, then `PATCH` the asset with `uploaded: true`.
3. Poll until the asset reaches Prepare for Submission matched to the placement's spec. Done when it is matched and the uploaded bytes' hash equals the delivered checksum.

## Submit for review (web UI)

4. `reviewSubmissionItems` has no Asset Library relationship, so the API cannot put an asset into a submission. In App Store Connect open the app's Asset Library, choose **Add for Review** on the asset (it creates or joins a draft submission), then **Submit for Review**.
5. A draft that already exists can be submitted through the API: `PATCH /v1/reviewSubmissions/{id}` with `submitted: true`.

- Apple caps iOS submissions in review. With two already waiting, Submit was refused ("maximum number of submissions allowed in review"); the draft waits until one clears.
- The first visit to an app's Asset Library opens an intro popup that swallows the first click.
- After sign-in the browser can land in another team; when app pages show "Sorry, something went wrong", switch team in the account menu.

## Attach after approval (web UI)

6. Version page → Header and Search Results → the placement → Browse Assets → select the approved asset → Save, then Publish. No new app version is needed.
7. A newer version in review or in preparation carries its own slots. Set the asset there too, or releasing that version brings the old asset back.
8. Read back what is live with `GET /v1/appStoreVersionLocalizations/{id}/placements?include=image,video`. Done when the readback shows the asset in the intended placement and locale.

Record each state with its IDs, date and time in the project's status record: uploaded, submitted, approved, attached, published. The readback outranks a local status file.
