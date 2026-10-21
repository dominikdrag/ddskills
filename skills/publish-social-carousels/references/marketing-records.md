# Marketing records and Studio

Resolve the current marketing root from task context. Read its `AGENTS.md`, `ai-rules/campaigns.md` and the relevant claims/profile sources. Keep the skill generic; account credentials and workstation paths belong outside it.

## Source and record ownership

`campaign.json` declares assets, hashes, platform copy files and publishable units. It can express three layouts supported by `scripts/prepare.py`:

- A post owns all platforms and copy, while child variants supply the portrait image sets.
- Child variants each own a subset of platforms and their copy; publication keys are `post/variant`.
- A post owns all platforms and contains separate `exports/images/instagram/` and `exports/images/tiktok/` sets.

Use platform declarations to resolve the publication key. Choose exactly one numbered image directory with the requested aspect ratio; ambiguity needs resolution. The helper reads PNG dimensions and manifest hashes, not visual quality or product availability. Inspect the retained artwork and current claim evidence separately. It supports the established numbered PNG workflow; other media need their own preparation.

Canonical publishing `.txt` files take precedence over captions cached in slideshow JSON or render source. For unresolved tasks, the helper reads the files referenced by the manifest and emits their text and hashes. It reports records without using their absence as proof that a remote post is absent. An existing published record with a URL is skipped without revalidating its old inputs, so an archived or damaged completed pack does not block remaining platforms. Use `--check-published-inputs` for an explicit audit. Scheduled or incomplete records need reconciliation.

## Local recording

Only after live verification:

```sh
python3 tools/campaigns/campaigns.py posted <campaign> <post-or-post/variant> \
  <platform> --date YYYY-MM-DD --url <verified-permalink>
```

Use `--scheduled` only after the platform confirms a scheduled post. Read the exact entry back from that campaign's `publication.json`. The helper's `record_command` is an argument list template containing `<verified-live-url>`; it is not executed and is not proof of publication. Existing project tooling owns writes.

## Studio tracking

Open the date explicitly in the Studio calendar and match each card's ID and title. A date can contain a second InTouch carousel or another item outside the named request. Leave those items alone.

After each verified outcome, mark only its matching platform tick. Re-read the current checkbox state before clicking; Studio rerenders can invalidate later element indices. A checked tick is tracking evidence, not evidence that the social post exists. Reload once at the end to confirm persistence.

Studio stores posted ticks remotely; its normal next site publication imports them into `publication.json`. Record the verified URL locally through `campaigns.py` as well, so the URL is retained. A social publishing request does not require deploying the tracker website merely to update these ticks. Run the project's build/deploy process only when requested or independently required.

Keep run plans, receipts and screenshots outside marketing. Preserve unrelated dirty files, existing publication entries and the approved media bytes. Creating a skill does not authorize a Git commit, push or website deployment.
