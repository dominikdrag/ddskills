---
name: publish-social-carousels
description: Publish existing image carousels to Instagram, Facebook, TikTok and YouTube image Posts, or resume an interrupted publishing batch. Use for uploads, account switching, live verification and publication records; creative production belongs to the campaign workflow.
---

# Publish Social Carousels

Publish the requested existing assets, verify each live post, and record its URL. Keep creative production, publication and tracker deployment separate.

## Establish the batch

Read the project's publishing and claims rules. Resolve the requested post IDs against the supplied calendar or campaign manifests, including the date and timezone. An ID that disagrees with the named day needs clarification; a similar ID is not a substitution. Include only the requested posts and platforms.

Reuse the user's explicit publishing authorization for this batch. Creating this skill or preparing a pack grants no authorization to publish future batches. Once publishing is authorized, finish preparation, upload, verification and recording without another routine confirmation.

For each post/platform, identify the canonical caption files, ordered exports, expected account and publication record key. In marketing campaign manifests, platform declarations determine whether the record belongs to the post or a variant. Publishing text files are authoritative over cached JSON captions.

For projects using `campaign.json` and `publication.json`, run the bundled read-only helper:

```sh
python3 <skill-dir>/scripts/prepare.py --repo <marketing-root> \
  --date YYYY-MM-DD \
  --post <app>/campaigns/<campaign>/posts/<post-id> \
  --platforms instagram facebook tiktok youtube \
  --output <outside-repo>/plan.json
```

Repeat `--post` for a batch; pass only the authorized platforms. A single variant uses its actual folder, `posts/<post-id>/variants/<variant-id>`. The helper resolves platform variants, verifies declared PNG hashes, checks numbering and aspect ratios, reads canonical text and reports existing records. Completed records with URLs are skipped without requiring their old media/copy; add `--check-published-inputs` to audit those too. It preserves files and never operates a browser or marks a post published. Asset production states in the plan are not approval claims. For a different campaign schema, perform equivalent preparation using that project's tooling.

Read [Chrome publishing mechanics](references/chrome-publishing.md) for browser work. Read [marketing records](references/marketing-records.md) when using the Studio calendar and marketing repository.

## Reconcile before uploading

Use the requested browser; default to Google Chrome for signed-in social accounts. Inspect the live account identity before composing each post. Inspect saved account switching before asking for credentials. Account creation, password resets and global account settings are outside an ordinary publishing request.

Reconcile local publication records, any run receipt and the platform's recent posts. A published record is a reason to skip another upload. A scheduled record or uncertain submission needs inspection. A missing record does not prove the remote post is absent. When a previous submit may have succeeded, resolve that outcome in the content list or profile before retrying.

Keep a small run receipt outside the repository with post/platform, expected account, input hashes, status, live URL and screenshot path. Save uncertain outcomes as uncertain. Do not put credentials or private messages in the receipt.

## Upload and publish

1. Choose the platform's native photo/image post format. A carousel request does not authorize rendering a video. Use Instagram/Facebook 4:5 exports and TikTok/YouTube 9:16 exports when the campaign supplies those sets. On YouTube, use an image Post and describe it as such; a Studio label saying “YouTube Shorts” does not change the uploaded format. If the current UI cannot publish the requested image format or count, report the constraint before substituting a format or dropping slides.
2. Select every slide in ascending order and verify the selected count. Inspect the cover and portrait framing. Instagram can initially crop portrait artwork to a square; choose 4:5 or Original as appropriate. Preserve the approved artwork and filters.
3. Load the canonical platform copy. TikTok photo posts have a separate title and description. Confirm the actual editor state, character count and preview; visible text alone can be stale. Keep the full caption, product qualifiers and correct app screenshot slide number.
4. Apply AI and promotional disclosures supported by the asset provenance and account relationship. Use the native AI label for generated scenes. TikTok's own-brand option is distinct from a paid partnership. When the native label is unavailable, use a truthful explicit caption disclosure under the project's rules and record that choice. Keep automatic Facebook sharing off when Facebook has already been posted separately.
5. Verify account, slide count, framing, caption, disclosures and publish-now/schedule choice, then submit once. Capture the provider's success or failure state.

## Verify and record

Open the actual post from its profile or content list. Verify account, image carousel, caption and available labels. A composer closing or a feed appearing is not sufficient proof. Save a screenshot and the canonical permalink. If processing or moderation remains pending, report that state instead of calling the post live.

Record only verified outcomes through the project's existing publication tool. Read the record back, then mark the corresponding Studio platform tick if the project uses one. Re-read checkbox state before each click so an already completed platform stays checked. Reload once to verify persistence.

Resume only unresolved post/platform pairs. Finish with the actual published count, links, any remaining blocker and a proof screenshot. Keep scheduled, pending, failed and published distinct.
